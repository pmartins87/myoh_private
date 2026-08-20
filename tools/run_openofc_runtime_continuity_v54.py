from __future__ import annotations

from pathlib import Path

import apply_openofc_runtime_continuity_v54 as v54

ROOT = Path(__file__).resolve().parents[1]


def normalize_v53_shape() -> None:
    """Normalize one already-fixed v5.3 source fragment for the v5.4 upgrader.

    `run_openofc_gameflow_v2.py` already generalized the new-hand Fantasy count
    from exactly 15 to 14..17. The v5.4 patch was intentionally written as an
    upgrader from the older literal source shape so it can assert the change.
    Recreate that one precondition in the ephemeral Actions workspace; the v5.4
    patch immediately writes the generic 14..17 form back. No committed/runtime
    source is downgraded and the final source contract asserts the generic form.
    """
    path = ROOT / "OpenHoldem/COFCRuntimeController.cpp"
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    generic = '''  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1 && PendingCount(state) == 0
    && state.hero_incoming_count >= 14 && state.hero_incoming_count <= 17;
'''
    legacy = '''  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1 && PendingCount(state) == 0
    && state.hero_incoming_count == 15;
'''
    if generic in text:
        text = text.replace(generic, legacy, 1)
    elif legacy not in text:
        raise RuntimeError("v5.3 initial_fantasy source shape is unknown")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print("normalized v5.3 initial_fantasy source shape for v5.4 upgrader")


if __name__ == "__main__":
    normalize_v53_shape()
    v54.main()
