"""Discover and package official Linux builds of Hiddify for Arch."""
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

import backend

API = 'https://api.github.com/repos/hiddify/hiddify-app/releases?per_page=30'
ASSETS = {'x86_64': 'x64', 'aarch64': 'arm64'}


def release():
    asset_name = f'Hiddify-Linux-{ASSETS[backend.os.uname().machine]}.AppImage'
    with urllib.request.urlopen(API, timeout=8) as response:
        releases = json.load(response)
    for item in releases:
        tag = item['tag_name']
        if item['draft'] or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
            continue
        for asset in item['assets']:
            digest = asset.get('digest') or ''
            if asset['name'] == asset_name and re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                return tag[1:], asset_name, digest[7:]
    raise RuntimeError('No verified Linux build found')


def available():
    version, name, digest = release()
    current = backend.version()
    if current and subprocess.check_output(['vercmp', version, current], text=True).strip() != '1':
        return None
    return version, name, digest


def install(build):
    version, name, digest = build
    package = 'hiddify-app-bin'
    path = backend.executable()
    if path:
        owner = subprocess.check_output(['pacman', '-Qoq', path], text=True).strip()
        if owner not in ('hiddify', 'hiddify-app-bin', 'hiddify-bin', 'hiddify-next-bin'):
            raise RuntimeError(f'Unsupported Hiddify package: {owner}')
        package = owner
    if backend.running():
        raise RuntimeError('Quit Hiddify from its tray menu, then retry.')
    mode_key = 'flutter.service-mode'
    saved_mode = backend.read_json(backend.PREFS, {}).get(mode_key)
    if saved_mode in ('vpn', 'proxy', 'system-proxy', 'router'):
        print(f'Keeping Hiddify mode: {saved_mode}', flush=True)
    url = f'https://github.com/hiddify/hiddify-app/releases/download/v{version}/{name}'
    with tempfile.TemporaryDirectory(prefix='hiddify-update-') as directory:
        root = pathlib.Path(directory)
        image = root / name
        with urllib.request.urlopen(url, timeout=30) as response, image.open('wb') as output:
            shutil.copyfileobj(response, output)
        with image.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != digest:
                raise RuntimeError('Hiddify download checksum mismatch')
        image.chmod(0o755)
        subprocess.run([image, '--appimage-extract'], cwd=root, check=True, stdout=subprocess.DEVNULL)
        (root / 'launcher').write_text('#!/bin/sh\nexec /opt/hiddify/Hiddify.AppImage "$@"\n')
        (root / 'PKGBUILD').write_text(f"""pkgname={package}
pkgver={version}
pkgrel=1
pkgdesc='Hiddify proxy client'
arch=('{backend.os.uname().machine}')
url='https://github.com/hiddify/hiddify-app'
depends=('gtk3' 'jq' 'hicolor-icon-theme')
options=('!strip' '!debug')
package() {{
    install -Dm755 "$startdir/{name}" "$pkgdir/opt/hiddify/Hiddify.AppImage"
    install -Dm755 "$startdir/launcher" "$pkgdir/usr/bin/hiddify"
    sed 's|^Exec=.*|Exec=/usr/bin/hiddify %U|' "$startdir/squashfs-root/hiddify.desktop" > "$startdir/hiddify.desktop"
    install -Dm644 "$startdir/hiddify.desktop" "$pkgdir/usr/share/applications/hiddify.desktop"
    install -Dm644 "$startdir/squashfs-root/hiddify.png" "$pkgdir/usr/share/icons/hicolor/256x256/apps/hiddify.png"
}}
""")
        env = dict(backend.os.environ, PKGDEST=directory)
        subprocess.run(['makepkg', '--noconfirm'], cwd=root, env=env, check=True)
        artifact, = root.glob('*.pkg.tar.*')
        if backend.running():
            raise RuntimeError('Quit Hiddify from its tray menu, then retry.')
        subprocess.run(['sudo', 'pacman', '-U', str(artifact)], check=True)
    if saved_mode in ('vpn', 'proxy', 'system-proxy', 'router') and not backend.running():
        prefs = backend.read_json(backend.PREFS, {})
        if prefs.get(mode_key) != saved_mode:
            prefs[mode_key] = saved_mode
            backend.save_json(backend.PREFS, prefs)


if __name__ == '__main__':
    try:
        build = available()
        if sys.argv[1:] == ['--check']:
            print(build[0] if build else '')
        elif build:
            install(build)
        else:
            print('Hiddify is up to date.')
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
