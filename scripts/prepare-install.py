# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 korhojoa
"""Prepare file locations and an owned Java startup block on a computer."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def install_folder(value):
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or value == "/"
        or ".." in path.parts
        or str(path) != value
        or not re.fullmatch(r"/[A-Za-z0-9_./-]+", value)
    ):
        raise ValueError(
            "Use an absolute install folder without spaces or shell characters"
        )
    return value


def replace_once(text, pattern, replacement):
    result, count = re.subn(
        pattern, lambda _match: replacement, text, flags=re.MULTILINE
    )
    if count != 1:
        raise ValueError("The supplied script layout is not recognized")
    return result


def startup_block(folder):
    directory = install_folder(folder) + "/lsd-extender"
    return (
        "# Start only our owned Java classes when their archive is readable.\n"
        f"LSD_EXTENDER_DIR={directory}\n"
        "LSD_EXTENDER_JAR=$LSD_EXTENDER_DIR/lsd-extender.jar\n"
        'if [ ! -r "$LSD_EXTENDER_JAR" ]; then\n'
        '    waitfor "$LSD_EXTENDER_JAR" 3 || :\n'
        "fi\n"
        'if [ -r "$LSD_EXTENDER_JAR" ]; then\n'
        '    BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:$LSD_EXTENDER_JAR"\n'
        '    VMOPTIONS="$VMOPTIONS -DextendedStartupSPI.class=org.korho.lsdextender.boot.StartupHook -Dlsdextender.conf=$LSD_EXTENDER_DIR/lsd-extender.conf"\n'
        "fi\n"
    )


def launcher(text, folder):
    if "\r" in text or not text.endswith("\n"):
        raise ValueError("Use the original launcher with LF line endings")
    if any(
        token in text
        for token in ("LSD_EXTENDER_", "extendedStartupSPI.class", "NavActiveIgnore")
    ):
        raise ValueError(
            "The launcher already has a startup extension; keep it unchanged"
        )
    lines = text.splitlines(keepends=True)
    positions = [i for i, line in enumerate(lines) if re.match(r"^\$J9 .* -jxe ", line)]
    if len(positions) != 1:
        raise ValueError("The native Java launch line is not unique")
    lines.insert(positions[0], startup_block(folder))
    return "".join(lines)


def prepare(card, stock_launcher, folder, output):
    folder = install_folder(folder)
    if output.exists() or output.is_symlink():
        raise ValueError("The prepared output folder must not exist")
    if card.is_symlink() or not card.is_dir():
        raise ValueError("The card input must be a regular folder")
    if output.resolve().is_relative_to(card.resolve()):
        raise ValueError("Prepared output cannot be inside its card input")
    files = sorted(card.rglob("*"))
    if any(p.is_symlink() for p in files):
        raise ValueError("Linked card input is not accepted")
    if any(p.is_file() and p.stat().st_size > 64 * 1024 * 1024 for p in files):
        raise ValueError("Card input file is too large")
    if stock_launcher.is_symlink() or not stock_launcher.is_file():
        raise ValueError("Use a regular copy of the unit launcher")
    if stock_launcher.stat().st_size > 1024 * 1024:
        raise ValueError("The unit launcher is too large")
    source_launcher = stock_launcher.read_text(encoding="ascii")
    planned_launcher = launcher(source_launcher, folder)
    directory = folder + "/lsd-extender"
    changes = {}
    conf = (card / "lsd-extender/lsd-extender.conf").read_text()
    conf = replace_once(
        conf,
        r"^spawn sh [^\n]*/mount-vaa[.]sh$",
        "spawn sh " + directory + "/mount-vaa.sh",
    )
    conf = replace_once(
        conf,
        r"^spawn sh [^\n]*/run-native-aa-creds[.]sh$",
        "spawn sh " + directory + "/run-native-aa-creds.sh",
    )
    conf = replace_once(
        conf,
        r"^prop lsdextender[.]carplay[.]config=.*$",
        "prop lsdextender.carplay.config=" + folder + "/dio-extender/dio_loader.conf",
    )
    conf += (
        "lsdextender.androidauto.config=" + folder + "/gal-extender/gal_loader.conf\n"
    )
    changes["lsd-extender/lsd-extender.conf"] = conf
    name = "lsd-extender/run-native-aa-creds.sh"
    text = (card / name).read_text()
    match = re.search(r"^PUBLISHER=(/[^\n]+/aawg-creds)$", text, re.MULTILINE)
    if match is None:
        raise ValueError("The wireless launcher layout is not recognized")
    text = text.replace(str(PurePosixPath(match[1]).parent), directory)
    changes[name] = text
    name = "lsd-extender/mount-vaa.sh"
    text = (card / name).read_text()
    text = replace_once(
        text,
        r'^  SO="\$\{VAA_SO:-\}"$',
        '  SO="${VAA_SO:-' + directory + '/devu-vaa.so}"',
    )
    changes[name] = text
    name = "lsd-extender/native-aa-kit/btstack"
    text = replace_once(
        (card / name).read_text(),
        r"^L=/[^\n]+$",
        "L=" + directory + "/libgal_btshim.so",
    )
    changes[name] = text
    gal_conf = "gal-extender/gal_loader.conf"
    text = (card / gal_conf).read_text()
    if re.search(r"^\s*extender_settings_dir\s*=", text, re.MULTILINE):
        text = replace_once(
            text,
            r"^\s*extender_settings_dir\s*=.*$",
            "extender_settings_dir=../lsd-extender",
        )
    else:
        text += "\nextender_settings_dir=../lsd-extender\n"
    changes[gal_conf] = text
    try:
        output.mkdir(parents=True)
        shutil.copytree(card, output / "card")
        for name, text in changes.items():
            (output / "card" / name).write_text(text, encoding="ascii")
        kit = output / "card/lsd-extender/native-aa-kit"
        checksums = []
        for line in (kit / "SHA256SUMS").read_text().splitlines():
            _digest, name = line.split("  ", 1)
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise ValueError("Invalid Bluetooth kit checksum path")
            checksums.append(
                hashlib.sha256((kit / name).read_bytes()).hexdigest() + "  " + name
            )
        (kit / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
        (output / "lsd.sh.prepared").write_text(planned_launcher, encoding="ascii")
        record = {
            "install_folder": folder,
            "original_launcher_sha256": hashlib.sha256(
                source_launcher.encode()
            ).hexdigest(),
            "prepared_launcher_sha256": hashlib.sha256(
                planned_launcher.encode()
            ).hexdigest(),
            "configured_files": sorted(changes),
        }
        (output / "PREPARED.json").write_text(json.dumps(record, indent=2) + "\n")
        sums = [
            hashlib.sha256(p.read_bytes()).hexdigest()
            + "  "
            + p.relative_to(output).as_posix()
            for p in sorted(output.rglob("*"))
            if p.is_file()
        ]
        (output / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    except BaseException:
        shutil.rmtree(output)
        raise
    print("Prepared files for " + folder + "; no unit file was changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, default=ROOT / "card")
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--install-folder", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.card, args.launcher, args.install_folder, args.output)


if __name__ == "__main__":
    main()
