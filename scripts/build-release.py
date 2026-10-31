# SPDX-License-Identifier: GPL-3.0-only
"""Build all components from pinned source and make one install archive."""

import argparse
import bundle
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def documents():
    return (
        json.loads((ROOT / "components.json").read_text()),
        json.loads((ROOT / "expected-files.json").read_text()),
    )


def relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts or str(path) != name:
        raise ValueError("Unsafe component path")
    return path


def check_sources():
    sources, expected = documents()
    names = []
    for part in sources["parts"].values():
        if not re.fullmatch(r"[0-9a-f]{40}", part["commit"]):
            raise ValueError("Source commit is not complete")
        if not part["url"].startswith("https://github.com/"):
            raise ValueError("Source URL must be public HTTPS")
        if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", part["image"]):
            raise ValueError("Compiler image is not pinned")
        if part["kind"] not in ("rust", "java") or not part["commands"]:
            raise ValueError("Missing public build command")
        for command in part["commands"]:
            if not command or not all(
                isinstance(item, str) and item for item in command
            ):
                raise ValueError("Invalid build command")
        relative(part["image_source"])
        for name, output in part["outputs"].items():
            relative(name)
            relative(output.removeprefix("@target/"))
            names.append(name)
    if len(names) != len(set(names)) or set(names) != set(expected["files"]):
        raise ValueError("Source outputs do not cover the release exactly")
    return sources, expected


def git_environment(local_sources):
    env = dict(os.environ)
    aliases = []
    server = env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    if server != "https://github.com":
        owner = env["GITHUB_REPOSITORY"].split("/", 1)[0]
        aliases.append((f"{server}/{owner}/", "https://github.com/korhojoa/"))
    if local_sources:
        env["GIT_ALLOW_PROTOCOL"] = "file:https:http"
        sources, _ = documents()
        for name, path in local_sources.items():
            url = sources["parts"][name]["url"] if name in sources["parts"] else name
            if urlparse(url).scheme != "https":
                raise ValueError("Local source alias needs a public HTTPS URL")
            aliases.append((Path(path).resolve().as_uri(), url))
    count = int(env.get("GIT_CONFIG_COUNT", "0"))
    for replacement, original in aliases:
        env[f"GIT_CONFIG_KEY_{count}"] = f"url.{replacement}.insteadOf"
        env[f"GIT_CONFIG_VALUE_{count}"] = original
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    return env


def checkout(part, destination, env):
    if destination.exists():
        raise ValueError("Source destination already exists")
    subprocess.run(["git", "init", "-q", str(destination)], check=True, env=env)
    for command in (
        ["git", "remote", "add", "origin", part["url"]],
        ["git", "fetch", "--no-tags", "--depth=1", "origin", part["commit"]],
        ["git", "checkout", "--detach", "FETCH_HEAD"],
        ["git", "submodule", "update", "--init", "--recursive"],
    ):
        subprocess.run(command, cwd=destination, check=True, env=env, timeout=180)


def checked_payload(path, expected):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing regular build output: " + path.name)
    data = bundle.read(path)
    if expected.get("native"):
        bundle.native(data, path.name)
    if "classes" in expected:
        with zipfile.ZipFile(path) as jar:
            names = jar.namelist()
            if len(names) != len(set(names)) or set(names) != set(expected["classes"]):
                raise ValueError("Java class membership differs: " + path.name)
            for name in names:
                if not name.startswith("org/korho/lsdextender/") or not name.endswith(
                    ".class"
                ):
                    raise ValueError("Unexpected Java archive member")
                if (
                    hashlib.sha256(jar.read(name)).hexdigest()
                    != expected["classes"][name]
                ):
                    raise ValueError("Java class bytes differ: " + name)
    elif "sha256" in expected and (
        len(data) != expected["bytes"]
        or hashlib.sha256(data).hexdigest() != expected["sha256"]
    ):
        raise ValueError("Build output differs from the released file: " + path.name)
    return data


