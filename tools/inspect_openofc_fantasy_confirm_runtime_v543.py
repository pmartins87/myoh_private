from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
HDR = ROOT / "OpenHoldem" / "COFCRuntimeController.h"


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
    print("FIELD_PACKAGE_AUTHORIZED=0")


if __name__ == "__main__":
    main()
