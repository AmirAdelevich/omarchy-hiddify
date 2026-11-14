import pathlib
import unittest
from unittest import mock

import test_backend as fixtures

b = fixtures.b
SQL = fixtures.SQL


class RecoveryTests(unittest.TestCase):
    setUp = fixtures.BackendTests.setUp
    tearDown = fixtures.BackendTests.tearDown
    prepare = fixtures.BackendTests.prepare

    def test_restore_can_be_undone_with_profile_config_intact(self):
        result = b.main({'action': 'commit_import', 'token': self.prepare()})
        pid = b.profiles()[0]['id']
        config = b.DATA / 'configs' / (pid + '.json')
        contents = config.read_bytes()
        b.main({'action': 'restore'})
        self.assertFalse(config.exists())
        b.main({'action': 'restore'})
        self.assertEqual(b.profiles()[0]['id'], pid)
        self.assertEqual(config.read_bytes(), contents)
        self.assertTrue((b.STATE / 'backups' / result['backup'] / 'snapshot.json').is_file())

    def test_interrupted_file_write_recovers_previous_database_and_files(self):
        token = self.prepare()
        original = b.atomic

        def interrupted(path, data):
            original(path, data)
            if path.parent == b.DATA / 'configs':
                raise SystemExit('simulated process termination')

        with mock.patch.object(b, 'atomic', side_effect=interrupted):
            with self.assertRaises(SystemExit):
                b.main({'action': 'commit_import', 'token': token})
        self.assertTrue((b.STATE / 'pending-write.json').is_file())
        b.main({'action': 'recover_write'})
        self.assertEqual(b.profiles(), [])
        self.assertEqual(list((b.DATA / 'configs').glob('*.json')), [])
        self.assertFalse((b.STATE / 'pending-write.json').exists())

    def test_interrupted_post_commit_bookkeeping_is_recoverable(self):
        original = b.save_json

        def interrupted(path, data):
            if path.name == 'operation.json':
                raise SystemExit('simulated termination after database commit')
            return original(path, data)

        with mock.patch.object(b, 'save_json', side_effect=interrupted):
            with self.assertRaises(SystemExit):
                b.main({'action': 'commit_import', 'token': self.prepare()})
        self.assertEqual(len(b.profiles()), 1)
        b.main({'action': 'recover_write'})
        self.assertEqual(b.profiles(), [])
        self.assertEqual(list((b.DATA / 'configs').glob('*.json')), [])

    def test_recovery_refuses_to_overwrite_running_app(self):
        backup = b.snapshot()
        b.save_json(b.STATE / 'pending-write.json', {'backup': backup.name})
        with mock.patch.object(b, 'running', return_value=True), self.assertRaisesRegex(b.UserError, 'recovery_close_app'):
            b.main({'action': 'recover_write'})
        self.assertTrue((b.STATE / 'pending-write.json').exists())

    def test_incomplete_backup_does_not_destroy_current_data(self):
        folder = b.snapshot()
        b.save_json(folder / 'snapshot.json', {'schemaVersion': 1, 'configs': ['missing.json'], 'preferences': True, 'database': True})
        original = b.PREFS.read_bytes()
        with self.assertRaisesRegex(b.UserError, 'invalid_backup'):
            b.restore_snapshot(folder)
        self.assertEqual(b.PREFS.read_bytes(), original)

    def test_unfinished_snapshot_is_never_selected_as_restore_target(self):
        b.snapshot()
        b.save_json(b.PREFS, {'flutter.mixed-port': 12345})
        partial = b.STATE / 'backups' / '.unfinished'
        partial.mkdir()
        (partial / 'db.sqlite').write_bytes(b'incomplete')
        b.main({'action': 'restore'})
        self.assertEqual(b.read_json(b.PREFS)['flutter.mixed-port'], 12334)

    def test_failure_halfway_through_restore_rolls_back_database_and_configs(self):
        b.main({'action': 'commit_import', 'token': self.prepare()})
        before = b.profiles()
        config = b.DATA / 'configs' / (before[0]['id'] + '.json')
        contents = config.read_bytes()
        original = b.atomic
        failed = False

        def fail_once(path, data):
            nonlocal failed
            if path == b.PREFS and not failed:
                failed = True
                raise OSError('simulated interrupted restore')
            return original(path, data)

        with mock.patch.object(b, 'atomic', side_effect=fail_once):
            with self.assertRaises(OSError):
                b.main({'action': 'restore'})
        self.assertEqual(b.profiles(), before)
        self.assertEqual(config.read_bytes(), contents)
        self.assertFalse((b.STATE / 'pending-write.json').exists())

    def test_app_restarted_during_write_retains_journal_instead_of_overwriting_it(self):
        original = b.save_json
        restarted = False

        def save(path, data):
            nonlocal restarted
            result = original(path, data)
            if path.name == 'operation.json':
                restarted = True
            return result

        with mock.patch.object(b, 'running', side_effect=lambda: restarted), mock.patch.object(b, 'save_json', side_effect=save):
            with self.assertRaisesRegex(b.UserError, 'recovery_close_app'):
                b.main({'action': 'commit_import', 'token': self.prepare()})
        self.assertTrue((b.STATE / 'pending-write.json').is_file())
        b.main({'action': 'recover_write'})
        self.assertEqual(b.profiles(), [])


class CompatibilityTests(unittest.TestCase):
    def test_current_schema_is_supported_without_mocking_compatibility(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            data = pathlib.Path(directory)
            with b.dbconnect(data / 'db.sqlite') as db:
                db.execute(SQL)
                db.execute('PRAGMA user_version=7')
            with mock.patch.object(b, 'DATA', data):
                for version in ('5.9.0-1', '5.9.1-1', '5.9.2-1', '1:5.9.2-2'):
                    with self.subTest(version=version), mock.patch.object(b, 'version', return_value=version):
                        self.assertTrue(b.compatible())
                with mock.patch.object(b, 'version', return_value='5.9.2-1'):
                    with b.dbconnect(data / 'db.sqlite') as db:
                        db.execute('PRAGMA user_version=999')
                    self.assertFalse(b.compatible())
                with mock.patch.object(b, 'version', return_value='99.0.0-1'):
                    self.assertFalse(b.compatible())


class CurrentHiddifyIntegrationTests(unittest.TestCase):
    setUp = fixtures.BackendTests.setUp
    tearDown = fixtures.BackendTests.tearDown

    def test_real_import_with_the_actual_installed_version_gate(self):
        self.patches[3].stop()
        try:
            b.cli_command()
        except b.UserError:
            self.skipTest('Hiddify CLI is not installed')
        with b.dbconnect(b.DATA / 'db.sqlite') as db:
            db.execute('PRAGMA user_version=7')
        self.assertTrue(b.compatible(), 'The actual installed Hiddify version must pass the schema gate')
        fixtures.BackendTests.test_real_cli_import_prepare_commit(self)
