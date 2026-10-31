# SPDX-License-Identifier: GPL-3.0-only
"""Bounded package inputs and corresponding public source files."""

import hashlib
import json
import posixpath
import re
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

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


def check_guide_links(files):
    """Require local links in the install documents to exist in the archive."""
    names = (
        "README.md",
        "INSTALL.md",
        "LICENSES.md",
        "docs/TERMS.md",
        "docs/SETTINGS.md",
    )
    for name in names:
        if name not in files:
            raise ValueError("Missing install document: " + name)
    for name in names:
        text = files[name].decode("ascii")
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), unquote(url.path))
            )
            if target not in files:
                raise ValueError("Broken install link: " + name + " -> " + link)


def ffmpeg_sources(source):
    """Include the exact source and license for the linked decoder dependency."""
    directory = source / "build/ffmpeg"

    result = json.loads(read(directory / "RESULT.json"))
    version = result["version"]
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", version
    ):
        raise ValueError("Invalid decoder dependency version")
    archive = "ffmpeg-" + version + ".tar.xz"
    data = read(directory / archive)
    if sha(data) != result["archive_sha256"]:
        raise ValueError("Decoder dependency source checksum differs")
    files = {"sources/third_party/" + archive: data}
    for name in ("COPYING.LGPLv2.1", "LICENSE.md"):
        files["LICENSES/ffmpeg/" + name] = read(
            directory / "prefix/share/licenses/ffmpeg" / name
        )
    return files
