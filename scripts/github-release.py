#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Create a GitHub release and upload the install bundle."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


def publish(repository: str, tag: str, token: str, bundle: Path) -> None:
    """Create the tag release, then upload its ZIP through the returned URL."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("invalid GitHub repository")
    if not tag.startswith("v") or not token:
        raise ValueError("a version tag and release token are required")
    payload = bundle.read_bytes()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/releases",
        data=json.dumps(
            {
                "tag_name": tag,
                "name": tag,
                "body": "Read INSTALL.md and the qualification limits in the bundle.",
            }
        ).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        release = json.load(response)
    upload_url = release["upload_url"].split("{", 1)[0]
    parsed = urllib.parse.urlsplit(upload_url)
    if parsed.scheme != "https" or parsed.netloc != "uploads.github.com":
        raise ValueError("unexpected GitHub asset upload URL")
    upload_url += "?" + urllib.parse.urlencode({"name": bundle.name})
    request = urllib.request.Request(
        upload_url,
        data=payload,
        headers=dict(headers, **{"Content-Type": "application/zip"}),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        asset = json.load(response)
    if asset.get("size") != len(payload) or asset.get("state") != "uploaded":
        raise RuntimeError("GitHub did not confirm the complete uploaded asset")
    print(f"Uploaded {bundle.name} for {tag}")


def main() -> None:
    if os.environ.get("GITHUB_SERVER_URL") != "https://github.com":
        raise ValueError("release uploads are supported on GitHub only")
    publish(
        os.environ["GH_REPO"],
        os.environ["TAG"],
        os.environ["GH_TOKEN"],
        Path("build/mib2-extenders.zip"),
    )


if __name__ == "__main__":
    main()