def source_clean(source, commit):
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True
    ).strip()
    if actual != commit:
        raise ValueError("Source commit differs from the release plan")
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--"], cwd=source, check=True)
    subprocess.run(
        ["git", "submodule", "foreach", "--recursive", "git diff --exit-code HEAD --"],
        cwd=source,
        check=True,
        timeout=30,
    )


def build_part(name, source, output, env, target_cache):
    sources, expected = check_sources()
    part = sources["parts"][name]
    source_clean(source, part["commit"])
    if part["image"] not in (source / part["image_source"]).read_text():
        raise ValueError("Public producer uses another compiler image")
    if output.exists():
        raise ValueError("Component output directory already exists")
    build_env = dict(env)
    if part["kind"] == "rust" and target_cache and name != "dio":
        build_env["CARGO_TARGET_DIR"] = str(target_cache)
    if name == "dio":
        # Its normal producer uses separate component target directories.
        build_env.pop("CARGO_TARGET_DIR", None)
    for command in part["commands"]:
        subprocess.run(command, cwd=source, check=True, env=build_env, timeout=900)
    source_clean(source, part["commit"])
    payloads = {}
    for dest, location in part["outputs"].items():
        if location.startswith("@target/"):
            base = target_cache if target_cache else source / "target"
            built = base / location.removeprefix("@target/")
        else:
            base = source
            built = source / location
        if not built.resolve().is_relative_to(base.resolve()):
            raise ValueError("Build output escapes its root")
        payloads[dest] = checked_payload(built, expected["files"][dest])
    output.mkdir(parents=True)
    for dest, data in payloads.items():
        path = output / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(int(expected["files"][dest]["mode"], 8))
        print("VERIFIED " + dest + " " + hashlib.sha256(data).hexdigest(), flush=True)

    for license_name in part.get("licenses", []):
        relative(license_name)
        license_file = source / license_name
        if license_file.is_symlink() or not license_file.is_file():
            raise ValueError("Missing regular source license")
        destination = output.parent.parent / "licenses" / name / license_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = license_file.read_bytes()
        if hashlib.sha256(data).hexdigest() != part["licenses"][license_name]:
            raise ValueError("Source license bytes differ")
        destination.write_bytes(data)


def manifest(payloads, expected, sources):
    lines = [
        "MIB2 extender install files",
        "version: " + sources["version"],
        "Android Auto, CarPlay and owned settings pages.",
        "",
    ]
    core = payloads["lsd-extender/core-build.properties"].decode()
    identity = next(
        line.removeprefix("core_id=")
        for line in core.splitlines()
        if line.startswith("core_id=")
    )
    lines.append("core-source-sha256: " + identity)
    for name, data in sorted(payloads.items()):
        header = name + "  "
        if name.endswith(".jar"):
            header += (
                "= bundle of: core"
                if Path(name).name == "lsd-extender.jar"
                else "(runtime jar)"
            )
        lines.extend(
            [
                header,
                "  sha256 " + hashlib.sha256(data).hexdigest(),
                "  version "
                + str(expected["files"][name]["version"] or "unversioned data"),
            ]
        )
        if name.endswith(".jar"):
            lines.append("  " + sources["parts"]["java"]["banners"][Path(name).name])
    return ("\n".join(lines) + "\n").encode()


