# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 korhojoa
"""Check folder preparation and refusal before a startup file is generated."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "prepare_install", Path(__file__).with_name("prepare-install.py")
)
assert SPEC and SPEC.loader
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)
STOCK = "J9=/bin/true\nVMOPTIONS=\nBOOTCLASSPATH=\nHMI_JXE=stock.jxe\n$J9 $VMOPTIONS $BOOTCLASSPATH -jxe $HMI_JXE &\n"


class PrepareTest(unittest.TestCase):
    def fixture(self, root):
        card = root / "card"
        data = {
            "lsd-extender/lsd-extender.conf": "spawn sh /original/lsd-extender/mount-vaa.sh\nspawn sh /original/lsd-extender/run-native-aa-creds.sh\nprop lsdextender.carplay.config=auto\n",
            "lsd-extender/run-native-aa-creds.sh": "#!/bin/sh\nPUBLISHER=/original/lsd-extender/aawg-creds\nSHIM=/original/lsd-extender/libgal_btshim.so\n",
            "lsd-extender/mount-vaa.sh": '#!/bin/sh\nvaa_mount() {\n  SO="${VAA_SO:-}"\n}\n',
            "lsd-extender/native-aa-kit/btstack": "#!/bin/sh\n# Exact compatibility marker.\nL=/original/lsd-extender/libgal_btshim.so\nexec vendor\n",
            "lsd-extender/native-aa-kit/SHA256SUMS": "unused  btstack\n",
            "gal-extender/gal_loader.conf": "cluster\n",
            "lsd-extender/aawg-creds": "exact native fixture",
        }
        for name, text in data.items():
            path = card / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        stock = root / "lsd.sh.original"
        stock.write_text(STOCK)
        return card, stock

    def test_three_install_folders_and_native_bytes_unchanged(self):
        for folder in (
            "/fs/sda0/extenders",
            "/fs/sdb0/software/extenders",
            "/data/extenders",
        ):
            with (
                self.subTest(folder=folder),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                card, stock = self.fixture(root)
                out = root / "prepared"
                prepare.prepare(card, stock, folder, out)
                conf = (out / "card/lsd-extender/lsd-extender.conf").read_text()
                self.assertIn(folder + "/lsd-extender/mount-vaa.sh", conf)
                self.assertIn(folder + "/gal-extender/gal_loader.conf", conf)
                self.assertEqual(
                    (card / "lsd-extender/aawg-creds").read_bytes(),
                    (out / "card/lsd-extender/aawg-creds").read_bytes(),
                )
                self.assertIn(
                    STOCK.splitlines()[-1], (out / "lsd.sh.prepared").read_text()
                )
                self.assertIn(
                    "${VAA_SO:-" + folder,
                    (out / "card/lsd-extender/mount-vaa.sh").read_text(),
                )
                self.assertEqual(
                    (card / "lsd-extender/native-aa-kit/btstack")
                    .read_text()
                    .splitlines()[:2],
                    (out / "card/lsd-extender/native-aa-kit/btstack")
                    .read_text()
                    .splitlines()[:2],
                )
                self.assertEqual(
                    json.loads((out / "PREPARED.json").read_text())["install_folder"],
                    folder,
                )

    def test_absent_jar_and_failed_wait_keep_stock_boot_available(self):
        script = (
            "set -eu\nBOOTCLASSPATH=\nVMOPTIONS=\nwaitfor() { return 1; }\n"
            + prepare.startup_block("/no-such-owned-install-folder")
            + "echo stock-continues\n"
        )
        result = subprocess.run(
            ["sh", "-c", script], capture_output=True, text=True, timeout=5
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "stock-continues\n")

    def test_shell_characters_relative_paths_and_parent_paths_refuse(self):
        for path in ("relative", "/", "/a/../b", "/a b", "/a;false", "/a/$(false)"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare.install_folder(path)

    def test_unknown_or_duplicate_startup_hook_refuses(self):
        for text in (
            STOCK + STOCK,
            STOCK + "# extendedStartupSPI.class\n",
            STOCK.replace("$J9 ", "# $J9 "),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                prepare.launcher(text, "/data/extenders")

    def test_source_symlink_and_nested_output_refuse_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            card, stock = self.fixture(root)
            (card / "alias").symlink_to("lsd-extender/aawg-creds")
            out = root / "prepared"
            with self.assertRaisesRegex(ValueError, "Linked"):
                prepare.prepare(card, stock, "/data/extenders", out)
            self.assertFalse(out.exists())
            (card / "alias").unlink()
            with self.assertRaisesRegex(ValueError, "inside"):
                prepare.prepare(card, stock, "/data/extenders", card / "prepared")
            self.assertFalse((card / "prepared").exists())


if __name__ == "__main__":
    unittest.main()
