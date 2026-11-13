### Repository URL

https://github.com/AmirAdelevich/omarchy-hiddify

### Category

Widgets

### Tags

vpn, bar, quickshell

### Suggest a missing tag

_No response_

### Maintainer notes

Hiddify control panel with Russian/English language selection, subscription import/refresh, connection switch, local server selection and latency tests, 91 settings, and private backups/restore. The preview is preview.png in the repository root.

Native settings/profile writes target Hiddify 5.5.5 and are blocked for other versions. Writes are explicit UI actions, close the app gracefully, create backups and restart it; the VPN can disconnect. The plugin automatically launches an Omarchy package-manager installer in a visible terminal when Hiddify is missing. It has no custom sudoers rules.

The repository includes the source and Linux x86_64 build of a small Go gRPC bridge. The bridge connects only to Hiddify's local background service using its existing control.secret; credentials are not logged or uploaded. All Go dependencies are pinned and their licenses are included. Hiddify itself is not bundled. Runtime dependencies and the install/removal/data behavior are documented in README.md.

### Submission checklist

- [x] The repository is public and contains installation and removal instructions.
- [x] I have documented the plugin license and any external dependencies.
- [x] I confirm that I own or have permission to submit this plugin and its preview assets.
- [x] The plugin does not overwrite user configuration without explicit consent.
- [x] I understand that approval is for listing and is not a security review.
