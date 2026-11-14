### Repository URL

https://github.com/AmirAdelevich/omarchy-hiddify

### Category

Widgets

### Tags

vpn, bar, quickshell

### Suggest a missing tag

_No response_

### Maintainer notes

Hiddify control panel with Russian/English language selection, subscription import/refresh, explicit connection action, four native quick modes, Open app / Minimize actions, hourly version checks with release labels and one notification per version, local server selection and latency tests, 86 settings, and private backups/restore. The English promotional preview is preview.png in the repository root. Its example profile contains no private server address or name.

Native writes require a verified Hiddify version and v7 profile schema. The catalog is verified against 5.9.2. Complete snapshots and a recovery journal cover multi-file writes. Writes are explicit UI actions, close the app gracefully, create backups and restart it; the VPN can disconnect. The plugin automatically launches an official-release package installer in a visible terminal when Hiddify is missing. It has no custom sudoers rules.

The repository includes the source and Linux x86_64 build of a small Go gRPC bridge. The bridge connects only to Hiddify's local background service using its existing control.secret; credentials are not logged or uploaded. The established server socket must be owned by root before any gRPC authorization metadata is sent. HTTP fallback verifies the connected peer as root or the current user before sending its token. All Go dependencies are pinned and their licenses are included. Explicit updates install a local Arch package from the official GitHub AppImage after SHA-256 verification, including numbered pre-releases. Hiddify itself is not bundled. Runtime dependencies and the install/removal/data behavior are documented in README.md.

### Submission checklist

- [x] The repository is public and contains installation and removal instructions.
- [x] I have documented the plugin license and any external dependencies.
- [x] I confirm that I own or have permission to submit this plugin and its preview assets.
- [x] The plugin does not overwrite user configuration without explicit consent.
- [x] I understand that approval is for listing and is not a security review.
