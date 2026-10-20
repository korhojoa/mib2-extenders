<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Licenses

| Source | License |
| --- | --- |
| Bundle tools and guides | GPL-3.0-only |
| GAL integration | GPL-3.0-only; shared crates have their own notices |
| DIO integration | See the per-crate licenses in the DIO source |
| `mib2-shared-crates` | MIT OR Apache-2.0 |
| `qnx650-crates` | Apache-2.0 or MIT OR Apache-2.0, as declared by each crate |
| FFmpeg | See the selected FFmpeg build and its notices |

The source bundle keeps each component's license files. The binary bundle
must keep the notices for all linked code. No vendor firmware or SDK is
included. The public compiler image supplies link-only runtime imports; these
are not runtime libraries to install on the unit.
