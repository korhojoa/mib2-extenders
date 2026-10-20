#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Assemble exact public build outputs. This tool never connects to a unit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
NATIVE = {
    "gal-extender/libgal_loader.so": "build/gal-target/armv7-unknown-nto-qnx650/release/libgal_loader.so",
    "dio-extender/libdio_loader.so": "dio-extender/build/public-compiler/libdio_loader.so",
    "dio-extender/libdio_altscreen.so": "dio-extender/build/public-compiler/libdio_altscreen.so",
    "dio-extender/libdio_clustervideo.so": "dio-extender/build/public-compiler/libdio_clustervideo.so",
    "dio-extender/cluster-video": "dio-extender/rust/cluster-video-decoder/target-img-e8c3e25afa71/armv7-unknown-nto-qnx650/release/cluster-video",
}
DEPENDENCIES = {
    "mib2-shared-crates": "88067cf6db70df46fe645d1d4c23ed40a3248a6d",
    "qnx650-crates": "a7c6b2dc6a6414c880be6ce565c7b05fb4ec975a",
}
LIMIT = 64 * 1024 * 1024


def git(root: Path, *args: str) -> str:
    """Read a bounded Git source identity without a shell."""
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, timeout=30
    ).strip()


def read(path: Path) -> bytes:
    """Reject links and empty or unbounded product inputs."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"not a regular input: {path.name}")
    if not 0 < path.stat().st_size <= LIMIT:
        raise ValueError(f"invalid input size: {path.name}")
    return path.read_bytes()


def sha(data: bytes) -> str:
    """Name exact bytes in the release receipt."""
    return hashlib.sha256(data).hexdigest()


def native(data: bytes, name: str) -> None:
    """Require little-endian ELF32 ARM outputs, never an SDK input archive."""
    if len(data) < 52 or data[:6] != b"\x7fELF\x01\x01" or data[18:20] != b"\x28\x00":
        raise ValueError(f"not an ELF32 ARM product: {name}")


def identities(root: Path) -> dict[str, str]:
    """Require all final pinned public dependencies before assembly."""
    spec = json.loads((root / "components.json").read_text(encoding="ascii"))
    if set(spec) != {"gal-extender", "dio-extender"}:
        raise ValueError("both frozen native components are required")
    result = {}
    for name, record in spec.items():
        expected = record["commit"]
        if len(expected) != 40 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError(f"unfrozen component: {name}")
        if record["url"] != f"../{name}.git":
            raise ValueError(f"non-public component URL: {name}")
        component = root / name
        if component.is_symlink() or not component.is_dir():
            raise ValueError(f"missing regular component checkout: {name}")
        if not (component / ".git").exists():
            raise ValueError(f"missing initialized component: {name}")
        for entry in git(component, "submodule", "status", "--recursive").splitlines():
            if entry.startswith(("-", "+", "U")):
                raise ValueError(f"missing or changed nested dependency: {name}")
        url = subprocess.check_output(
            [
                "git",
                "config",
                "--file",
                str(root / ".gitmodules"),
                "--get",
                f"submodule.{name}.url",
            ],
            text=True,
            timeout=30,
        ).strip()
        if url != record["url"]:
            raise ValueError(f"submodule URL differs: {name}")
        entry = git(root, "ls-files", "--stage", "--", name).split()
        if entry[:3] != ["160000", expected, "0"]:
            raise ValueError(f"submodule index differs: {name}")
        if git(component, "rev-parse", "HEAD") != expected:
            raise ValueError(f"component identity differs: {name}")
        if git(component, "status", "--porcelain", "--untracked-files=normal"):
            raise ValueError(f"component source is dirty: {name}")
        for dependency, commit in DEPENDENCIES.items():
            nested = component / "third_party" / dependency
            if git(nested, "rev-parse", "HEAD") != commit:
                raise ValueError(
                    f"shared dependency identity differs: {name}/{dependency}"
                )
        result[name] = expected
    return result


def source_tree(root: Path, prefix: str, files: dict[str, tuple[bytes, int]]) -> None:
    """Include corresponding public source and pinned nested dependencies."""
    entries = git(root, "ls-files", "--stage", "-z").split("\0")
    for entry in entries:
        if not entry:
            continue
        info, name = entry.split("\t", 1)
        mode, _object, stage = info.split()
        path = PurePosixPath(name)
        if stage != "0" or path.is_absolute() or ".." in path.parts:
            raise ValueError("invalid source index")
        if mode == "160000":
            source_tree(root / name, f"{prefix}/{name}", files)
        elif mode in {"100644", "100755"}:
            files[f"{prefix}/{name}"] = (
                (root / name).read_bytes(),
                int(mode, 8) & 0o777,
            )
        else:
            raise ValueError(f"unsupported source mode: {mode}")


def readme_for_bundle(data: bytes) -> bytes:
    """Use source paths present in the ZIP and omit Git-only build commands."""
    text = data.decode("ascii")
    for part in ("gal", "dio"):
        text = text.replace(
            f"({part}-extender/README.md)", f"(sources/{part}-extender/README.md)"
        )
    text = text.replace(
        "Skip the\nsource and build sections below and follow", "Follow"
    )
    start = text.index("## Get the source\n")
    end = text.index("## Install\n", start)
    return (text[:start] + text[end:]).encode("ascii")


def collect(
    root: Path, gal_target: Path | None, dio_output: Path | None = None
) -> dict[str, tuple[bytes, int]]:
    """Collect a complete matched install set with corresponding source."""
    commits = identities(root)
    files: dict[str, tuple[bytes, int]] = {}
    dio_output = dio_output or root / "build/dio"
    for destination, source in NATIVE.items():
        path = root / source
        if destination.startswith("gal-") and gal_target is not None:
            path = gal_target / "armv7-unknown-nto-qnx650/release/libgal_loader.so"
        if destination.startswith("dio-"):
            path = dio_output / Path(source).relative_to("dio-extender")
        data = read(path)
        native(data, destination)
        files[f"card/{destination}"] = (
            data,
            0o755 if destination.endswith("/cluster-video") else 0o644,
        )
    for name in ("gal", "dio"):
        files[f"card/{name}-extender/{name}_loader.conf"] = (
            read(root / f"{name}-extender/examples/{name}_loader.conf"),
            0o644,
        )
    checksum = (gal_target or root / "build/gal-target") / (
        "armv7-unknown-nto-qnx650/release/file-checksum"
    )
    data = read(checksum)
    native(data, "file-checksum")
    files["card/mib2-extenders/file-checksum"] = (data, 0o755)
    ffmpeg = dio_output / "build/ffmpeg"
    dependency = json.loads(read(ffmpeg / "RESULT.json"))
    version = dependency["version"]
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", version
    ):
        raise ValueError("invalid dependency version")
    archive_name = f"ffmpeg-{version}.tar.xz"
    source = read(ffmpeg / archive_name)
    if sha(source) != dependency["archive_sha256"]:
        raise ValueError("dependency source archive differs")
    files[f"sources/third_party/{archive_name}"] = (source, 0o644)
    for name in ("COPYING.LGPLv2.1", "LICENSE.md"):
        files[f"licenses/ffmpeg/{name}"] = (
            read(ffmpeg / "prefix/share/licenses/ffmpeg" / name),
            0o644,
        )
    for name in (
        "README.md",
        "INSTALL.md",
        "docs/TERMS.md",
        "docs/SETTINGS.md",
        "LICENSES.md",
        "COPYING",
    ):
        files[name] = (
            readme_for_bundle(read(root / name))
            if name == "README.md"
            else read(root / name),
            0o644,
        )
    for name in commits:
        source_tree(root / name, f"sources/{name}", files)
    payload = {name: sha(data) for name, (data, _mode) in sorted(files.items())}
    receipt = {
        "schema": 1,
        "components": commits,
        "files": payload,
        "unit_commands": "not qualified in emulator",
        "device_test": "not performed",
    }
    files["RELEASE.json"] = (
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("ascii"),
        0o644,
    )
    files["SHA256SUMS"] = (
        "".join(
            f"{sha(data)}  {name}\n" for name, (data, _mode) in sorted(files.items())
        ).encode("ascii"),
        0o644,
    )
    return files


def write_bundle(path: Path, files: dict[str, tuple[bytes, int]]) -> str:
    """Write once, verify every member, remove only an owned failed output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        try:
            with zipfile.ZipFile(
                stream, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for name, (data, mode) in sorted(files.items()):
                    item = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                    item.create_system = 3
                    item.external_attr = (stat.S_IFREG | mode) << 16
                    item.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(item, data, compresslevel=9)
            stream.flush()
            with zipfile.ZipFile(path) as archive:
                if set(archive.namelist()) != set(files):
                    raise ValueError("bundle members differ")
                for name, (data, mode) in files.items():
                    if (
                        archive.read(name) != data
                        or archive.getinfo(name).external_attr >> 16
                        != stat.S_IFREG | mode
                    ):
                        raise ValueError(f"bundle readback differs: {name}")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return sha(path.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build/mib2-extenders.zip")
    parser.add_argument("--gal-target", type=Path)
    parser.add_argument("--dio-output", type=Path)
    args = parser.parse_args()
    files = collect(ROOT, args.gal_target, args.dio_output)
    print(
        f"bundle={args.out.name} files={len(files)} sha256={write_bundle(args.out, files)}"
    )


if __name__ == "__main__":
    main()
