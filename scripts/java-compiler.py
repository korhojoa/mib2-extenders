# SPDX-License-Identifier: GPL-3.0-only
"""Get the pinned Java compiler inside the public compiler container."""

import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

URL = (
    "https://github.com/adoptium/temurin8-binaries/releases/download/"
    "jdk8u504-b01/OpenJDK8U-jdk_x64_linux_hotspot_8u504b01.tar.gz"
)
SHA256 = "9c70e102f527ac674ac2fe9c7d47b9a04e2d19842ba5ab8e9b33f368bbadfaea"
SIZE = 103542511


def install(destination):
    if (
        not Path("/opt/rust-qnx/bin/rustc").is_file()
        or not Path("/usr/local/bin/link-qnx.sh").is_file()
    ):
        raise ValueError("Java build tools must stay inside the compiler container")
    if destination.exists():
        raise ValueError("Java compiler destination already exists")
    with tempfile.TemporaryDirectory(prefix="java-compiler-") as folder:
        root = Path(folder)
        archive = root / "compiler.tar.gz"
        digest = hashlib.sha256()
        size = 0
        with (
            urllib.request.urlopen(URL, timeout=60) as response,
            archive.open("wb") as out,
        ):
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > SIZE:
                    raise ValueError("Java compiler archive is too large")
                digest.update(block)
                out.write(block)
        if size != SIZE or digest.hexdigest() != SHA256:
            raise ValueError("Java compiler checksum differs")
        unpack = root / "unpack"
        with tarfile.open(archive) as source:
            source.extractall(unpack, filter="data")
        roots = list(unpack.iterdir())
        if len(roots) != 1 or not (roots[0] / "bin/javac").is_file():
            raise ValueError("Unexpected Java compiler archive layout")
        result = subprocess.run(
            [str(roots[0] / "bin/javac"), "-version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if (result.stdout + result.stderr).strip() != "javac 1.8.0_504":
            raise ValueError("Unexpected Java compiler version")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(roots[0]), destination)
    print("Verified Java compiler: javac 1.8.0_504")


if __name__ == "__main__":
    install(Path(sys.argv[1]))
