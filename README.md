# Hiddify for Omarchy

[Русский](README.ru.md) · English

A Hiddify control panel for the Omarchy Quickshell bar. Connect or disconnect, import subscriptions, choose servers and edit 91 settings from one panel.

![Hiddify panel preview](preview.png)

## Features

- Live connection switch and tray status.
- HTTPS subscription import and refresh, validated by the installed Hiddify CLI.
- Active-profile selection, server selection and latency tests.
- Searchable settings for DNS, TUN, ports, routing, TLS fragmentation, WARP, Psiphon and the app.
- Private backups before settings/profile writes and a restore action.
- Russian and English labels, options, plural forms, numbers and dates.
- Automatic Hiddify installation when missing, using Omarchy's package manager in a visible terminal.
- Quiet background refresh: stable controls and preserved settings scroll position.

## Install

Requires Omarchy Quattro, Python 3 and Hiddify **5.5.5** for native settings/profile writes. The shipped core bridge targets Linux x86_64. Hiddify itself is installed separately through the package manager; its runtime is not bundled in this repository.

```bash
omarchy plugin add https://github.com/AmirAdelevich/omarchy-hiddify --enable
```

The plugin ID is `msi.hiddify`. Left-click its bar icon to open the panel; right-click to hide the Hiddify window. Use Open app to restore it and the panel switch to toggle the connection. Missing Hiddify is installed through `omarchy pkg add hiddify`, with `omarchy pkg aur add hiddify` as a fallback. Enter any requested password in the installer terminal. Installing from AUR follows the usual AUR build process.

## Update

Select **Update extension** on the panel’s Home tab. On devices with an older version, run:

```bash
omarchy plugin update msi.hiddify --yes
```

## Language

The plugin follows the live language selected in **Omarchy Setup → Language**. If no Omarchy language has been selected, it uses `LC_ALL`, `LC_MESSAGES`, `LANGUAGE`, then `LANG`. Russian locales select Russian; English and other locales use English. No shell restart is required when changing the Omarchy language.

All 91 preference labels and supported choice labels have Russian and English text. Technical keys, protocol names and user-supplied server/profile names remain as entered.

## Data changes and compatibility

The native adapter targets Hiddify **5.5.5**, matching its preference names and profile database schema. Writes are disabled for other versions; opening the native app remains available.

**Apply, subscription import/refresh, profile activation and restore close Hiddify gracefully and restart it. The VPN can disconnect.** Each button identifies this behavior. A backup is made before a write, and writing is refused while the GUI still runs. Other preferences are preserved, and conflicting edits made in Hiddify are detected.

Advanced routing rules, full logs and system autostart are accessed through the native Hiddify pages. This widget does not replace every native app screen. WARP's structured settings are JSON strings; per-app lists use `;` separators.

## Network, credentials and dependencies

Runtime dependencies: Omarchy Quickshell and its `qs.Ui`/`qs.Commons` components, Python 3 standard library, Hiddify and its HiddifyCli, and the usual Omarchy package-management tools. The Go bridge is included with source and pinned build dependencies in `corebridge/go.mod` and `corebridge/go.sum`.

External requests occur on installation, explicit subscription import/refresh, or explicit latency tests. HTTPS subscriptions are limited to 8 MB; HTTP redirects are refused and download/parser timeouts are applied. Hiddify performs latency checks through its configured test destination. Local state is refreshed every five seconds while the panel is open.

Server controls use Hiddify's local background core at `127.0.0.1:18020` and its existing `/var/lib/hiddify-admin-bgservice/control.secret`. This credential is read locally, never logged or uploaded. A local Clash API is used as a fallback if its token is available. Credentials are never forwarded through an HTTP proxy or redirect. The native server page remains available when neither API can be used.

Hiddify data is under `$XDG_DATA_HOME/app.hiddify.com/` (default `~/.local/share/app.hiddify.com/`). Private backups and staged imports are under `$XDG_STATE_HOME/omarchy-hiddify/` (default `~/.local/state/omarchy-hiddify/`), with private directory/file permissions. Subscription URLs are sent to the adapter on stdin, not process arguments.

## Disable or remove

```bash
omarchy plugin disable msi.hiddify
omarchy plugin remove msi.hiddify
```

Removing the plugin preserves Hiddify, its subscriptions/settings and the backups. Hiddify remains usable through its native app. Backups can be removed separately from the state directory when no longer needed.

## IPC

```bash
omarchy-shell msi.hiddify open
omarchy-shell msi.hiddify close
omarchy-shell msi.hiddify page subscriptions
omarchy-shell msi.hiddify page settings
omarchy-shell msi.hiddify page servers
omarchy-shell msi.hiddify status
```

## Build and test

```bash
python -m unittest discover -s . -p test_backend.py
node test.cjs
(cd corebridge && go test ./... && go build -trimpath -ldflags='-s -w' -o ../corebridge-bin .)
omarchy plugin validate .
```

Go 1.27.3 or later is required to rebuild the bridge. Write/import tests use temporary databases and fixtures and never change the real VPN connection. Package installation is tested with stub commands.

## License and attribution

Plugin code: [MIT](LICENSE). Go dependency licenses are in [licenses/](licenses/). This is an independent integration for [Hiddify](https://github.com/hiddify/hiddify-app) and [Omarchy](https://github.com/omacom/omarchy), not an official Hiddify or Omarchy release.

Preference keys and supported values were checked against Hiddify app v5.5.5; local gRPC message fields follow hiddify-core's `v2/hcore/hcore.proto`. The adapter and its labels are implemented in this repository. No Hiddify application or core source is compiled into the bridge: the bridge uses the local protocol to communicate with the separately installed application. The supplied preview is a screenshot of this plugin.
