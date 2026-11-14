import unittest

from update_hiddify import package_recipe


class UpdateInstallerTests(unittest.TestCase):
    def release(self):
        return {'version': '5.9.2', 'assets': [{
            'name': 'Hiddify-Linux-x64.AppImage',
            'browser_download_url': 'https://github.com/hiddify/hiddify-app/releases/download/v5.9.2/Hiddify-Linux-x64.AppImage',
            'digest': 'sha256:' + 'a' * 64,
        }]}

    def test_verified_release_builds_package_for_existing_launcher(self):
        recipe = package_recipe(self.release(), 'x86_64')
        self.assertIn('pkgver=5.9.2', recipe)
        self.assertIn("sha256sums=('" + 'a' * 64 + "')", recipe)
        self.assertIn('/opt/hiddify/Hiddify.AppImage', recipe)
        self.assertNotIn('--appimage-extract', recipe)

    def test_unverified_download_is_rejected(self):
        for field, value in [('digest', None), ('digest', 'sha256:bad'),
                             ('browser_download_url', 'https://example.invalid/file')]:
            release = self.release()
            release['assets'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                package_recipe(release, 'x86_64')

    def test_invalid_version_and_architecture_are_rejected(self):
        release = self.release()
        with self.assertRaises(ValueError):
            package_recipe(release, 'unknown')
        release['version'] = '5.9.2;whoami'
        with self.assertRaises(ValueError):
            package_recipe(release, 'x86_64')

    def test_existing_package_name_is_preserved(self):
        recipe = package_recipe(self.release(), 'x86_64', 'hiddify-app-bin')
        self.assertIn('pkgname=hiddify-app-bin', recipe)
        with self.assertRaises(ValueError):
            package_recipe(self.release(), 'x86_64', 'other-package')


class InstallerFlowTests(unittest.TestCase):
    def setUp(self):
        import pathlib
        import tempfile
        from unittest import mock
        import update_hiddify as updater
        self.updater = updater
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.prefs = self.root / 'preferences.json'
        updater.backend.save_json(self.prefs, {'flutter.service-mode': 'vpn', 'unrelated': 'keep'})
        self.commands = []
        release = UpdateInstallerTests().release()

        def output(command, **kwargs):
            if command[0] == 'pacman':
                return 'hiddify-app-bin\n'
            if command[0] == 'uname':
                return 'x86_64\n'
            if command == ['makepkg', '--packagelist']:
                artifact = pathlib.Path(kwargs['cwd']) / 'hiddify-app-bin-5.9.2-1-x86_64.pkg.tar.zst'
                artifact.write_bytes(b'fixture package')
                return str(artifact) + '\n'
            raise AssertionError(command)

        self.patches = [
            mock.patch.object(updater.backend, 'PREFS', self.prefs),
            mock.patch.object(updater.backend, 'STATE', self.root / 'state'),
            mock.patch.object(updater.backend, 'fetch_latest_release', return_value=release),
            mock.patch.object(updater.backend, 'installed', return_value=True),
            mock.patch.object(updater.backend, 'version', return_value='5.9.0-1'),
            mock.patch.object(updater.backend, 'executable', return_value='/usr/bin/hiddify'),
            mock.patch.object(updater.backend, 'running', return_value=False),
            mock.patch.object(updater.shutil, 'which', return_value='/usr/bin/makepkg'),
            mock.patch.object(updater.subprocess, 'check_output', side_effect=output),
            mock.patch.object(updater.subprocess, 'run', side_effect=lambda command, **kwargs: self.commands.append(command)),
        ]
        self.mocks = [patch.start() for patch in self.patches]

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.temp.cleanup()

    def test_build_then_install_preserves_mode_and_unrelated_preferences(self):
        self.updater.main('en')
        self.assertEqual(self.commands[0], ['makepkg', '--syncdeps'])
        self.assertEqual(self.commands[1][:4], ['sudo', 'pacman', '-U', '--'])
        self.assertIn('hiddify-app-bin-5.9.2', self.commands[1][-1])
        self.assertEqual(self.updater.backend.read_json(self.prefs), {'flutter.service-mode': 'vpn', 'unrelated': 'keep'})

    def test_app_started_during_build_blocks_privileged_install(self):
        self.mocks[6].side_effect = [False, False, True]
        with self.assertRaises(RuntimeError):
            self.updater.main('en')
        self.assertEqual(self.commands, [['makepkg', '--syncdeps']])

    def test_failed_package_install_preserves_preferences(self):
        import subprocess

        def run(command, **kwargs):
            if command[0] == 'sudo':
                raise subprocess.CalledProcessError(1, command)

        self.mocks[-1].side_effect = run
        before = self.prefs.read_bytes()
        with self.assertRaises(subprocess.CalledProcessError):
            self.updater.main('ru')
        self.assertEqual(self.prefs.read_bytes(), before)
