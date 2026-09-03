#!/usr/bin/env python3
"""Derive the inert P3 shadow TableMap from the frozen v5.5.2 recognizer map."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = "28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6"

REPLACEMENTS = {
    b"s$ofc_executor_enabled      1": b"s$ofc_executor_enabled      0",
    b"s$ofc_tablemap_stage        openofc_v5_5_2_fantasy_live_recovery": (
        b"s$ofc_tablemap_stage        openofc_v5_5_3_p3_shadow"
    ),
    b"s$openofc_contract          5": (
        b"s$openofc_contract          5\n"
        b"s$openofc_p3_shadow_only    1"
    ),
    b"s$openofc_field_revision    552": b"s$openofc_field_revision    553",
}


def build(source: Path, output: Path) -> bytes:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("P3 TableMap source differs from frozen v5.5.2 identity")
    result = raw
    for before, after in REPLACEMENTS.items():
        if result.count(before) != 1:
            raise ValueError(f"P3 TableMap expected exactly one marker: {before!r}")
        result = result.replace(before, after)
    result = result.rstrip(b"\r\n") + b"\n"
    if b"s$ofc_executor_enabled      1" in result:
        raise ValueError("P3 shadow TableMap retained physical executor authority")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.output)
    print(f"OPENOFC_P3_SHADOW_TABLEMAP={args.output}")
    print(f"OPENOFC_P3_SHADOW_TABLEMAP_SHA256={hashlib.sha256(result).hexdigest()}")


if __name__ == "__main__":
    main()
