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
