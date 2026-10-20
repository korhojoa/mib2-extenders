#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise native package integrity and complete dependency requirements."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import bundle


class BundleTest(unittest.TestCase):
    """Constructed bytes are test inputs, never unit captures."""

    def test_write_is_reproducible_and_refuses_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.zip"
            second = Path(temp) / "second.zip"
            files = {
                "card/config.conf": (b"value=1\n", 0o644),
                "card/run.sh": (b"#!/bin/sh\nexit 0\n", 0o755),
            }
            self.assertEqual(
                bundle.write_bundle(first, files), bundle.write_bundle(second, files)
            )
            before = first.read_bytes()
            with self.assertRaises(FileExistsError):
                bundle.write_bundle(first, files)
            self.assertEqual(first.read_bytes(), before)
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.getinfo("card/run.sh").external_attr >> 16 & 0o777, 0o755
                )

    def test_bundle_readme_uses_packaged_paths_and_omits_build_commands(self) -> None:
        original = (Path(__file__).resolve().parents[1] / "README.md").read_bytes()
        packaged = bundle.readme_for_bundle(original).decode("ascii")
        for part in ("gal", "dio"):
            self.assertIn(f"(sources/{part}-extender/README.md)", packaged)
            self.assertIn(f"({part}-extender/README.md)", original.decode("ascii"))
        self.assertIn("## Use a prebuilt bundle", packaged)
        self.assertIn("[INSTALL.md](INSTALL.md)", packaged)
        self.assertNotIn("scripts/build-release.py", packaged)
        self.assertNotIn("scripts/test-bundle.py", packaged)

    def test_linked_product_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = root / "actual"
            actual.write_bytes(b"constructed")
            linked = root / "linked"
            linked.symlink_to(actual)
            with self.assertRaisesRegex(ValueError, "regular input"):
                bundle.read(linked)

    def test_native_requires_arm_not_host_executable(self) -> None:
        header = bytearray(52)
        header[:6] = b"\x7fELF\x01\x01"
        header[18:20] = b"\x28\x00"
        bundle.native(bytes(header), "constructed")
        header[18:20] = b"\x3e\x00"
        with self.assertRaises(ValueError):
            bundle.native(bytes(header), "constructed")

    def test_missing_component_refuses_partial_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "components.json").write_text("{}", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "both frozen native"):
                bundle.identities(root)

    def test_native_payload_requires_the_checksum_command(self) -> None:
        header = bytearray(52)
        header[:6] = b"\x7fELF\x01\x01"
        header[18:20] = b"\x28\x00"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gal = root / "build/gal-target"
            dio = root / "build/dio"
            for destination, source in bundle.NATIVE.items():
                if destination.startswith("gal-"):
                    path = gal / "armv7-unknown-nto-qnx650/release/libgal_loader.so"
                else:
                    path = dio / Path(source).relative_to("dio-extender")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(header)
            checksum = gal / "armv7-unknown-nto-qnx650/release/file-checksum"
            checksum.write_bytes(header)
            for name in ("gal", "dio"):
                path = root / f"{name}-extender/examples/{name}_loader.conf"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {name} component example\nfeature=1\n")
            dependency = dio / "build/ffmpeg"
            licenses = dependency / "prefix/share/licenses/ffmpeg"
            licenses.mkdir(parents=True)
            archive = b"constructed dependency source"
            (dependency / "ffmpeg-1.2.3.tar.xz").write_bytes(archive)
            (dependency / "RESULT.json").write_text(
                json.dumps({"version": "1.2.3", "archive_sha256": bundle.sha(archive)})
            )
            for name in ("COPYING.LGPLv2.1", "LICENSE.md"):
                (licenses / name).write_text("constructed license fixture\n")
            for name in ("README.md", "INSTALL.md", "LICENSES.md", "COPYING"):
                (root / name).write_text(
                    "## Get the source\nGit-only commands\n## Install\n"
                    if name == "README.md"
                    else "constructed documentation\n"
                )
            documents = {
                "docs/TERMS.md": b"# Terms\n\nConstructed term definition.\n",
                "docs/SETTINGS.md": b"# Settings\n\nConstructed setting description.\n",
            }
            for name, data in documents.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            with (
                patch.object(bundle, "identities", return_value={}),
                patch.object(bundle, "source_tree"),
            ):
                files = bundle.collect(root, gal, dio)
                self.assertEqual(
                    {"card/" + name for name in bundle.NATIVE}
                    | {
                        "card/gal-extender/gal_loader.conf",
                        "card/dio-extender/dio_loader.conf",
                        "card/mib2-extenders/file-checksum",
                    },
                    {name for name in files if name.startswith("card/")},
                )
                self.assertEqual(
                    (bytes(header), 0o755), files["card/mib2-extenders/file-checksum"]
                )
                for name in ("gal", "dio"):
                    self.assertEqual(
                        (
                            root / f"{name}-extender/examples/{name}_loader.conf"
                        ).read_bytes(),
                        files[f"card/{name}-extender/{name}_loader.conf"][0],
                    )
                for name, data in documents.items():
                    self.assertEqual((data, 0o644), files[name])
                    receipt = json.loads(files["RELEASE.json"][0])
                    self.assertEqual(bundle.sha(data), receipt["files"][name])
                package = root / "documents.zip"
                bundle.write_bundle(package, files)
                with zipfile.ZipFile(package) as archive:
                    for name, data in documents.items():
                        self.assertEqual(data, archive.read(name))
                        self.assertEqual(
                            0o644, archive.getinfo(name).external_attr >> 16 & 0o777
                        )
                for name, data in documents.items():
                    with self.subTest(missing=name):
                        (root / name).unlink()
                        with self.assertRaisesRegex(
                            ValueError, "not a regular input: " + Path(name).name
                        ):
                            bundle.collect(root, gal, dio)
                        (root / name).write_bytes(data)
                checksum.unlink()
                with self.assertRaisesRegex(
                    ValueError, "not a regular input: file-checksum"
                ):
                    bundle.collect(root, gal, dio)


