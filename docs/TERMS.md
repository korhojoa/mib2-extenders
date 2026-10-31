<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Terms

| Term | Meaning |
| --- | --- |
| MIB2 High | The vehicle infotainment unit supported by this project. |
| Firmware | The unit's installed system software. |
| QNX 6.5 | The operating system on the unit. |
| ARMv7 | The unit's processor type. |
| GAL | The unit process that receives Android Auto from a phone. |
| DIO | The CarPlay receiver, named `dio_manager` on the unit. |
| LSD extender | Our Java core and feature archives for the unit's display and controls. |
| M.I.B. toolkit | Separate software that supplies the unit command shell and file-transfer tools. |
| Root shell | A command shell with administrative access to the unit. |
| MMX | The unit computer that runs the phone receiver processes. |
| HMI | The unit software that draws screens and handles input. |
| J9 | The unit's Java virtual machine, which runs the HMI. |
| Java archive (JAR) | A file that contains compiled Java classes and their resources. |
| Stock | The unit's original software. |
| Tile | A small panel on the HOME screen. Its header is the strip at its upper edge. |
| Content-selection list | The HOME control that selects which application a tile shows. |
| Loader | A library loaded into a receiver to add selected functions. |
| Native library | A compiled library that a unit process loads. Its filename usually ends in `.so`. |
| `LD_PRELOAD` | The environment variable that selects libraries to load before a process starts. |
| `LD_LIBRARY_PATH` | The environment variable that lists folders to search for library dependencies. |
| Bluetooth wrapper | Our script that starts the original Bluetooth program with the wireless library. |
| TCP | A network transport used for phone data and the optional command listener. |
| RFCOMM | A Bluetooth serial channel used for wireless Android Auto setup. |
| Virtual USB driver | A program that presents a USB device without a physical cable. |
| PPS | QNX Publish/Subscribe objects used to share state between programs. |
| DSI | The stock device service interface used for state and control. |
| Hotspot (access point) | The unit's Wi-Fi network that the phone joins. |
| WPA2 passphrase | The original Wi-Fi password, from which a key is derived. |
| SSID | The Wi-Fi network name. |
| BSSID | The access point's radio address. |
| `uap0` | The unit's Wi-Fi access point network interface. |
| `uaputl` | The unit command that reads and configures its Wi-Fi access point. |
| `ifconfig` | The unit command that reports network interface addresses. |
| RAM | Temporary memory whose contents are lost at restart. |
| JSON | A structured text format used by the phone configuration. |
| Decoder | A program that converts compressed video into display frames. |
| FFmpeg | The video decoding software used by the decoder. |
| MOST | The media network used for direct instrument-cluster video. |
| EXLAP | The unit protocol for named vehicle measurements. |
| SHA256 | A file checksum used to detect different file contents. |
| Submodule | A separate Git repository fixed at one selected commit. |
| Container | An isolated environment that runs build tools on the computer. |

[README](../README.md)