def package(parts, archive):
    sources, expected = check_sources()
    if not parts.is_dir() or {p.name for p in parts.iterdir()} != set(sources["parts"]):
        raise ValueError("Missing or unknown component directory")
    collected = {}
    for part in sources["parts"]:
        directory = parts / part
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError("Linked component output")
            if path.is_file():
                name = path.relative_to(directory).as_posix()
                if name not in sources["parts"][part]["outputs"] or name in collected:
                    raise ValueError("Unknown or duplicate component output")
                collected[name] = checked_payload(path, expected["files"][name])
    if set(collected) != set(expected["files"]):
        raise ValueError("Missing source-built release files")
    collected["lsd-extender/MANIFEST.txt"] = manifest(collected, expected, sources)
    inventory = {
        "version": sources["version"],
        "sources": sources["parts"],
        "files": [],
    }
    for name, data in sorted(collected.items()):
        record = {
            "path": name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "mode": expected["files"].get(name, {}).get("mode", "0o644"),
        }
        if name in expected["files"]:
            record.update(
                {key: expected["files"][name][key] for key in ("version", "car_sha256")}
            )
            if record["car_sha256"] and record["sha256"] != record["car_sha256"]:
                record["difference"] = expected["files"][name]["difference"]
        inventory["files"].append(record)
    extras = {
        "RELEASE.json": (json.dumps(inventory, indent=2) + "\n").encode(),
        "INSTALL.md": (ROOT / "INSTALL.md").read_bytes(),
        "scripts/prepare-install.py": (
            ROOT / "scripts/prepare-install.py"
        ).read_bytes(),
        "README.md": (ROOT / "README.md").read_bytes(),
        "components.json": (ROOT / "components.json").read_bytes(),
        "COPYING": (ROOT / "COPYING").read_bytes(),
        "LICENSES.md": (ROOT / "LICENSES.md").read_bytes(),
        "docs/TERMS.md": (ROOT / "docs/TERMS.md").read_bytes(),
        "docs/SETTINGS.md": (ROOT / "docs/SETTINGS.md").read_bytes(),
    }
    extra_modes = {}
    for part_name in sources["parts"]:
        source_root = parts.parent / "source-locations" / part_name
        if not source_root.is_file():
            raise ValueError("Missing component source location")
        source = Path(source_root.read_text().strip())
        source_clean(source, sources["parts"][part_name]["commit"])
        owned_source = {}
        bundle.source_tree(source, "sources/" + part_name, owned_source)
        extras.update({key: data for key, (data, _mode) in owned_source.items()})
        extra_modes.update({key: mode for key, (_data, mode) in owned_source.items()})
        if part_name == "dio":
            extras.update(bundle.ffmpeg_sources(source))
    required_licenses = {
        part_name + "/" + path: digest
        for part_name, part in sources["parts"].items()
        for path, digest in part.get("licenses", {}).items()
    }
    observed_licenses = set()
    for path in sorted((parts.parent / "licenses").rglob("*")):
        if path.is_symlink():
            raise ValueError("Linked license file")
        if path.is_file():
            name = path.relative_to(parts.parent / "licenses").as_posix()
            data = path.read_bytes()
            if (
                name not in required_licenses
                or hashlib.sha256(data).hexdigest() != required_licenses[name]
            ):
                raise ValueError("Unknown or changed license file")
            observed_licenses.add(name)
            extras["LICENSES/" + name] = data
    if observed_licenses != set(required_licenses):
        raise ValueError("Missing source license file")
    if archive.exists():
        raise ValueError("Archive already exists")
    archive.parent.mkdir(parents=True, exist_ok=True)
    contents = {"card/" + name: data for name, data in collected.items()} | extras
    bundle.check_guide_links(contents)
    contents["SHA256SUMS"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(contents.items())
    ).encode()
    entries = {}
    for name, data in sorted(contents.items()):
        card_name = name.removeprefix("card/")
        mode = extra_modes.get(
            name, int(expected["files"].get(card_name, {}).get("mode", "0o644"), 8)
        )
        entries[name] = (data, mode)
    bundle.write_bundle(archive, entries)
    archive.with_suffix(".inventory.json").write_bytes(extras["RELEASE.json"])
    print(f"VERIFIED archive: {len(collected)} source-built card files", flush=True)


def parse_local(values):
    result = {}
    for value in values:
        name, path = value.split("=", 1)
        result[name] = path
    return result


