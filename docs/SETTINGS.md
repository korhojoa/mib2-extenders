<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Settings

The bundle starts with the component example files. The computer preparation
command sets their install locations.
The examples can differ from the code defaults. Read the setting definitions
before changing an existing configuration.

| Component | Configuration | Types, bounds, defaults and meaning |
| --- | --- | --- |
| GAL | `gal-extender/gal_loader.conf`, beside its loader | [GAL settings](https://github.com/korhojoa/gal-extender/blob/main/docs/SETTINGS.md) |
| DIO | `dio-extender/dio_loader.conf`, beside its loader | [DIO settings](https://github.com/korhojoa/dio-extender/blob/main/docs/SETTINGS.md) |
| LSD extender | `lsd-extender/lsd-extender.conf` | [Keys below](#lsd-extender) |
| Shared readers | Paths supplied by the consuming loader | [Shared settings](https://github.com/korhojoa/mib2-shared-crates/blob/main/docs/SETTINGS.md) |
| QNX libraries | No configuration file | [QNX API settings](https://github.com/korhojoa/qnx650-crates/blob/main/docs/SETTINGS.md) |

## LSD extender

The core reads `lsd-extender/lsd-extender.conf` in the chosen install folder.
The computer preparation command sets both receiver configuration paths for
`<INSTALL_FOLDER>`. Keep those prepared values for a portable installation.
The table gives the defaults supplied by this release, before personal changes.

| Key | Release default | Meaning |
| --- | --- | --- |
| `lsdextender.nav.aa` | `true` | Send Android Auto turn and distance updates to the cluster arrows. The code default is false. |
| `lsdextender.nav.turnto` | Empty | Cluster turn-to text. The empty value disables this text; the code default is `{road}`. |
| `lsdextender.nav.turnto.sign` | Empty | Cluster signpost text. The empty value disables this text; the code default is `{sign}`. |
| `lsdextender.restart.enabled` | `false` | Permit the optional restart control. The release does not load the key-input feature that supplies that control. |
| `lsdextender.carplay.config` | `auto` before preparation; `<INSTALL_FOLDER>/dio-extender/dio_loader.conf` after it | Configuration file for the CarPlay settings page. `auto` searches the built-in locations. |
| `lsdextender.androidauto.config` | `<INSTALL_FOLDER>/gal-extender/gal_loader.conf`, added by preparation | Configuration file for the Android Auto settings page. Keep the explicit prepared path. |
| `lsdextender.wireless.bt` | `true` | Watch Bluetooth-connected phones for the wireless device and settings. |
| `lsdextender.wireless.autoconnect` | `false` | Permit automatic Android Auto start requests when a watched phone appears. `false` keeps the normal manual start. |
| `lsdextender.publish.port` | `0` | TCP command listener port. `0` disables the listener; valid enabled ports are 1 through 65535. |
| `lsdextender.publish.pf` | `false` | Open the listener's firewall port when the listener is enabled. Keep `false` for the supplied configuration. |
| `lsdextender.wireless.pf` | `true` | Open TCP 5288 for the wireless bridge. The code default is true. |
| `lsdextender.publish.pf_ifaces` | `$wlan_if` | Restrict firewall openings to the access point uap0. The code default also includes debug and cellular interfaces. |
| `lsdextender.wireless.card_remount` | `true`, code default; omitted from the file | If a wireless settings save fails on a read-only card, briefly remount it writable, save the wireless setting and phone choice, then restore read-only mode. |
| `lsdextender.dsispy.enabled` | `false` | Disable DSI diagnostics. The code default is true; its archive is not loaded. |
| `lsdextender.dsispy.slog` | `false` | Disable extra DSI slog output. |
| `lsdextender.keys.enabled` | `false` | Disable the key-input feature. The code default is true; its archive is not loaded. |
| `lsdextender.input.trace` | `false` | Disable native input queue timing output. |
| `lsdextender.touch.slog` | `false` | Disable continuous touch output. |
| `lsdextender.vehicle_probe.enabled` | `false` | Disable the optional vehicle probe. |
| `lsdextender.vehicle_probe.read_only` | `true` | Keep the optional vehicle probe read-only if enabled. The code default is false; the release leaves the probe disabled. |
| `lsdextender.nav.destination` | `false` | Disable native destination handling. |
| `lsdextender.updates.worker` | `/dev/null` | Disable the updater through its regular-file check. The code default is a hu-agent file beside the configuration. |
| `lsdextender.updates.agent.config` | `/dev/null` | Do not select an update configuration. The code default is hu-agent.json beside the configuration. |
| `lsdextender.games.directory` | `/dev/null` | Supply no game directory. The code default is the headunit folder on the first SD slot. |

Boolean values are `true` or `false`. The `prop` prefix before a key is optional.
If `lsdextender.publish.pf` is omitted, its code default is `true`; the release
sets it explicitly to `false`. Exceptions to code defaults are identified in the table. The listener-port
code default is 0. Receiver settings must keep the prepared file paths.

The file also contains these directives:

| Directive | Function |
| --- | --- |
| `jar FILE` | Load the named feature archive from the configuration folder. |
| `feature CLASS` | Start the named owned feature class. |
| `spawn COMMAND` | Start the listed helper command after startup. |

The supplied archives provide wireless Android Auto, the settings pages,
cluster turn guidance, cluster stream-state feedback and vehicle energy data.
The helpers supply the virtual USB device and the Wi-Fi connection data.
Diagnostic logging features, key input, games audio and native destination
handling stay off.

## Output selection

The two loaders assign different meanings to `cluster_output`.

| Loader | Default | Values |
| --- | --- | --- |
| GAL | 0 | 0 sends video directly through MOST. 2 forwards to the DIO decoder. 1 is not supported and falls back to 0. |
| DIO | -1 | -1 follows the module lines. 0 disables both sinks. 1 selects the direct sink. 2 selects the forwarder. The selected module also needs its bare feature line. |

The supplied GAL example uses direct output. Its `identify_as_dhu=1` presents
the unit to the phone as Google's Desktop Head Unit, an Android Auto
development receiver. Set it to 0 to preserve the native identity.
The supplied DIO example enables `altscreen` and `clustervideo`, with
`cluster_output=2`. See the component Status sections for test limits.

The LSD configuration enables wireless Android Auto and our settings pages.
It leaves the TCP command listener off. The wireless TCP port opening is on,
on the access point interface `uap0` only. Optional features
can need other programs or unit tests. Keep those features off until tested.

Use [INSTALL.md](../INSTALL.md) to keep existing settings during an update.