class CheckoutTest(unittest.TestCase):
    def test_entrypoint_refuses_missing_components(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "checkout"
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--no-recurse-submodules",
                    str(source),
                    str(checkout),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
            # Exercise the current entrypoint correction before its source commit.
            for name in ("bundle.py", "test-bundle.py"):
                shutil.copyfile(source / "scripts" / name, checkout / "scripts" / name)
            shutil.copyfile(source / "components.json", checkout / "components.json")
            for name in ("test-bundle.py",):
                result = subprocess.run(
                    [sys.executable, "-B", str(checkout / "scripts" / name)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("missing initialized component", result.stderr)

    def test_default_producer_paths_stay_in_combined_build(self):
        spec = importlib.util.spec_from_file_location(
            "release_builder", Path(__file__).with_name("build-release.py")
        )
        assert spec and spec.loader
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(producer, "ROOT", root),
                patch.object(producer, "in_compiler_image", return_value=False),
                patch.object(bundle, "identities"),
                patch.object(bundle, "git", return_value=""),
                patch.object(producer.shutil, "which", return_value="container-engine"),
                patch.object(producer.subprocess, "run") as run,
                patch.object(sys, "argv", ["build-release.py"]),
            ):
                producer.main()
            self.assertEqual(1, run.call_count)
            native = run.call_args_list[0]
            self.assertIn(
                str(root / "build/gal-target") + ":/target:rw", native.args[0]
            )
            self.assertIn(str(root / "build/dio") + ":/dio-output:rw", native.args[0])
            self.assertIn(
                str(root / "build/dio/build") + ":/work/dio-extender/build:rw",
                native.args[0],
            )
            self.assertTrue((root / "build/gal-target").is_dir())
            self.assertFalse((root / "gal-extender/target").exists())

    def test_compiler_image_uses_no_container_engine(self):
        spec = importlib.util.spec_from_file_location(
            "release_builder", Path(__file__).with_name("build-release.py")
        )
        assert spec and spec.loader
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for fetch in (False, True):
                argv = ["build-release.py", *(["--fetch"] if fetch else [])]
                with (
                    patch.object(producer, "ROOT", root),
                    patch.object(bundle, "identities"),
                    patch.object(producer, "in_compiler_image", return_value=True),
                    patch.object(producer.shutil, "which") as which,
                    patch.object(producer.subprocess, "run") as run,
                    patch.object(sys, "argv", argv),
                ):
                    producer.main()
                which.assert_not_called()
                self.assertEqual(["sh", "-ec"], run.call_args.args[0][:2])
                script = run.call_args.args[0][2]
                self.assertEqual(not fetch, "public-build.py" in script)
                self.assertEqual(
                    [
                        str(root),
                        str(root / "build/gal-target"),
                        str(root / "dio-extender"),
                    ],
                    run.call_args.args[0][-3:],
                )
                self.assertEqual(
                    str(root / "build/gal-target"),
                    run.call_args.kwargs["env"]["CARGO_TARGET_DIR"],
                )

    def test_direct_workspace_paths_are_separate_shell_arguments(self):
        spec = importlib.util.spec_from_file_location(
            "release_builder", Path(__file__).with_name("build-release.py")
        )
        assert spec and spec.loader
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)
        for root in (
            Path("/workspace/public/mib2-extenders"),
            Path("/workspace/public/folder with spaces"),
        ):
            target = root / "build/gal-target"
            for fetch in (False, True):
                with patch.object(producer.subprocess, "run") as run:
                    producer.build_direct(root, target, fetch)
                argv = run.call_args.args[0]
                self.assertEqual(
                    [str(root), str(target), str(root / "dio-extender")], argv[-3:]
                )
                self.assertEqual(
                    producer.FETCH_SCRIPT if fetch else producer.NATIVE_SCRIPT,
                    argv[2],
                )
                self.assertNotIn(str(root), argv[2])

    def test_fetch_does_not_build_or_package(self):
        spec = importlib.util.spec_from_file_location(
            "release_builder", Path(__file__).with_name("build-release.py")
        )
        assert spec and spec.loader
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(bundle, "git", return_value=""):
                command = producer.container_command(
                    "engine", root, None, root / "target", root / "dio", True
                )
            self.assertEqual(producer.FETCH_SCRIPT, command[-5])
            self.assertNotIn("public-build.py", command[-5])
            self.assertNotIn("scripts/bundle.py", command[-5])


if __name__ == "__main__":
    bundle.identities(Path(__file__).resolve().parents[1])
    unittest.main()
