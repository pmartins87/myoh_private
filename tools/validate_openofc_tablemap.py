from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED_INT_SYMBOLS = {
    "ofc_drag_targets_calibrated": 1,
    "ofc_executor_enabled": 1,
    "ofc_fantasy15_geometry_measured": 1,
    "ofc_fantasy_recognizer_calibrated": 1,
    "ofc_joker_detector_calibrated": 1,
}


def parse_tm(path: Path):
    symbols = {}
    regions = []
    target_size = None
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("z$targetsize"):
            parts = line.split()
            if len(parts) >= 3:
                target_size = (int(parts[1]), int(parts[2]))
        elif line.startswith("s$"):
            parts = line.split(None, 1)
            key = parts[0][2:]
            val = parts[1].strip() if len(parts) > 1 else ""
            symbols[key] = val
        elif line.startswith("r$"):
            parts = line.split()
            if len(parts) >= 8:
                name = parts[0][2:]
                transform = parts[7]
                regions.append((lineno, name, transform, raw))
    return target_size, symbols, regions


def is_ofc_identity_region(name: str) -> bool:
    # OpenOFC card perception is deliberately Tn-only, but player identity is a
    # separate passive evidence channel. Explicit OFC-native name regions may
    # therefore use AutoOCR without weakening the card-recognition contract.
    return re.fullmatch(r"ofc_p\d+_name", name) is not None


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate OpenOFC TableMap perception contract")
    ap.add_argument("tablemap", type=Path)
    ap.add_argument("--require-contract", type=int, default=None)
    args = ap.parse_args()

    target, symbols, regions = parse_tm(args.tablemap)
    errors = []
    notes = []

    if target != (450, 830):
        errors.append(f"target size must be 450x830, got {target}")
    if symbols.get("ofc_variant") != "joker_ultimate":
        errors.append(f"ofc_variant must be joker_ultimate, got {symbols.get('ofc_variant')!r}")
    for key, expected in REQUIRED_INT_SYMBOLS.items():
        try:
            got = int(symbols.get(key, ""))
        except ValueError:
            got = None
        if got != expected:
            errors.append(f"s${key} must be {expected}, got {symbols.get(key)!r}")

    if args.require_contract is not None:
        try:
            got = int(symbols.get("openofc_contract", ""))
        except ValueError:
            got = None
        if got != args.require_contract:
            errors.append(f"s$openofc_contract must be {args.require_contract}, got {symbols.get('openofc_contract')!r}")

    ofc_text = []
    ofc_autoocr_forbidden = []
    ofc_identity_autoocr = []
    legacy_autoocr = []
    for lineno, name, transform, raw in regions:
        is_ofc = name.startswith("ofc_")
        is_rank_suit = name.endswith("rank") or name.endswith("suit")
        if is_ofc and is_rank_suit:
            ofc_text.append((lineno, name, transform))
            if not re.fullmatch(r"T\d+", transform):
                errors.append(f"line {lineno}: {name} must use Tn text transform, got {transform}")
        if is_ofc and transform.startswith("A"):
            if is_ofc_identity_region(name):
                ofc_identity_autoocr.append((lineno, name, transform))
            else:
                ofc_autoocr_forbidden.append((lineno, name, transform))
        if not is_ofc and transform.startswith("A"):
            legacy_autoocr.append((lineno, name, transform))

    if ofc_autoocr_forbidden:
        errors.append(
            "OFC card/gameplay regions contain AutoOCR transforms: "
            + ", ".join(f"{n}:{t}" for _, n, t in ofc_autoocr_forbidden)
        )
    if not ofc_text:
        errors.append("no OFC rank/suit text-transform regions found")

    if ofc_identity_autoocr:
        notes.append(
            "OFC-native identity OCR regions are passive history evidence: "
            + ", ".join(f"{n}:{t}" for _, n, t in ofc_identity_autoocr)
        )
    if legacy_autoocr:
        notes.append(
            "legacy non-OFC AutoOCR regions exist but are outside the OpenOFC path: "
            + ", ".join(f"{n}:{t}" for _, n, t in legacy_autoocr)
        )

    print(f"TableMap: {args.tablemap}")
    print(f"target={target} variant={symbols.get('ofc_variant')} OFC rank/suit regions={len(ofc_text)}")
    used = sorted({t for _, _, t in ofc_text})
    print("OFC text transforms: " + ", ".join(used))
    for note in notes:
        print("NOTE:", note)
    if errors:
        for e in errors:
            print("ERROR:", e)
        return 1
    print("PASS: OpenOFC card recognition is Tn text-transform based; only explicit OFC identity regions may use AutoOCR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
