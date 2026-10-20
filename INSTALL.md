<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Manual installation

## Scope

This guide installs the GAL and DIO native extensions on a MIB2 High unit.
Android Auto or CarPlay must already be licensed and working. This bundle
does not add a license, remove component protection or update firmware.

GAL extends the Android Auto receiver. DIO extends the CarPlay receiver.
See the [Terms](docs/TERMS.md) for the process and build names.
Install either part or both. Keep the stock main projection path. The bundle
contains no firmware or unit libraries.

The two shared source repositories supply runtime interfaces, video code,
settings code and the file checksum command. They are build dependencies;
do not copy their source directories into a unit system directory.

## Status

The GAL map test and the DIO Pi startup checks are described in
[the release status](README.md#status). The install command set below has
not run on an emulated or physical unit. It remains an unqualified manual
procedure. A successful build or startup banner does not qualify these
startup-file changes. No automatic installer is supplied.

## Requirements

Start with the stock unit files. Save its firmware version, a complete backup
and a working recovery method. First install a compatible M.I.B. toolkit from
its [upstream instructions](https://github.com/Mr-MIBonk/M.I.B._More-Incredible-Bash#readme).
The toolkit and its credentials are not in this bundle. Check its engineering
menu, MMX command shell and file-copy method before you change startup
configuration. MMX is the computer that runs the phone receivers.

Use a computer with OpenSSH, Python 3 and an archive tool. Keep the complete
release on that computer. Extract the ZIP into an empty folder, then open a
terminal in the extracted folder that contains `SHA256SUMS`, `README.md` and
`card`. Verify all files before preparation.

On Linux, run:

```sh
sha256sum -c SHA256SUMS
```

On macOS, run:

```sh
shasum -a 256 -c SHA256SUMS
```

Every entry must report `OK`; stop on a missing file or checksum error.
These commands run on the computer. The bundled `file-checksum` binary runs
only on the QNX ARM unit. Do not combine files from different releases.

Choose one writable install folder on an SD card, a USB drive or internal
storage. Keep removable storage connected before the unit starts. The toolkit
must mount that storage before it starts either phone receiver. Storage that
you connect after Android Auto or CarPlay starts cannot supply the loader. Use the same folder throughout this guide. Replace the single
placeholder `<INSTALL_FOLDER>` with that folder's absolute path, including
in the two JSON examples. Do not include the placeholder brackets. The folder
can be on either SD slot, USB storage or internal storage. Use the toolkit
startup instructions to check its mount order before you enable the preload. Do not format or replace toolkit files.
Use only letters, digits, slashes, hyphens, underscores and periods in this
folder name. Spaces and colons cannot be used in a preload path.

## Prepare the configuration

Copy the unit's current `/etc/eso/production/smartphone_integrator.json` to
the computer. Save a second, unchanged copy outside every public repository.
Do not use a file from another unit or firmware.

The file uses JSON, a structured text format for configuration.
In a working copy, find `children.gal` and `children.carplay`. Confirm that
their executables are `gal` and `dio_manager`. In each selected child's
`envs` array, add the corresponding string:

```json
"LD_PRELOAD=<INSTALL_FOLDER>/gal-extender/libgal_loader.so"
```

```json
"LD_PRELOAD=<INSTALL_FOLDER>/dio-extender/libdio_loader.so"
```

`LD_PRELOAD` tells the operating system which libraries to load before a
process starts. These are separate child environments. Do not set a global
preload. Keep the arguments, working directories, other children and all existing environment
values. If a selected child already has `LD_PRELOAD`, append the extender path
to its existing value with a colon. Do not add a second variable or discard
the existing preload. Do not apply a loader to the toolkit shell or Bluetooth
process. Review the exact diff before copying the edited file.

Keep the file's original comment syntax. Validate it with the unit's own
framework parser before installation: the `/eso/bin/jsonlint` command in
the unit command set below checks the prepared file on the unit. Stop if it
reports an error. A generic JSON parser on a computer is not a substitute. Do not change the launcher for the HMI, which
draws screens and handles input.

Review the supplied `gal_loader.conf` and `dio_loader.conf` on the computer.
Use [Settings](docs/SETTINGS.md) for component keys, defaults and limits.

The bundle copies each component's `examples` configuration without changes.
These same files are documented in each component README.

The supplied GAL file enables Android Auto cluster video with the whole-line
flag `cluster` and vehicle sensor data with `sensor`. It uses direct cluster
video output (`cluster_output=0`) and presents the unit to the phone as Google's Desktop Head Unit
(`identify_as_dhu=1`), an Android Auto development receiver. Electric-vehicle model sending remains off. Remove a
flag or put `#` before it to disable that feature. Set `identify_as_dhu=0`
if you do not want the development receiver identity.

The supplied DIO file enables CarPlay cluster video: the whole-line
`altscreen` flag receives the phone stream, `clustervideo` forwards it, and
`cluster_output=2` selects the decoder. The direct `cluster` module remains
commented out. To disable the decoder path, comment out `altscreen` and
`clustervideo` and set `cluster_output=0`. The example sets `cp_suppress_navigation_active=1` to filter the phone
navigation-active flag before the native receiver handles it. Set it to `0`
to leave that flag unchanged. These exact components passed Pi startup checks only. They still need
CarPlay display tests on a MIB2 High unit. Do not enable
other features only because their libraries built successfully.

## Copy the bundle files

The bundle's `card` directory contains this layout:

```text
card/
  gal-extender/
    libgal_loader.so
    gal_loader.conf
  dio-extender/
    libdio_loader.so
    libdio_altscreen.so
    libdio_clustervideo.so
    cluster-video
    dio_loader.conf
  mib2-extenders/
    file-checksum
```

Use `RELEASE.json` for the complete file list and its SHA256 checksums.
For a first install, the selected extender directories must not exist. If they exist, stop and
inspect the previous install. Do not replace saved settings with a sample.
For an update, keep all existing settings, including keys that you do not
recognize. Do not replace an existing configuration with the supplied example.

Copy the prepared extender configuration files first. Then copy the matching
libraries, decoder and checksum command. Copy the contents
of `card` into the chosen install folder, not the `card` directory itself.
Keep the executable modes. Omit an unused extender directory and its preload
edit together. Keep `mib2-extenders/file-checksum` for either install.

Make a `mib2-extenders-prepared` directory in the install folder. Copy the
edited phone configuration into it as `smartphone_integrator.json`. This
private file must not enter a public repository or release. Keep its original
copy on the computer and in the unit-side backup made below.

## Unit command set

Run these commands from the toolkit's MMX command shell, one at a time.
Stop at any error. The install folder must already be writable. Record the configuration
filesystem's original mount mode before any remount. The commands below use
`/mnt/system` for that filesystem. Run `mount` without arguments in the
unit shell to list mounted filesystems and their read-only or writable modes:

```sh
mount
```

Check that `/mnt/system` is the system mount used by the toolkit for the
configuration file. If that mount is absent or the toolkit uses another
layout, stop: do not run the remount commands for a different filesystem.

```sh
# Select the one install folder and name the files.
cd "<INSTALL_FOLDER>"
config=/etc/eso/production/smartphone_integrator.json
prepared=mib2-extenders-prepared/smartphone_integrator.json
# Check the shipped command before a startup-file change.
./mib2-extenders/file-checksum --help
```

### First install: save the original

Run this block only for the first install. An existing original-backup
folder is an error: keep it unchanged and use the update procedure instead.

```sh
backup_dir=mib2-extenders-original
mkdir "$backup_dir"
backup="$backup_dir/smartphone_integrator.json"
cp "$config" "$backup"
sync
```

### Update: save the currently installed configuration

Keep `mib2-extenders-original` unchanged. Start from the current unit
configuration and preserve every existing feature setting and unrelated
value. Save a new dated backup before each update. If the directory name
already exists, stop and choose a different time; never reuse a backup.

On the computer, print the dated assignment with its standard `date` tool:

```text
date '+backup_dir=mib2-extenders-update-%Y%m%dT%H%M%S'
```

Copy the one printed `backup_dir=...` line into the unit shell. This assigns
a folder name; it changes no file. Then run these commands in that unit shell:

```sh
mkdir "$backup_dir"
backup="$backup_dir/smartphone_integrator.json"
cp "$config" "$backup"
sync
```

Record the printed value from this command with the update notes:

```sh
echo "$backup"
```

### Install the prepared file

After exactly one backup block above, continue in the same shell. The
`backup` variable names the configuration saved for this transaction.

```sh
# Compare the backup with the original and validate the prepared file.
./mib2-extenders/file-checksum "$backup" "$config"
/eso/bin/jsonlint --file "$prepared"
# Make the configuration filesystem writable and install the prepared file.
mount -uw /mnt/system
cp "$prepared" "$config"
sync
# Compare the installed file with the prepared file.
./mib2-extenders/file-checksum "$prepared" "$config"
# Restore read-only mode only if it was the original mode.
mount -ur /mnt/system
# STOP HERE. The remaining commands undo this install or update.
# Restore only when this installed file still matches the prepared file.
./mib2-extenders/file-checksum "$prepared" "$config"
mount -uw /mnt/system
cp "$backup" "$config"
sync
# Compare the restored file with the saved original.
./mib2-extenders/file-checksum "$backup" "$config"
mount -ur /mnt/system
```

For each two-file checksum command, compare the two printed hashes before
the next step. They must be equal. An exit status of zero means that both
files were read; it does not mean their hashes match. The command reads files
without changing them. It prints SHA256 in the same sum-line format as the
host `sha256sum` command. A read or output error gives a nonzero exit status.

If the configuration filesystem was already writable, omit both read-only
commands. Restore every changed mount to its original mode. A failed copy,
parser check or hash comparison is a failed install. Restore the saved
configuration and mount mode before any restart. Do not continue with a
partial copy. No command in this set stops or restarts a process.

After all checks succeed, use the unit's normal restart control.
Inspect the stock main screen and normal projection first. Check the loader
versions in the system log. Open the toolkit's MMX command shell and run:

```sh
/bin/sloginfo
```

Find these exact message bodies for the current receiver process. Timestamp
and process fields can appear before each message:

```text
[GalLoader] loader 1.3.1+0
loader v43 version=0.36.0+43
```

The first line identifies GAL; the second identifies DIO. Only an installed
and selected receiver is expected to log its line. An earlier log entry is
not proof that a new process loaded the library. Check after a normal restart
and receiver startup. A missing line, a different version or a load error
means that the install is not verified. Save the output before further changes.
Record visible map, guidance start, disconnect and return to the built-in map
as separate results.

## Remove an extension

To remove GAL only, remove only its loader path from `children.gal.envs` in
a copy of the currently installed phone configuration. For DIO only, do the
same in `children.carplay.envs`. Keep other preload paths and unrelated fields.
Validate, review and install that copy with the same procedure.

The restore commands above undo the last transaction: after an update,
they restore the previously installed extension configuration. For complete
removal, use the first original backup only if no later configuration change
would be lost. Otherwise remove only the owned preload edits from a
copy of the current file. A configuration edit does not stop a running loader
or decoder. End projection through the stock controls before a normal restart.
Do not delete a running executable.

Keep the extension files until stock projection works after the restart.
Then remove only the owned extension directories from storage. Keep the
toolkit, maps, media, credentials and other content. Removing storage alone
is not a tested uninstall. Keep the original files for recovery.
