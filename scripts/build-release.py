#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run the component producers, then assemble one install and source bundle."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

import bundle

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/korhojoa/qnx650-compiler@sha256:85f95b995d4b5dc2c323a6842c29b5c08652f34cc2288f6cc745534f5b2ecc7a"
NATIVE_SCRIPT = """set -eu
cd "$1"
python3 -B scripts/test-bundle.py
cd "$1/gal-extender"
sh .github/scripts/build-public-rust.sh
cargo build --locked --offline --release --target armv7-unknown-nto-qnx650 \\
    --manifest-path third_party/mib2-shared-crates/Cargo.toml -p file-checksum
cd "$1/dio-extender"
python3 tools/public-build.py
cd "$1"
python3 scripts/bundle.py --gal-target "$2" --dio-output "$3"
"""
FETCH_SCRIPT = """set -eu
for component in gal-extender dio-extender; do
    cd "$1/$component"
    cargo fetch --locked
    for dependency in mib2-shared-crates qnx650-crates; do
        cargo fetch --locked --manifest-path "third_party/$dependency/Cargo.toml"
    done
done
"""


def container_command(
    engine: str,
    root: Path,
    registry: Path | None,
    gal_target: Path,
    dio_cache: Path,
    fetch: bool = False,
) -> list[str]:
    """Use normal optional caches, never copy a Cargo home or compiler tools."""
    command = [
        engine,
        "run",
        "--rm",
        "--entrypoint",
        "sh",
        "-v",
        f"{root}:/work:rw",
        "-v",
        f"{gal_target}:/target:rw",
        "-e",
        "CARGO_TARGET_DIR=/target",
        "-e",
        "CARGO_HOME=/cargo",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-w",
        "/work",
    ]
    if registry is not None:
        command.extend(["-v", f"{registry}:/cargo/registry:rw"])
        command.extend(["-v", f"{registry.parent / 'git'}:/cargo/git:rw"])
    safe = ["/work", "/work/gal-extender", "/work/dio-extender"]
    for component in ("gal-extender", "dio-extender"):
        output = bundle.git(root / component, "submodule", "status", "--recursive")
        for line in output.splitlines():
            fields = line.split()
            if len(fields) >= 2:
                safe.append(f"/work/{component}/{fields[1]}")
    command.extend(["-e", f"GIT_CONFIG_COUNT={len(safe)}"])
    for index, path in enumerate(safe):
        command.extend(
            [
                "-e",
                f"GIT_CONFIG_KEY_{index}=safe.directory",
                "-e",
                f"GIT_CONFIG_VALUE_{index}={path}",
            ]
        )
    if dio_cache is not None:
        command.extend(["-v", f"{dio_cache}:/dio-output:rw"])
        product = dio_cache / "build"
        product.mkdir(parents=True, exist_ok=True)
        command.extend(["-v", f"{product}:/work/dio-extender/build:rw"])
        for manifest in bundle.git(
            root / "dio-extender", "ls-files", "*Cargo.toml"
        ).splitlines():
            relative = Path(manifest).parent / "target-img-e8c3e25afa71"
            cache = dio_cache / relative
            cache.mkdir(parents=True, exist_ok=True)
            command.extend(["-v", f"{cache}:/work/dio-extender/{relative}:rw"])
        ffmpeg = dio_cache / "build/ffmpeg"
        ffmpeg.mkdir(parents=True, exist_ok=True)
        command.extend(["-v", f"{ffmpeg}:/work/dio-extender/build/ffmpeg:rw"])
    return [
        *command,
        IMAGE,
        "-ec",
        FETCH_SCRIPT if fetch else NATIVE_SCRIPT,
        "build-release",
        "/work",
        "/target",
        "/dio-output",
    ]


def in_compiler_image() -> bool:
    """Recognize the installed compiler and linker, without a container engine."""
    return (
        Path("/opt/rust-qnx/bin/rustc").is_file()
        and Path("/usr/local/bin/link-qnx.sh").is_file()
    )


def build_direct(root: Path, gal_target: Path, fetch: bool) -> None:
    """Use this image's tools and the component's normal output directories."""
    env = dict(os.environ, CARGO_TARGET_DIR=str(gal_target))
    env.setdefault("CARGO_HOME", str(Path.home() / ".cargo"))
    subprocess.run(
        [
            "sh",
            "-ec",
            FETCH_SCRIPT if fetch else NATIVE_SCRIPT,
            "build-release",
            str(root),
            str(gal_target),
            str(root / "dio-extender"),
        ],
        env=env,
        check=True,
        timeout=1800,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE"))
    parser.add_argument(
        "--registry-cache", type=Path, default=Path.home() / ".cargo/registry"
    )
    parser.add_argument(
        "--fetch", action="store_true", help="Fetch the pinned registry dependencies"
    )
    parser.add_argument("--gal-target", type=Path, default=ROOT / "build/gal-target")
    parser.add_argument("--dio-cache-root", type=Path, default=ROOT / "build/dio")
    args = parser.parse_args()
    bundle.identities(ROOT)
    if not args.fetch and (ROOT / "build/mib2-extenders.zip").exists():
        raise ValueError(
            "bundle already exists; retain or remove it before a new build"
        )
    args.gal_target = args.gal_target.resolve()
    args.gal_target.mkdir(parents=True, exist_ok=True)
    if in_compiler_image():
        build_direct(ROOT, args.gal_target, args.fetch)
        return
    engine = args.engine or shutil.which("podman")
    if not engine:
        raise RuntimeError("TOOL MISSING: Podman, for the public compiler container")
    engine = shutil.which(engine)
    if engine is None:
        raise RuntimeError("configured container engine is not available")
    if args.registry_cache is not None:
        args.registry_cache = args.registry_cache.resolve()
        args.registry_cache.mkdir(parents=True, exist_ok=True)
        (args.registry_cache.parent / "git").mkdir(parents=True, exist_ok=True)
    args.dio_cache_root = args.dio_cache_root.resolve()
    args.dio_cache_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        container_command(
            engine,
            ROOT,
            args.registry_cache,
            args.gal_target,
            args.dio_cache_root,
            args.fetch,
        ),
        check=True,
        timeout=1800,
    )


if __name__ == "__main__":
    main()
