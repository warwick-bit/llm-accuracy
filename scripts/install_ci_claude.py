#!/usr/bin/env python3
"""Download a reviewed, pinned Claude binary without executing an installer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import urllib.request
from pathlib import Path

PINS = Path(__file__).with_name("ci_claude_pins.json")


def native_platform():
    os_name = {"Linux": "linux", "Darwin": "darwin", "Windows": "win32"}.get(
        platform.system()
    )
    arch = {"x86_64": "x64", "AMD64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        platform.machine()
    )
    return f"{os_name}-{arch}"


def verify_manifest(manifest, pins, target):
    expected = pins["platforms"].get(target)
    if expected is None:
        raise ValueError("ci_claude_platform_unsupported")
    if manifest["platforms"][target]["checksum"] != expected:
        raise ValueError("ci_claude_manifest_mismatch")
    return expected


def download(destination):
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    target = native_platform()
    base = pins["origin"] + "/" + pins["version"]
    with urllib.request.urlopen(base + "/manifest.json", timeout=30) as response:
        expected = verify_manifest(json.load(response), pins, target)
    filename = "claude.exe" if target.startswith("win32-") else "claude"
    destination.mkdir(parents=True, exist_ok=True)
    partial, output = destination / (filename + ".partial"), destination / filename
    digest = hashlib.sha256()
    try:
        with (
            urllib.request.urlopen(
                base + "/" + target + "/" + filename, timeout=60
            ) as response,
            partial.open("wb") as stream,
        ):
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("ci_claude_binary_mismatch")
        partial.chmod(0o700)
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    options = parser.parse_args(arguments)
    try:
        download(options.destination)
    except (OSError, ValueError, KeyError, TypeError) as error:
        allowed = {
            "ci_claude_platform_unsupported",
            "ci_claude_manifest_mismatch",
            "ci_claude_binary_mismatch",
        }
        label = (
            str(error)
            if isinstance(error, ValueError) and str(error) in allowed
            else "ci_claude_download_failed"
        )
        print(json.dumps({"status": "fail", "error": label}))
        return 1
    print(
        json.dumps(
            {"status": "pass", "version": "2.1.287", "platform": native_platform()}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
