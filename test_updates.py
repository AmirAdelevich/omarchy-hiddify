import concurrent.futures
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('updater_backend', pathlib.Path(__file__).with_name('backend.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
REAL_NOTIFY_UPDATE = b.notify_update


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.clock = 10000
        self.patches = [
            mock.patch.object(b, 'STATE', pathlib.Path(self.directory.name)),
            mock.patch.object(b, 'installed', return_value=True),
            mock.patch.object(b, 'version', return_value='5.5.5-1'),
            mock.patch.object(b.time, 'time', side_effect=lambda: self.clock),
            mock.patch.object(b, 'fetch_latest_release', return_value={
                'version': '5.5.6', 'url': 'https://github.com/hiddify/hiddify-app/releases/tag/v5.5.6'}),
            mock.patch.object(b, 'notify_update', return_value=True),
        ]
        self.mocks = [patch.start() for patch in self.patches]
        self.fetch = self.mocks[-2]
        self.notify = self.mocks[-1]

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.directory.cleanup()

    def check(self, force=False):
        return b.check_updates({'action': 'check_updates', 'language': 'ru', 'force': force})['updates']

    def test_hourly_cadence_and_persistent_notification_deduplication(self):
        self.assertEqual(self.check()['status'], 'update_available')
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(self.notify.call_count, 1)
        self.clock += 1800
        self.assertEqual(self.check()['nextCheckSeconds'], 1800)
        self.assertEqual(self.fetch.call_count, 1)
        self.clock += 1800
        self.check()
        self.check(force=True)
        self.assertEqual(self.fetch.call_count, 3)
        self.assertEqual(self.notify.call_count, 1)
        self.assertEqual(b.load_update_state()['notifiedVersions'], ['5.5.6'])

    def test_up_to_date_is_status_text_without_background_popup(self):
        self.fetch.return_value = {'version': '5.5.5', 'url': 'https://github.com/hiddify/hiddify-app/releases/tag/v5.5.5'}
        self.assertEqual(self.check()['status'], 'updates_current')
        self.notify.assert_not_called()

    def test_another_release_gets_one_new_notification(self):
        self.check()
        self.clock += 3600
        self.fetch.return_value = {'version': '5.6.0', 'url': 'https://github.com/hiddify/hiddify-app/releases/tag/v5.6.0'}
        self.check()
        self.check(force=True)
        self.assertEqual(self.notify.call_count, 2)

    def test_installed_update_recomputes_cached_status(self):
        self.check()
        with mock.patch.object(b, 'version', return_value='5.5.6-2'):
            self.assertEqual(self.check()['status'], 'updates_current')
        self.assertEqual(self.fetch.call_count, 1)

    def test_disable_persists_but_explicit_checks_are_supported(self):
        b.check_updates({'action': 'update_settings', 'enabled': False})
        self.assertFalse(self.check()['enabled'])
        self.fetch.assert_not_called()
        self.check(force=True)
        self.fetch.assert_called_once()

    def test_failure_does_not_claim_latest_and_retries_next_hour(self):
        self.fetch.side_effect = OSError('offline')
        self.assertEqual(self.check()['status'], 'update_check_failed')
        self.assertEqual(self.check()['status'], 'update_check_failed')
        self.assertEqual(self.fetch.call_count, 1)
        self.notify.assert_not_called()
        self.clock += 3600
        self.check()
        self.assertEqual(self.fetch.call_count, 2)

    def test_failed_notification_can_retry_after_an_hour(self):
        self.notify.return_value = False
        self.check()
        self.assertEqual(b.load_update_state()['notifiedVersions'], [])
        self.clock += 3600
        self.notify.return_value = True
        self.check()
        self.assertEqual(self.notify.call_count, 2)

    def test_concurrent_monitors_share_one_check_and_notification(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.check(), range(2)))
        self.assertEqual([result['status'] for result in results], ['update_available'] * 2)
        self.fetch.assert_called_once()
        self.notify.assert_called_once()

    def test_missing_installation_does_not_schedule_a_tight_retry_loop(self):
        with mock.patch.object(b, 'installed', return_value=False):
            result = self.check()
        self.assertEqual(result['status'], 'not_installed')
        self.assertEqual(result['nextCheckSeconds'], 3600)
        self.fetch.assert_not_called()

    def test_corrupt_cache_can_recover(self):
        (b.STATE / 'updates.json').write_text('not json')
        self.assertEqual(self.check()['status'], 'update_available')

    def test_version_comparison_handles_multi_digit_segments(self):
        self.assertGreater(b.release_version('v5.10.0'), b.release_version('5.9.99'))
        self.assertEqual(b.installed_release_version('1:5.5.5-3'), b.release_version('5.5.5'))
        for tag in ('<img src=x>', 'v5.5.5-beta', 'https://example.invalid', '999999999.0.0'):
            with self.assertRaises(ValueError):
                b.release_version(tag)

    def test_notification_text_is_escaped_for_shared_sink(self):
        with mock.patch.object(b, 'read_json', return_value={
                'update_notification_title': '<b>Update</b>',
                'update_notification_body': '<img src="https://example.invalid"> %1'}), \
                mock.patch.object(b.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(REAL_NOTIFY_UPDATE({'version': '5.5.6'}, 'ru'))
            arguments = run.call_args.args[0]
            self.assertNotIn('<', arguments[-1])
            self.assertNotIn('<', arguments[-2])
            self.assertIn('&lt;img', arguments[-1])


class ReleaseResponseTests(unittest.TestCase):
    def fetch(self, release):
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = json.dumps(release if isinstance(release, list) else [release]).encode()
        response.__enter__.return_value = response
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(b.urllib.request, 'build_opener', return_value=opener):
            return b.fetch_latest_release()

    def test_stable_official_release_is_accepted(self):
        result = self.fetch({'tag_name': 'v5.5.6', 'draft': False, 'prerelease': False,
                             'html_url': 'https://github.com/hiddify/hiddify-app/releases/tag/v5.5.6'})
        self.assertEqual(result['version'], '5.5.6')

    def test_draft_or_unexpected_url_is_rejected(self):
        release = {'tag_name': 'v5.5.6', 'draft': False, 'prerelease': False,
                   'html_url': 'https://github.com/hiddify/hiddify-app/releases/tag/v5.5.6'}
        for changes in ({'draft': True}, {'html_url': 'https://example.invalid'},
                        {'tag_name': '<img src=x>'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.fetch({**release, **changes})

    def test_newest_numbered_prerelease_is_selected(self):
        def release(tag, prerelease=False):
            return {'tag_name': tag, 'draft': False, 'prerelease': prerelease,
                    'html_url': 'https://github.com/hiddify/hiddify-app/releases/tag/' + tag}
        result = self.fetch([release('draft', True), release('v5.9.1', True),
                             release('v5.5.5'), release('v5.9.2', True)])
        self.assertEqual(result['version'], '5.9.2')
        self.assertIs(result['prerelease'], True)
        status = b.update_result({'latest': result}, '5.9.0-1')
        self.assertIs(status['prerelease'], True)
