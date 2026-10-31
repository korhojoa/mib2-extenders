# SPDX-License-Identifier: GPL-3.0-only
"""Release controls for changed files, class membership and source state."""

import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "release_build", Path(__file__).with_name("build-release.py")
)
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseControls(unittest.TestCase):
    def test_native_bytes_must_equal_the_released_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native"
            path.write_bytes(b"released")
            expected = {"bytes": 8, "sha256": hashlib.sha256(b"released").hexdigest()}
            self.assertEqual(release.checked_payload(path, expected), b"released")
            path.write_bytes(b"changed!")
            with self.assertRaisesRegex(ValueError, "differs"):
                release.checked_payload(path, expected)

    def test_linked_native_output_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real").write_bytes(b"native")
            (root / "link").symlink_to("real")
            with self.assertRaisesRegex(ValueError, "regular"):
                release.checked_payload(root / "link", {})

    def java_file(self, path, members, compression=zipfile.ZIP_STORED):
        with zipfile.ZipFile(path, "w", compression=compression) as archive:
            for name, data in members:
                archive.writestr(name, data)

    def test_java_compression_can_differ_but_class_bytes_cannot(self):
        name = "org/korho/lsdextender/Example.class"
        data = b"owned class bytes for a checksum boundary test"
        expected = {"classes": {name: hashlib.sha256(data).hexdigest()}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owned.jar"
            for compression in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                self.java_file(path, [(name, data)], compression)
                release.checked_payload(path, expected)
            self.java_file(path, [(name, data + b"changed")])
            with self.assertRaisesRegex(ValueError, "class bytes"):
                release.checked_payload(path, expected)

    def test_extra_stock_class_or_duplicate_member_is_refused(self):
        name = "org/korho/lsdextender/Example.class"
        data = b"owned class checksum fixture"
        expected = {"classes": {name: hashlib.sha256(data).hexdigest()}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owned.jar"
            self.java_file(
                path, [(name, data), ("org/dsi/Stock.class", b"not allowed")]
            )
            with self.assertRaisesRegex(ValueError, "membership"):
                release.checked_payload(path, expected)
            with self.assertWarns(UserWarning):
                self.java_file(path, [(name, data), (name, data)])
            with self.assertRaisesRegex(ValueError, "membership"):
                release.checked_payload(path, expected)

    def test_install_links_cannot_point_outside_the_archive(self):
        files = {
            name: b""
            for name in (
                "README.md",
                "INSTALL.md",
                "LICENSES.md",
                "docs/TERMS.md",
                "docs/SETTINGS.md",
            )
        }
        files["README.md"] = b"[Settings](docs/SETTINGS.md#output-selection)\n"
        files["docs/TERMS.md"] = b"[README](../README.md)\n"
        release.bundle.check_guide_links(files)
        del files["docs/SETTINGS.md"]
        with self.assertRaisesRegex(ValueError, "Missing install document"):
            release.bundle.check_guide_links(files)
        files["docs/SETTINGS.md"] = b"[Missing](not-in-package.md)\n"
        with self.assertRaisesRegex(ValueError, "Broken install link"):
            release.bundle.check_guide_links(files)

    def test_public_plan_has_complete_unique_outputs(self):
        sources, expected = release.check_sources()
        outputs = [
            name for part in sources["parts"].values() for name in part["outputs"]
        ]
        self.assertEqual(set(outputs), set(expected["files"]))
        self.assertEqual(len(outputs), len(set(outputs)))

    def test_only_loaded_java_archives_enter_the_install_tree(self):
        sources, _ = release.documents()
        jars = {
            Path(name).name
            for name in sources["parts"]["java"]["outputs"]
            if name.endswith(".jar")
        }
        self.assertEqual(
            jars,
            {
                "lsd-extender.jar",
                "lsd-extender-aa-guidance.jar",
                "lsd-extender-kombisync.jar",
                "lsd-extender-ev.jar",
                "lsd-extender-homeui.jar",
                "lsd-extender-wirelessaa.jar",
                "lsd-extender-aasettings.jar",
            },
        )

    def test_mirror_aliases_use_public_namespace_without_global_git_edits(self):
        with patch.dict(
            "os.environ",
            {
                "GITHUB_SERVER_URL": "https://forge.example",
                "GITHUB_REPOSITORY": "public/mib2-extenders",
            },
            clear=True,
        ):
            env = release.git_environment({})
        self.assertEqual(
            env["GIT_CONFIG_KEY_0"], "url.https://forge.example/public/.insteadOf"
        )
        self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
        sources, _ = release.documents()
        self.assertEqual(
            sources["parts"]["driver"]["url"],
            "https://github.com/korhojoa/qnx650-rpi-drivers.git",
        )
        self.assertNotIn("mirror_path", sources["parts"]["driver"])

    def test_source_change_is_refused_by_real_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "source").write_text("original\n")
            subprocess.run(["git", "add", "source"], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Release test",
                    "-c",
                    "user.email=release@example.invalid",
                    "commit",
                    "-qm",
                    "Fixture",
                ],
                cwd=root,
                check=True,
            )
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            release.source_clean(root, commit)
            (root / "source").write_text("changed\n")
            with self.assertRaises(subprocess.CalledProcessError):
                release.source_clean(root, commit)

    def test_missing_part_cannot_make_an_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "Missing"):
                release.package(root / "parts", root / "wireless.zip")
            self.assertFalse((root / "wireless.zip").exists())

    def test_manifest_keeps_the_real_core_banner(self):
        sources, expected = release.documents()
        payloads = {
            "lsd-extender/core-build.properties": b"core_id=example\n",
            "lsd-extender/lsd-extender.jar": b"owned",
        }
        text = release.manifest(payloads, expected, sources).decode()
        self.assertIn("lsd-extender/lsd-extender.jar  = bundle of: core", text)
        self.assertIn("  lsd-extender-core 2.3.2+522 built=", text)
        self.assertNotIn("lsd-extender-core v0", text)

    def test_paths_cannot_escape(self):
        for name in ("../outside", "/absolute", "inside/../outside"):
            with self.assertRaises(ValueError):
                release.relative(name)


if __name__ == "__main__":
    unittest.main()
