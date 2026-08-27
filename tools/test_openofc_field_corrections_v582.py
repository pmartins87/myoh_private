from __future__ import annotations

import math
from pathlib import Path

from openofc_tablemap_identity import validate_v552_semantic_contract


ROOT = Path(__file__).resolve().parents[1]

T14 = [
    (29.5,693.5),(55.5,684.5),(83.0,677.0),(110.5,671.0),
    (138.5,666.0),(168.0,663.0),(196.0,661.5),(224.5,660.5),
    (253.0,662.0),(281.5,663.5),(307.5,669.0),(337.0,671.0),
    (366.0,677.0),(394.0,684.0),
]
T15 = [
    (29.5,693.5),(55.0,685.5),(79.5,678.5),(105.0,672.0),
    (131.0,668.0),(157.0,664.0),(183.5,662.0),(210.5,661.0),
    (237.0,661.0),(263.5,661.5),(289.5,664.5),(316.0,667.0),
    (341.5,672.0),(368.5,677.0),(392.5,684.0),
]

# Exact anchor centers reproduced from the current C++ LocateDynamicAnchors
# algorithm on the two 2026-08-25 field BMPs supplied with the v5.8.1 failure.
# They deliberately preserve the detector's miss instead of hand-correcting it.
FIELD_F15_FRAME000000_ANCHORS = [
    (30.0,693.5),(53.5,684.5),(79.0,678.0),(103.5,672.0),
    (130.0,667.5),(157.5,664.5),(183.5,662.0),(210.5,661.0),
    (236.5,661.0),(263.0,662.0),(289.5,664.5),(314.5,667.5),
    (341.0,672.0),(368.5,676.5),
]
FIELD_F15_FRAME000003_ANCHORS = [
    (55.0,685.0),(79.5,677.5),(105.0,672.0),(129.5,667.5),
    (157.5,664.5),(184.0,662.0),(210.5,661.0),(236.5,661.0),
    (263.5,662.0),(288.5,664.5),(315.5,668.0),(341.0,672.5),
    (368.5,677.0),(392.5,684.0),
]


def bounded_alignment(observed, expected):
    """Python mirror of the C++ v5.8.2 count correspondence contract."""
    max_missing = 1
    max_extra = 2
    inf = float("inf")
    dp = {(0, 0, 0, 0): 0.0}
    for a in range(len(observed) + 1):
        for e in range(len(expected) + 1):
            for missing in range(max_missing + 1):
                for extra in range(max_extra + 1):
                    key = (a, e, missing, extra)
                    current = dp.get(key, inf)
                    if not math.isfinite(current):
                        continue
                    if a < len(observed) and e < len(expected):
                        dx = observed[a][0] - expected[e][0]
                        dy = observed[a][1] - expected[e][1]
                        nxt = (a + 1, e + 1, missing, extra)
                        dp[nxt] = min(dp.get(nxt, inf), current + dx*dx + 0.5*dy*dy)
                    if e < len(expected) and missing < max_missing:
                        nxt = (a, e + 1, missing + 1, extra)
                        dp[nxt] = min(dp.get(nxt, inf), current)
                    if a < len(observed) and extra < max_extra:
                        nxt = (a + 1, e, missing, extra + 1)
                        dp[nxt] = min(dp.get(nxt, inf), current)
    best = inf
    for missing in range(max_missing + 1):
        for extra in range(max_extra + 1):
            squared = dp.get((len(observed), len(expected), missing, extra), inf)
            matched = len(expected) - missing
            if not math.isfinite(squared) or matched <= 0 or matched != len(observed) - extra:
                continue
            score = math.sqrt(squared / matched) + 2.5 * missing + 6.0 * extra
            best = min(best, score)
    return best


def test_one_missing_f15_anchor_is_not_forced_to_f14() -> None:
    for missing in range(len(T15)):
        observed = T15[:missing] + T15[missing + 1:]
        f15 = bounded_alignment(observed, T15)
        f14 = bounded_alignment(observed, T14)
        assert f15 <= 8.0, (missing, f15, f14)
        assert f14 - f15 >= 3.0, (missing, f15, f14)


def test_exact_field_replay_anchors_choose_f15() -> None:
    cases = (
        (FIELD_F15_FRAME000000_ANCHORS, 3.3660254037844384, 15.551756905801442),
        (FIELD_F15_FRAME000003_ANCHORS, 3.1614378277661475, 15.523024373951285),
    )
    for observed, expected_f15, expected_f14 in cases:
        f15 = bounded_alignment(observed, T15)
        f14 = bounded_alignment(observed, T14)
        assert abs(f15 - expected_f15) < 1e-12, (f15, expected_f15)
        assert abs(f14 - expected_f14) < 1e-12, (f14, expected_f14)
        assert f15 <= 8.0
        assert f14 - f15 >= 3.0


def test_exact_f14_stays_f14() -> None:
    f14 = bounded_alignment(T14, T14)
    f15 = bounded_alignment(T14, T15)
    assert f14 == 0.0
    assert f15 - f14 >= 3.0


def test_materialized_source_contract() -> None:
    recognizer = (ROOT / "OpenHoldem/COFCFantasy15PixelRecognizer.cpp").read_text(
        encoding="utf-8-sig"
    )
    scraper = (ROOT / "OpenHoldem/COFCScraper.cpp").read_text(encoding="utf-8-sig")
    runtime = (ROOT / "OpenHoldem/COFCRuntimeController.cpp").read_text(
        encoding="utf-8-sig"
    )
    assert "OPENOFC_V582_BOUNDED_COUNT_ALIGNMENT" in recognizer
    assert "kFantasyCountMaxMissingAnchors = 1" in recognizer
    assert "kFantasyCountMaxExtraAnchors = 2" in recognizer
    assert "OPENOFC_V582_EMPTY_ARRANGEMENT_BOOTSTRAP" in scraper
    assert "bootstrap arrangement=EMPTY identity_scan=SKIPPED" in scraper
    assert "RecognizeArrangementOccupancy" in scraper
    assert "OPENOFC_V582_FANTASY_NEW_HAND_RELEASE" in runtime
    assert "fantasy_count >= 14 && fantasy_count <= 17" in runtime
    gate = runtime.split("OPENOFC_V582_FANTASY_NEW_HAND_RELEASE", 1)[1].split(
        "return (initial_normal", 1
    )[0]
    assert "PendingCount(state) == 0" not in gate
    assert "board.CountKnownCards() == 0" in gate


def test_paired_tablemap_semantic_contract() -> None:
    identity = validate_v552_semantic_contract()
    assert identity["stage"] == "openofc_v5_5_2_fantasy_live_recovery"
    assert identity["contract"] == 5
    assert identity["field_revision"] == 552
    assert int(identity["regions"]) >= 250


def main() -> None:
    test_one_missing_f15_anchor_is_not_forced_to_f14()
    test_exact_field_replay_anchors_choose_f15()
    test_exact_f14_stays_f14()
    test_materialized_source_contract()
    test_paired_tablemap_semantic_contract()
    print(
        "OPENOFC_V582_FIELD_REGRESSION=PASS "
        "field_f15_anchors=RECOVERED synthetic_f15=RECOVERED exact_f14=PRESERVED "
        "empty_bootstrap=OCCUPANCY_FIRST runtime=F14_17_RELEASE "
        "tablemap=V552_SEMANTIC_CONTRACT_VALID"
    )


if __name__ == "__main__":
    main()
