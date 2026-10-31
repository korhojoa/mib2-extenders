<!-- SPDX-License-Identifier: GPL-3.0-only -->
# MIB2 extenders

This bundle adds Android Auto and CarPlay extensions to a QNX 6.5 ARMv7
MIB2 High unit. It includes wireless Android Auto and an independent settings
page. The Android Auto extensions require a licensed Android Auto receiver.
The CarPlay extensions require a licensed CarPlay receiver.
The Java archives contain our feature classes and their release metadata.

| Part | Function |
| --- | --- |
| GAL | Extend the Android Auto receiver and send its map to the cluster. |
| DIO | Extend the CarPlay receiver and receive its cluster video stream. |
| LSD extender | Load our Java features and supply owned settings pages. |
| Wireless Android Auto | Use the stock Bluetooth stack and a virtual USB connection. |
| devu-vaa | Supply the virtual USB driver. |
| android-auto-settings | Read and save the Android Auto settings. |

See [INSTALL.md](INSTALL.md) for installation and removal.
[Terms](docs/TERMS.md) explains the technical names.
[Settings](docs/SETTINGS.md) describes the configuration files.

## Status

Android Auto and wireless Android Auto worked on a MIB2 High unit with
firmware MHI2_ER_VWG13_P4512_2 on 2026-10-30. Bluetooth calls worked during
wireless projection. CarPlay cluster display is not verified with this release.
A cluster map that is already stuck can remain stuck after projection ends.

## Build

Install Git, Python 3.11 or later and Podman. Get the source:

```sh
git clone https://github.com/korhojoa/mib2-extenders.git
cd mib2-extenders
```

The build needs network access for pinned source, Cargo dependencies, FFmpeg
and the Java compiler. Fetch the pinned compiler image, then build:

```sh
podman pull ghcr.io/korhojoa/qnx650-compiler@sha256:85f95b995d4b5dc2c323a6842c29b5c08652f34cc2288f6cc745534f5b2ecc7a
python3 -B scripts/build-release.py build
```

Output: `build/release/mib2-extenders.zip`.

## Configuration

GAL and DIO read their configuration next to their loaded libraries.
The supplied LSD configuration enables wireless Android Auto and the owned
settings backend. It also loads cluster guidance, stream-state feedback and
vehicle energy data. See [LSD extender settings](docs/SETTINGS.md#lsd-extender)
for its configuration keys and defaults. Diagnostic logging features, the key
feed and the TCP command listener are off. The wireless TCP port opening is
on, on the access point interface `uap0` only. Optional code remains in the
source and archives; some off features require programs not included here.

Keep untested optional features off. Read the component README files before
you enable a new feature. A build result alone does not qualify unit behavior.

## License

The bundle tools and guide use GPL-3.0-only. Each component retains its own
license. See [COPYING](COPYING), [LICENSES.md](LICENSES.md) and the license files
in each component source folder.
