#!/usr/bin/env python3
"""Integrity gate for OpenOFC HBITMAP v2 lossless crops.

The fixture files are derived directly from original replay BMPs. This verifier
checks exact byte identity before any Windows/GDI+/recognizer test is allowed to
run. It deliberately has no recovery or fuzzy mode.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

EXPECTED = {
    "frame000036_arrangement.png": {
        "bytes": 56386,
        "sha256": "826f786d8c5b47a2e85b1d0195626dff70cb0a9c031a90c254b8807f7bceca50",
    },
    "frame000036_loose.png": {
        "bytes": 49363,
        "sha256": "ce6a83ff71aca8cf3b760a50f0f42b46ceb8ced2365da4a1ec571078e9195524",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_openofc_hbitmap_v2_fixtures.py <fixture-dir>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    ok = True
    for name, spec in EXPECTED.items():
        path = root / name
        if not path.is_file():
            print(f"FAIL missing fixture: {path}", file=sys.stderr)
            ok = False
            continue
        size = path.stat().st_size
        digest = sha256(path)
        print(f"HBITMAP_V2_FIXTURE name={name} bytes={size} sha256={digest}")
        if size != spec["bytes"]:
            print(
                f"FAIL {name}: byte count {size} != {spec['bytes']}",
                file=sys.stderr,
            )
            ok = False
        if digest != spec["sha256"]:
            print(
                f"FAIL {name}: sha256 {digest} != {spec['sha256']}",
                file=sys.stderr,
            )
            ok = False

    if not ok:
        print("HBITMAP_V2_FIXTURE_GATE=FAIL", file=sys.stderr)
        return 1

    print("HBITMAP_V2_FIXTURE_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
