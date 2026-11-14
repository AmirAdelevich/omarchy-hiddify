#!/usr/bin/env python3
"""Install a verified official AppImage as an Arch package in a visible terminal."""
import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile

import backend


def package_recipe(release, machine, package='hiddify'):
    if package not in ('hiddify', 'hiddify-app-bin', 'hiddify-bin', 'hiddify-next-bin'):
        raise ValueError('Unsupported Hiddify package')
    architecture = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(machine)
    if architecture is None:
        raise ValueError('Unsupported architecture')
    version = release['version']
    backend.release_version(version)
    filename = f'Hiddify-Linux-{architecture}.AppImage'
    url = f'https://github.com/hiddify/hiddify-app/releases/download/v{version}/{filename}'
    assets = release.get('assets')
    if not isinstance(assets, list):
        raise ValueError('Missing release assets')
    asset = next((item for item in assets if isinstance(item, dict) and item.get('name') == filename), {})
    digest = asset.get('digest', '')
    if asset.get('browser_download_url') != url or not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ValueError('Missing verified official download')
    return f"""pkgname={package}
pkgver={version}
pkgrel=1
pkgdesc='Hiddify proxy client'
arch=('{machine}')
url='https://github.com/hiddify/hiddify-app'
license=('GPL-3.0-only')
depends=('fuse3' 'gtk3' 'libayatana-appindicator')
options=('!strip' '!debug')
source=('{url}')
sha256sums=('{digest.removeprefix('sha256:')}')

package() {{
    install -Dm755 "$srcdir/{filename}" "$pkgdir/opt/hiddify/Hiddify.AppImage"
    install -Dm755 "$startdir/hiddify" "$pkgdir/usr/bin/hiddify"
    install -Dm644 "$startdir/hiddify.desktop" "$pkgdir/usr/share/applications/hiddify.desktop"
    if [[ -f "$startdir/hiddify.png" ]]; then
        install -Dm644 "$startdir/hiddify.png" "$pkgdir/usr/share/icons/hicolor/256x256/apps/hiddify.png"
    fi
}}
"""


def main(language='en', check=False):
    strings = backend.read_json(backend.ROOT / 'i18n' / (language + '.json'), {})

    if not shutil.which('makepkg'):
        raise RuntimeError('makepkg is required')
    release = backend.fetch_latest_release()
    if backend.installed() and backend.installed_release_version(backend.version()) >= backend.release_version(release['version']):
        print('' if check else strings['installer_current'])
        return
    if check:
        print(release['version'])
        return
    if backend.running():
        raise RuntimeError(strings['close_app_first'])
    package = 'hiddify-app-bin'
    if backend.installed():
        package = subprocess.check_output(['pacman', '-Qoq', backend.executable()], text=True).strip()
    machine = subprocess.check_output(['uname', '-m'], text=True).strip()
    recipe = package_recipe(release, machine, package)
    kind = strings['prerelease' if release.get('prerelease') else 'stable_release']
    print(strings['installer_updating'].replace('%1', release['version']).replace('%2', kind), flush=True)
    with tempfile.TemporaryDirectory(prefix='hiddify-update-') as directory:
        work = pathlib.Path(directory)
        (work / 'PKGBUILD').write_text(recipe)
        (work / 'hiddify').write_text('#!/bin/sh\nexec /opt/hiddify/Hiddify.AppImage "$@"\n')
        (work / 'hiddify.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=Hiddify\nExec=hiddify %U\n'
            'Icon=hiddify\nTerminal=false\nCategories=Network;\n'
            'MimeType=x-scheme-handler/hiddify;\n')
        icon = pathlib.Path('/usr/share/icons/hicolor/256x256/apps/hiddify.png')
        if icon.is_file():
            shutil.copy2(icon, work / 'hiddify.png')
        backend.private_state()
        with (backend.STATE / 'write.lock').open('a') as lock:
            backend.fcntl.flock(lock, backend.fcntl.LOCK_EX)
            if backend.running():
                raise RuntimeError(strings['close_app_first'])
            mode_key = 'flutter.service-mode'
            saved_mode = backend.read_json(backend.PREFS, {}).get(mode_key)
            environment = dict(backend.os.environ, PKGDEST=directory)
            subprocess.run(['makepkg', '--syncdeps'], cwd=work, check=True, env=environment)
            artifacts = subprocess.check_output(['makepkg', '--packagelist'], cwd=work,
                                                text=True, env=environment).splitlines()
            if len(artifacts) != 1:
                raise RuntimeError('Expected one Hiddify package')
            artifact = pathlib.Path(artifacts[0])
            if artifact.parent != work or artifact.is_symlink() or not artifact.is_file():
                raise RuntimeError('Invalid Hiddify package path')
            if backend.running():
                raise RuntimeError(strings['close_app_first'])
            subprocess.run(['sudo', 'pacman', '-U', '--', str(artifact)], check=True)
            if saved_mode in ('vpn', 'proxy', 'system-proxy', 'router') and not backend.running():
                prefs = backend.read_json(backend.PREFS, {})
                if prefs.get(mode_key) != saved_mode:
                    prefs[mode_key] = saved_mode
                    backend.save_json(backend.PREFS, prefs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', choices=('en', 'ru'), default='en')
    parser.add_argument('--check', action='store_true')
    arguments = parser.parse_args()
    main(arguments.language, arguments.check)
