<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Install and remove the extensions

## Before you start

This release supplies GAL, DIO, LSD extender and wireless Android Auto.
Each extension needs its corresponding licensed receiver: Android Auto for
the Android Auto extensions, and CarPlay for the CarPlay extensions. Check
that the receiver you will use works with a cable.
It supplies no firmware or stock program. The cluster map can fail to return
from an already faulty cluster state. Keep a working recovery method.

Install a compatible [M.I.B. toolkit](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash#readme)
first. Follow its instructions for the MMX command shell and file transfer.
MMX is the unit computer that runs the phone receivers. Keep a complete
backup. Do not use startup files from a different unit or firmware.

Extract the release ZIP on a computer with Python 3.11 or later. Open a
terminal in the extracted folder. Check all files. On Linux, use:

```sh
sha256sum -c SHA256SUMS
```

On macOS, use:

```sh
shasum -a 256 -c SHA256SUMS
```

Stop unless every file reports OK. Keep the complete extracted release.

Choose one writable storage folder. Replace `<INSTALL_FOLDER>` everywhere
below with its absolute path, without the brackets. Use only letters,
digits, slashes, periods, underscores and hyphens. Do not use spaces or
colons. The folder must be available before the phone receivers start.
Keep removable storage connected. Do not format or replace toolkit files.

These steps are for a first install. If the unit already has an extension,
keep its settings and existing startup changes. Do not replace them with
these examples. Compare the changes before an update.

## Prepare files on the computer

Copy these two current files from the unit to the computer:

- `/mnt/app/eso/hmi/lsd/lsd.sh`
- `/etc/eso/production/smartphone_integrator.json`

Keep unchanged copies outside the release folder. They are your recovery
files. Do not publish them. Keep their original file modes too.

Run this command on the computer with your copy of `lsd.sh`:

```sh
python3 scripts/prepare-install.py --launcher lsd.sh --install-folder <INSTALL_FOLDER> --output prepared
```

The output folder must not exist. This command changes no unit file.
It supplies a configured `prepared/card` tree and `prepared/lsd.sh.prepared`.
The latter adds our Java startup block before the unchanged native Java
launch line. The tool refuses a launcher that already has that extension.
It changes only text configuration; native libraries stay unchanged.
Check `prepared/SHA256SUMS` from inside the prepared folder with the same
checksum command. Review the startup diff on the computer:

```sh
diff -u lsd.sh prepared/lsd.sh.prepared
```

In a working copy of `smartphone_integrator.json`, find `children.gal` and
`children.carplay`. Their executables must be `gal` and `dio_manager`.
Add this string to the GAL child's `envs` array:

```json
"LD_PRELOAD=<INSTALL_FOLDER>/gal-extender/libgal_loader.so"
```

Add this string to the CarPlay child's `envs` array:

```json
"LD_PRELOAD=<INSTALL_FOLDER>/dio-extender/libdio_loader.so"
```

These are separate child environments. Do not set a global preload. If the
child already has LD_PRELOAD, append the new path with a colon. Keep the
existing value, arguments and all other children. Do not add a duplicate
variable. Keep the original comment syntax. Review the exact diff.
Save the changed copy as `smartphone_integrator.json.prepared`.

Read `docs/SETTINGS.md` before you change the supplied configuration.
The GAL configuration enables its direct cluster output. The DIO example
uses its video receiver and decoder; startup tests do not prove a CarPlay
cluster picture. The LSD configuration enables wireless Android Auto and
our settings pages. The TCP command listener is off. The wireless TCP port
opening is on, on the access point interface uap0 only.
Do not enable other features only because they built.

## Copy the prepared files

Open the toolkit's MMX command shell before the transfer. Keep this shell
open for the following installation commands. Run `mount` to find the storage
mount that contains `<INSTALL_FOLDER>`. Replace `<STORAGE_MOUNT>` below with
that mount point. A mount listing does not show its write access on all units.
Check write access with the shell instead:

```sh
mount
storage_mount="<STORAGE_MOUNT>"
for p in "$storage_mount" /mnt/app /mnt/system; do
    if [ -w "$p" ]; then echo "$p writable"; else echo "$p not writable"; fi
done
```

Record all three results. In this root shell, a not-writable result requires
a writable remount before writes. Make only the install storage writable now,
and omit this command if it was already writable:

```sh
mount -uw "$storage_mount"
```

Run the write-access check again. Stop if the storage is still not writable.
Keep the recorded original state. Restore it on success and on error.

For a first install, the component folders must not exist on the unit.
Copy the contents of `prepared/card` into `<INSTALL_FOLDER>`. Do not copy
the `card` folder itself. Keep file modes. Copy text configuration first,
then the matching libraries and programs. The component folders are:

- `gal-extender`
- `dio-extender`
- `lsd-extender`
- `mib2-extenders`

Create `<INSTALL_FOLDER>/prepared` through the toolkit's file transfer.
Copy `lsd.sh.prepared` and `smartphone_integrator.json.prepared` there.
No stock startup file is changed by this transfer.

## Install the startup files

Continue in the same MMX command shell. Run one command at a time. Stop at
an error. Use the write-access results recorded above for `/mnt/app` and
`/mnt/system`. Stop if these are not the toolkit's application and system
mounts. Do not infer their state from missing flags in the mount listing.

```sh
cd "<INSTALL_FOLDER>"
launcher=/mnt/app/eso/hmi/lsd/lsd.sh
config=/etc/eso/production/smartphone_integrator.json
mkdir original-startup
cp "$launcher" original-startup/lsd.sh
cp "$config" original-startup/smartphone_integrator.json
sync
./mib2-extenders/file-checksum "$launcher" original-startup/lsd.sh
./mib2-extenders/file-checksum "$config" original-startup/smartphone_integrator.json
/bin/sh -n prepared/lsd.sh.prepared
LD_LIBRARY_PATH=/eso/lib:$LD_LIBRARY_PATH /eso/bin/jsonlint --file prepared/smartphone_integrator.json.prepared
```

The backup folder must not exist before mkdir. Keep it unchanged after
installation. Each checksum command prints two hashes. They must be equal.
An exit status of zero means the files were read; it does not compare them.
Stop if either syntax check fails.

Make each read-only mount writable. Omit a command if that mount was
already writable:

```sh
mount -uw /mnt/app
mount -uw /mnt/system
```

Install the two prepared files, then check their contents:

```sh
cp prepared/lsd.sh.prepared "$launcher"
cp prepared/smartphone_integrator.json.prepared "$config"
sync
./mib2-extenders/file-checksum prepared/lsd.sh.prepared "$launcher"
./mib2-extenders/file-checksum prepared/smartphone_integrator.json.prepared "$config"
```

The hashes in each pair must be equal. Restore each mount to its original
mode. Run only the commands for mounts that were originally read-only:

```sh
mount -ur /mnt/system
mount -ur /mnt/app
```

If a copy or comparison fails, restore both saved startup files before a
restart. Use the removal commands below and restore the mount modes.

## Install the wireless Bluetooth wrapper

Wireless Android Auto uses the unit's existing Bluetooth stack. The kit
installs our wrapper at `/eso/bin/PhoneCustomer/btstack`. It leaves the
vendor executable unchanged. It copies the card library into RAM at each
Bluetooth start, so a later card update can replace the card file.

Run this command only for a fresh installation with no existing customer
wrapper:

```sh
sh "<INSTALL_FOLDER>/lsd-extender/native-aa-kit/install.sh"
```

Require `Installed wrapper; read-only remount succeeded. No service was started.`
The kit manages its application remount and returns it to read-only mode.
If a wrapper already exists, run `remove.sh` from the kit that installed it
first. Use the removal command in this guide when the existing wrapper came
from this same kit. Require successful removal before you run `install.sh`
again. An unknown customer executable must stay unchanged; stop if the removal
script refuses it.

After all storage writes, flush them. Restore the storage mount to read-only
only if its original result was not writable:

```sh
sync
mount -ur "$storage_mount"
```

Repeat the write-access check. Require the original results for all three
mounts. Restore these states on an error too, before a restart.

Restart the unit through its usual control. The new Java startup block and
Bluetooth wrapper require this restart. Check the stock main screen and
normal wired projection first. In the MMX shell, read the system log:

```sh
/bin/sloginfo
```

Find these exact message prefixes for the new boot and receiver process:

```text
[GalLoader] loader 1.4.2+1
lsd-extender-core 2.3.2+522
native-aa-btstack-wrapper version=1.0.6 decision=loaded
```

The core line continues with its build information. The Bluetooth library
must also log `kind=aa_diagnostics build=0.1.11+1` and
`AA service published on factory RFCOMM channel`. A missing line or a load
error is not a successful install.

First pair the phone with the unit through the normal Bluetooth menu.
Open the HOME screen. In a tile's content-selection list, select **Extender settings**.
Tap that tile's header to open **Extender menu**, then select **Android Auto**.
Open **Wireless connection**. Turn **Wireless Android Auto** on and allow
the paired phone there.
The settings save briefly makes a read-only card writable when needed, then
restores its read-only mode.

The unit's Wi-Fi hotspot must already work. Set its network name and WPA2
passphrase in the unit's normal Wi-Fi settings. The credential program reads
missing network data from the active `uap0` hotspot with `uaputl` and
`ifconfig`. It needs the original passphrase, not a derived 64-character key.

Before hotspot detection, the program reads any `AAWG_*` variables supplied
by its launcher's process environment. In a new installation, the launcher
inherits that environment from the HMI Java process. This guide sets no
passphrase override. A fresh installation on firmware that returns only a
derived key is not supported in this release. Do not erase an existing
credential override when you update a working installation.

Start Android Auto on the paired phone without a cable. A complete Wi-Fi
configuration, an incoming native AA channel and projection are separate
checks. Do not infer projection from a service-published line alone.
Bluetooth calls must still work.

## Remove the extensions

End projection through the stock controls. Use the same storage folder.
Remove only the wrapper installed by this kit:

```sh
sh "<INSTALL_FOLDER>/lsd-extender/native-aa-kit/remove.sh"
```

Require its successful removal and read-only restoration. It refuses an
unknown customer executable. Keep all files if it reports an error.

Before the next commands, compare the current startup files with your
installed prepared files. Restore the saved originals only if no later
change would be lost. Otherwise remove only our preload paths and Java
startup block from copies of the current files, validate those copies and
use them instead. Preserve other programs and settings.

```sh
cd "<INSTALL_FOLDER>"
./mib2-extenders/file-checksum prepared/lsd.sh.prepared /mnt/app/eso/hmi/lsd/lsd.sh
./mib2-extenders/file-checksum prepared/smartphone_integrator.json.prepared /etc/eso/production/smartphone_integrator.json
```

If both pairs match, read `mount` and repeat the write-access check above.
Make only not-writable application and system mounts writable:

```sh
mount
mount -uw /mnt/app
mount -uw /mnt/system
cp original-startup/lsd.sh /mnt/app/eso/hmi/lsd/lsd.sh
cp original-startup/smartphone_integrator.json /etc/eso/production/smartphone_integrator.json
sync
./mib2-extenders/file-checksum original-startup/lsd.sh /mnt/app/eso/hmi/lsd/lsd.sh
./mib2-extenders/file-checksum original-startup/smartphone_integrator.json /etc/eso/production/smartphone_integrator.json
mount -ur /mnt/system
mount -ur /mnt/app
```

Omit each remount that is not needed, and restore the original mount modes.
Compare each printed hash pair. Stop if they differ. Restart through the
usual control. Check stock startup and wired projection before you remove
only the four owned component folders through the toolkit's file transfer.
Repeat the storage write-access check, writable remount if necessary, and
original-state restoration around that removal. Keep the toolkit, media, maps and
recovery copies. Removing storage alone is not an uninstall.
