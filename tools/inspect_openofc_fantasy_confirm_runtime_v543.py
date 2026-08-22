from __future__ import annotations

import base64
import gzip
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
HDR = ROOT / "OpenHoldem" / "COFCRuntimeController.h"
TABLEMAP_TRANSPORT = ROOT / "OpenOFC" / "TableMaps" / "KKPoker_OpenOFC_JokerUltimate_v3.tm.gz.b64"
TABLEMAP = ROOT / "OpenOFC" / "TableMaps" / "KKPoker_OpenOFC_JokerUltimate_v3.tm"
TABLEMAP_VALIDATOR = ROOT / "tools" / "validate_openofc_tablemap.py"
TABLEMAP_SHA256 = "dcefdee38ed8f628fe07e364885591540c223b53f54d6f4fc474b7b16569daa3"


def extract_method(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"method signature not found: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"opening brace not found: {signature}")
    depth = 0
    i = brace
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    raise RuntimeError(f"unterminated method: {signature}")


def materialize_and_validate_canonical_tablemap() -> None:
    """Materialize the hash-pinned v3 TableMap from its canonical transport.

    The repository intentionally stores the TableMap as gzip+Base64.  The final
    integrated release gate packages the losslessly reconstructed .tm, so the
    integration inspection step also enforces the exact transport, structural
    contract and SHA-256 before any release artifact can be assembled.
    """
    if not TABLEMAP_TRANSPORT.is_file():
        raise RuntimeError(f"canonical TableMap transport missing: {TABLEMAP_TRANSPORT}")
    if not TABLEMAP_VALIDATOR.is_file():
        raise RuntimeError(f"TableMap validator missing: {TABLEMAP_VALIDATOR}")

    encoded = "".join(TABLEMAP_TRANSPORT.read_text(encoding="utf-8-sig").split())
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError(f"canonical TableMap Base64 transport is invalid: {exc}") from exc
    try:
        raw = gzip.decompress(compressed)
    except Exception as exc:
        raise RuntimeError(f"canonical TableMap gzip transport is invalid: {exc}") from exc

    actual = hashlib.sha256(raw).hexdigest()
    if actual != TABLEMAP_SHA256:
        raise RuntimeError(
            "canonical TableMap SHA-256 mismatch: "
            f"expected={TABLEMAP_SHA256} actual={actual}"
        )

    TABLEMAP.write_bytes(raw)
    result = subprocess.run(
        [sys.executable, str(TABLEMAP_VALIDATOR), str(TABLEMAP), "--require-contract", "3"],
        cwd=str(ROOT),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"canonical TableMap structural validation failed: {result.returncode}")

    text = raw.decode("utf-8", errors="replace")
    # TableMap symbols are whitespace-delimited, not single-space-delimited.
    # Mirror the historical release checks without weakening the semantic
    # contract: accept tabs/alignment spaces, but still require exact values.
    required_patterns = {
        "joker rank token X": r"(?m)^s\$ofc_joker_rank_token[ \t]+X[ \t]*\r?$",
        "partial slot tolerance": r"(?m)^s\$openofc_partial_slot_tolerance[ \t]+1[ \t]*\r?$",
        "partial opponent progression": r"(?m)^s\$openofc_opponent_partial_progression[ \t]+1[ \t]*\r?$",
        "Fantasy dynamic sources": r"(?m)^s\$openofc_fantasy_dynamic_sources[ \t]+1[ \t]*\r?$",
        "p0 timer region": r"(?m)^r\$ofc_p0_timer_active\b",
        "p1 timer region": r"(?m)^r\$ofc_p1_timer_active\b",
    }
    missing = [
        name for name, pattern in required_patterns.items()
        if re.search(pattern, text) is None
    ]
    if missing:
        raise RuntimeError(f"canonical TableMap markers missing: {missing}")
    if re.search(r"r\$ofc_.*joker[12]", text):
        raise RuntimeError("canonical TableMap still contains separate Joker identity regions")
    if not re.search(
        r"r\$ofc_p0_bottom2rank\s+191\s+242\s+205\s+260\s+ffffffff\s+-120\s+T5",
        text,
    ):
        raise RuntimeError("canonical TableMap p0_bottom2 rank-bank regression is not repaired to T5")

    # Re-hash the bytes on disk as a final protection against accidental
    # transformation while materializing the package input.
    disk_sha = hashlib.sha256(TABLEMAP.read_bytes()).hexdigest()
    if disk_sha != TABLEMAP_SHA256:
        raise RuntimeError(
            "materialized canonical TableMap changed on disk: "
            f"expected={TABLEMAP_SHA256} actual={disk_sha}"
        )
    print(f"CANONICAL_TABLEMAP_SHA256={disk_sha}")
    print("CANONICAL_TABLEMAP_V3=PASS")


def main() -> None:
    text = SRC.read_text(encoding="utf-8-sig")
    header = HDR.read_text(encoding="utf-8-sig")
    methods = [
        "void COFCRuntimeController::Recover(",
        "bool COFCRuntimeController::SendConfirm(",
        "bool COFCRuntimeController::StartDecision(",
        "bool COFCRuntimeController::AdvanceArrangement(",
        "bool COFCRuntimeController::HandlePostConfirm(",
        "void COFCRuntimeController::Tick(",
    ]
    for signature in methods:
        block = extract_method(text, signature)
        print(f"===== {signature} =====")
        print(block)
        print()

    required = [
        "kReacquire",
        "recovery_fingerprint_",
        "fantasy_executor_",
        "ofc_fantasy_confirm_button",
    ]
    combined = text + "\n" + header
    missing = [x for x in required if x not in combined]
    if missing:
        raise RuntimeError(f"missing runtime continuity/confirm markers: {missing}")
    if "kBlocked" in combined:
        raise RuntimeError("absorbing kBlocked survived materialized v5.4.3G runtime")

    print("CONFIRM_RUNTIME_INSPECTION=PASS")
    materialize_and_validate_canonical_tablemap()
    print("FIELD_PACKAGE_AUTHORIZED=0")


if __name__ == "__main__":
    main()
