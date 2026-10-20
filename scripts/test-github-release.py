#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Check release requests without network access or credentials."""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "github_release", Path(__file__).with_name("github-release.py")
)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def response(data):
    return io.BytesIO(json.dumps(data).encode())


class ReleaseTest(unittest.TestCase):
    def test_create_then_upload_exact_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "mib2-extenders.zip"
            payload = b"constructed ZIP bytes"
            bundle.write_bytes(payload)
            with patch.object(
                release.urllib.request,
                "urlopen",
                side_effect=[
                    response(
                        {
                            "upload_url": "https://uploads.github.com/repos/owner/repo/releases/1/assets{?name,label}"
                        }
                    ),
                    response({"size": len(payload), "state": "uploaded"}),
                ],
            ) as network:
                release.publish("owner/repo", "v1.2.3", "test-token", bundle)
            create, upload = [call.args[0] for call in network.call_args_list]
            self.assertEqual("POST", create.method)
            self.assertEqual(
                "https://api.github.com/repos/owner/repo/releases", create.full_url
            )
            self.assertEqual("v1.2.3", json.loads(create.data)["tag_name"])
            self.assertEqual("Bearer test-token", create.get_header("Authorization"))
            self.assertEqual(
                "https://uploads.github.com/repos/owner/repo/releases/1/assets?name=mib2-extenders.zip",
                upload.full_url,
            )
            self.assertEqual(payload, upload.data)
            self.assertEqual("application/zip", upload.get_header("Content-type"))

    def test_refuses_foreign_upload_host(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle.zip"
            bundle.write_bytes(b"fixture")
            with patch.object(
                release.urllib.request,
                "urlopen",
                return_value=response({"upload_url": "https://example.com/assets"}),
            ) as network:
                with self.assertRaisesRegex(ValueError, "unexpected GitHub"):
                    release.publish("owner/repo", "v1", "test-token", bundle)
            self.assertEqual(1, network.call_count)

    def test_failed_create_never_uploads(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle.zip"
            bundle.write_bytes(b"fixture")
            with patch.object(
                release.urllib.request,
                "urlopen",
                side_effect=OSError("fixture failure"),
            ) as network:
                with self.assertRaises(OSError):
                    release.publish("owner/repo", "v1", "test-token", bundle)
            self.assertEqual(1, network.call_count)

    def test_forgejo_is_refused_before_network(self):
        with (
            patch.dict(os.environ, {"GITHUB_SERVER_URL": "https://example.com"}),
            patch.object(release.urllib.request, "urlopen") as network,
        ):
            with self.assertRaisesRegex(ValueError, "GitHub only"):
                release.main()
        network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
