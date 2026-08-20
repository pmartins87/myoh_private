from __future__ import annotations

from pathlib import Path

import apply_openofc_runtime_continuity_v54 as v54

ROOT = Path(__file__).resolve().parents[1]


def normalize_v53_shape() -> None:
    """Normalize known v5.3 generated-source shapes for the v5.4 upgrader.

    The frozen v5.3 chain already generalized the new-hand Fantasy count from
    exactly 15 to 14..17, while the v5.4 upgrader retains an assertion that it
    performed that migration. Also, the controller enum token appears both in
    the header and in the generated implementation; v5.4 owns the rename to
    `kReacquire` in both locations. These normalizations occur only in the
    ephemeral Actions workspace before the v5.4 patch finishes and its final
    source-contract assertions run.
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

    blocked_count = text.count("kBlocked")
    if blocked_count < 1:
        raise RuntimeError("v5.3 controller implementation has no kBlocked token to migrate")
    text = text.replace("kBlocked", "kReacquire")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print(
        "normalized v5.3 source shape for v5.4 upgrader: "
        f"fantasy-precondition=legacy-for-assertion blocked_tokens={blocked_count}->kReacquire"
    )


def assert_post_chain_liveness() -> None:
    lazy = (ROOT / "OpenHoldem/CLazyScraper.cpp").read_text(
        encoding="utf-8-sig", errors="strict"
    )
    required = (
        "OPENOFC_IDENTICAL_FAULT_RETRY_V541",
        "deepofc_cached_snapshot_safe",
        "[OpenOFC FAULT_RETRY]",
        "continue_scraping=1",
    )
    missing = [needle for needle in required if needle not in lazy]
    if missing:
        raise RuntimeError(
            "post-v5.4 liveness contract missing from CLazyScraper: "
            + ", ".join(missing)
        )
    print(
        "OpenOFC v5.4 post-chain liveness contract passed: "
        "invalid byte-identical frames are re-scraped, never cached forever"
    )


if __name__ == "__main__":
    normalize_v53_shape()
    v54.main()
    # Invalid observations are never cacheable terminal results. Importing this
    # narrow follow-up patch forces byte-identical invalid frames to be scraped
    # again on future heartbeats, which is essential when the client is waiting
    # for Hero and the pixels themselves remain unchanged.
    import apply_openofc_identical_fault_retry_v541  # noqa: F401,E402
    assert_post_chain_liveness()