def run_container(args):
    """Run the same source build in one pinned public compiler container."""
    sources, _ = check_sources()
    engine = shutil.which(args.engine)
    if engine is None:
        raise RuntimeError(
            "No container engine found; install Podman or set CONTAINER_ENGINE"
        )
    if args.local_source:
        raise ValueError("Local source aliases need --inside-compiler")
    work = args.work.resolve()
    work.parent.mkdir(parents=True, exist_ok=True)
    target = args.target_cache.resolve()
    target.mkdir(parents=True, exist_ok=True)
    cargo = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))
    for folder in ("registry", "git"):
        (cargo / folder).mkdir(parents=True, exist_ok=True)
    image = sources["parts"]["gal"]["image"]
    command = [
        engine,
        "run",
        "--rm",
        "--entrypoint",
        "/bin/sh",
        "-v",
        str(ROOT) + ":/bundle:ro",
        "-v",
        str(work.parent) + ":/output",
        "-v",
        str(target) + ":/target",
        "-v",
        str(cargo / "registry") + ":/cargo/registry",
        "-v",
        str(cargo / "git") + ":/cargo/git",
        "-e",
        "CARGO_HOME=/cargo",
        "-e",
        "JAVA_HOME=/opt/owned-jdk8",
        "-w",
        "/bundle",
        image,
        "-ec",
        "python3 -B scripts/java-compiler.py /opt/owned-jdk8; "
        "exec python3 -B scripts/build-release.py build --inside-compiler "
        '--target-cache /target --work "$1"',
        "release-build",
        "/output/" + work.name,
    ]
    subprocess.run(command, check=True, timeout=2700)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("check")
    build = commands.add_parser("build")
    build.add_argument("--work", type=Path, default=ROOT / "build/release")
    build.add_argument("--target-cache", type=Path, default=ROOT / "build/target")
    build.add_argument("--inside-compiler", action="store_true")
    build.add_argument("--local-source", action="append", default=[])
    build.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE", "podman"))
    pack = commands.add_parser("package")
    pack.add_argument("parts", type=Path)
    pack.add_argument("archive", type=Path)
    args = parser.parse_args()
    sources, _ = check_sources()
    if args.action == "check":
        print("All public source pins and output contracts are complete")
    elif args.action == "package":
        package(args.parts, args.archive)
    else:
        if not args.inside_compiler:
            run_container(args)
            return 0
        local = parse_local(args.local_source)
        env = git_environment(local)
        env["CONTAINER_ENGINE"] = args.engine
        if args.inside_compiler:
            if (
                not Path("/opt/rust-qnx/bin/rustc").is_file()
                or not Path("/usr/local/bin/link-qnx.sh").is_file()
            ):
                raise ValueError("Direct build needs the pinned compiler container")
            env["PUBLIC_COMPILER_DIRECT"] = "1"
            env["OWNED_JAVA_DIRECT"] = "1"
        work = args.work.resolve()
        if work.exists():
            raise ValueError("Build work folder already exists")
        work.mkdir(parents=True)
        target_cache = args.target_cache.resolve() if args.target_cache else None
        if target_cache:
            target_cache.mkdir(parents=True, exist_ok=True)
        failures = []
        for name, part in sources["parts"].items():
            source = work / "sources" / name
            checkout(part, source, env)
            try:
                build_part(name, source, work / "parts" / name, env, target_cache)
            except (ValueError, subprocess.SubprocessError) as error:
                print("REFUSED component " + name + ": " + str(error), flush=True)
                failures.append(name)
                continue
            locations = work / "source-locations"
            locations.mkdir(exist_ok=True)
            (locations / name).write_text(str(source) + "\n")
        if failures:
            raise ValueError(
                "No bundle created; component checks failed: " + ", ".join(failures)
            )
        package(work / "parts", work / "mib2-extenders.zip")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        sys.exit(1)
