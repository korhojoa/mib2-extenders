<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Settings

The bundle uses the component example files without changing their values.
The examples can differ from the code defaults. Read the setting definitions
before changing an existing configuration.

| Component | Configuration | Types, bounds, defaults and meaning |
| --- | --- | --- |
| GAL | `gal-extender/gal_loader.conf`, beside its loader | [GAL settings](https://github.com/korhojoa/gal-extender/blob/main/docs/SETTINGS.md) |
| DIO | `dio-extender/dio_loader.conf`, beside its loader | [DIO settings](https://github.com/korhojoa/dio-extender/blob/main/docs/SETTINGS.md) |
| Shared readers | Paths supplied by the consuming loader | [Shared settings](https://github.com/korhojoa/mib2-shared-crates/blob/main/docs/SETTINGS.md) |
| QNX libraries | No configuration file | [QNX API settings](https://github.com/korhojoa/qnx650-crates/blob/main/docs/SETTINGS.md) |

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

The navigation guidance decoder is disabled and needs correction. Parked
wireless and vendor-channel features need programs that are not released.
They are not enabled by these install steps.

Use [INSTALL.md](../INSTALL.md) to keep existing settings during an update.
