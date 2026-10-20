<!-- SPDX-License-Identifier: GPL-3.0-only -->
# MIB2 extenders

Build one install bundle for the Android Auto and CarPlay extensions on a
QNX 6.5 ARMv7 MIB2 High unit. The bundle contains matching native libraries,
configuration examples, a video decoder, a SHA256 file checksum command,
license notices and the corresponding public source.

See [Terms](docs/TERMS.md) for the technical names and
[Settings](docs/SETTINGS.md) for configuration files and values.

| Part | Function |
| --- | --- |
| [GAL](gal-extender/README.md) | Extend the Android Auto receiver. |
| [DIO](dio-extender/README.md) | Extend the CarPlay receiver. |
| Shared Rust crates | Supply video, settings and file checksum code. |
| QNX runtime crates | Supply native runtime interfaces. |

The shared repositories are pinned dependencies of both extenders. The
bundle contains no unit firmware or development kit.

## Included features

- Android Auto map video on the instrument cluster, the display behind the
  steering wheel, through GAL.
- A CarPlay receiver, forwarder and decoder for cluster video. This path has
  startup tests only, not a unit display result.
- Vehicle sensor data for Android Auto through the optional GAL `sensor`
  feature. The supplied GAL configuration enables this feature.
- Optional GAL input controls, a settings menu, wireless transport, a data
  uplink and a command launcher. These features are off in the bundle example
  and do not have test results for this bundle on a MIB2 High unit.
- Optional DIO direct video output, map zoom, vehicle-data tools and video
  replay tools. These features are off in the bundle example. The standalone
  tools are available in the component source, not in the install folders.
  Their operation on a MIB2 High unit remains untested for this bundle.

## Status

Tested on a MIB2 High unit, firmware MHI2_ER_VWG13_P4512_2, 2026-10-20.

The GAL cluster map appeared on the first connection with no stream write
errors. Native navigation returned after disconnect. The GAL sensor feature
can send battery level from EXLAP. Other sensor mappings remain unqualified.
The DIO loader, receiver, forwarder and decoder passed Pi startup checks.
That test does not prove CarPlay pictures on an instrument cluster.

The manual installation command set has not run on an emulated or physical
unit. It is an unqualified manual procedure. Read the component Status
sections before selecting a feature.

## Use a prebuilt bundle

If you downloaded a release ZIP, extract it into an empty folder. Skip the
source and build sections below and follow [INSTALL.md](INSTALL.md).
The build scripts belong to the Git source checkout; they are not required
or included in the prebuilt ZIP.

## Get the source

```sh
git clone --recurse-submodules https://github.com/korhojoa/mib2-extenders.git
cd mib2-extenders
```

Keep the selected submodule commits. Every build checks that all component
and shared dependency checkouts match those commits and have no source edits.

## Build the bundle

Install Python 3.11 or later and Podman. The following commands
fetch the locked dependencies and build in the pinned public QNX compiler
image. No unit files or QNX development kit are required.

```sh
python3 -B scripts/build-release.py --fetch
python3 -B scripts/build-release.py
```

The first build also downloads and verifies the FFmpeg source. Generated
files stay under `build`. The output is `build/mib2-extenders.zip`. Its
`RELEASE.json` records the selected component commits and payload hashes.
Its `SHA256SUMS` covers the archive files. Both lists are generated during
the build. The workflow runs the same build and package tests.

To run the package tests separately:

```sh
python3 -B scripts/test-bundle.py
```

## Install

Follow [the manual install guide](INSTALL.md). Copy the selected extender
folders to one install folder of your choice. Configure each selected phone
process to preload its own loader. Keep every existing preload and unrelated
configuration value. Configuration files are copied before libraries.

The build command does not connect to a unit or install software. An automatic
installer is not supplied. Keep the original unit configuration for recovery.

## License

The bundle tools and guide use GPL-3.0-only. Each component and dependency
keeps its own license. See [COPYING](COPYING) and [LICENSES.md](LICENSES.md).
