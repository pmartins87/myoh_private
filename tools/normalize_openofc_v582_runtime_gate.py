from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    path = ROOT / "OpenHoldem/COFCRuntimeController.cpp"
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    marker = "OPENOFC_V582_FANTASY_NEW_HAND_RELEASE"
    if marker in text:
        print("OPENOFC_V582_RUNTIME_GATE_NORMALIZATION=ALREADY_FINAL")
        return

    start = text.find("bool COFCRuntimeController::IsKnownNewHand(")
    end = text.find("\n}\n", start)
    if start < 0 or end < 0:
        raise SystemExit("IsKnownNewHand function not found")
    end += 3
    function = text[start:end]
    pattern = r"  const bool initial_fantasy =.*?;\n"
    replacement = r'''  // OPENOFC_V582_FANTASY_NEW_HAND_RELEASE
  // A reconstructed fresh Fantasy state can already contain pending target
  // placements. New-hand identity therefore comes from an empty Hero board and
  // a legal F14..F17 packet; IncomingSignature keeps same-hand resets excluded.
  const int fantasy_count = state.hero_incoming_count;
  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1
    && state.players[state.hero_chair].board.CountKnownCards() == 0
    && fantasy_count >= 14 && fantasy_count <= 17;
'''
    updated_function, count = re.subn(
        pattern, lambda _m: replacement, function, count=1, flags=re.S
    )
    if count != 1:
        raise SystemExit(
            "IsKnownNewHand has no unique initial_fantasy semantic gate to normalize"
        )
    text = text[:start] + updated_function + text[end:]
    output = text if eol == "\n" else text.replace("\n", "\r\n")
    data = output.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print(
        "OPENOFC_V582_RUNTIME_GATE_NORMALIZATION=PASS "
        "fresh_fantasy=EMPTY_BOARD_F14_17 pending=IGNORED signature=PRESERVED"
    )


if __name__ == "__main__":
    main()
