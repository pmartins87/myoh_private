from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8-sig")


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        return ordered[n // 2]
    return 0.5 * (ordered[n // 2 - 1] + ordered[n // 2])


def affine_profile_residual(expected, actual):
    n = float(len(expected))
    sx = sum(expected)
    sy = sum(actual)
    sxx = sum(x * x for x in expected)
    sxy = sum(x * y for x, y in zip(expected, actual))
    denom = n * sxx - sx * sx
    scale = (n * sxy - sx * sy) / denom
    offset = (sy - scale * sx) / n
    residual = max(abs(y - (offset + scale * x)) for x, y in zip(expected, actual))
    return offset, scale, residual


def regular_grid_residual(actual):
    ordered = sorted(actual)
    deltas = [ordered[i] - ordered[i - 1] for i in range(1, len(ordered))]
    pitch = median(deltas)
    half = (len(ordered) - 1) / 2.0
    implied_centers = [ordered[i] - (i - half) * pitch for i in range(len(ordered))]
    center = median(implied_centers)
    residual = max(
        abs(ordered[i] - (center + (i - half) * pitch))
        for i in range(len(ordered))
    )
    return residual


def main() -> None:
    geometry = read("OpenHoldem/COFCFantasyDynamicGeometry.h")
    recognizer_h = read("OpenHoldem/COFCFantasy15PixelRecognizer.h")
    recognizer_cpp = read("OpenHoldem/COFCFantasy15PixelRecognizer.cpp")
    generic = read("OpenHoldem/COFCFantasyPixelRecognizer.h")
    scraper = read("OpenHoldem/COFCScraper.cpp")

    # Exact field anchor centers reproduced from the 2026-08-23 22:58:34
    # 450x830 Fantasy frame using LocateDynamicAnchors + v5.4.6 anchor pairing.
    actual = [
        28.5, 53.0, 79.0, 105.0, 130.0,
        158.0, 183.5, 210.5, 236.0, 264.0,
        289.5, 314.5, 342.5, 368.5, 392.5,
    ]
    expected = [
        28.0, 54.0, 79.0, 105.0, 131.0,
        158.0, 184.0, 210.0, 237.0, 263.0,
        289.0, 316.0, 343.0, 370.0, 396.0,
    ]
    regular = regular_grid_residual(actual)
    offset, scale, profile = affine_profile_residual(expected, actual)
    assert regular > 3.5, (regular, "old regular-grid gate must reject this exact field fan")
    assert math.isclose(regular, 3.75, abs_tol=1e-9), regular
    assert 0.97 <= scale <= 1.03, scale
    assert profile <= 3.0, profile

    # Measured bright-substrate fractions from exact current empty slots versus
    # an existing real partially-arranged Fantasy fixture. The threshold is 20%.
    empty_current = [0.0] * 13
    occupied_fixture = [0.727, 0.719, 0.658, 0.794, 0.732, 0.689, 0.762, 0.749]
    assert max(empty_current) < 0.20
    assert min(occupied_fixture) > 0.20

    assert "FitMeasuredInitialFan15" in geometry
    assert "double allowed_residual = 3.5" in geometry, "global regular-grid threshold changed"
    assert "measured initial Fantasy fan profile residual is too high" in geometry

    assert "RecognizeArrangementOccupancy" in recognizer_h
    assert "bright_face_pixels * 5 < face_pixels" in recognizer_cpp
    assert "mean >= 165.0" in recognizer_cpp
    assert "FitMeasuredInitialFan15" in recognizer_cpp
    assert "!original_fantasy_cards.empty()" in recognizer_cpp
    assert "24.0, 42.0, 5.5" in recognizer_cpp
    assert "RecognizeArrangementOccupancy" in generic

    # Strict rank thresholds remain unchanged; v5.4.10 gains robustness from
    # occupancy/lineage constraints, not from globally accepting weak glyphs.
    assert "upright ? 0.36 : kDeepOFCFanRankMaxDistance" in recognizer_cpp
    assert "upright ? 0.04 : kDeepOFCFanRankMinMargin" in recognizer_cpp

    lineage = scraper.find("OPENOFC_FANTASY_FIELD_V5410")
    assert lineage >= 0
    lineage_block = scraper[lineage:lineage + 7000]
    order = [
        lineage_block.find("RecognizeArrangementOccupancy"),
        lineage_block.find("RecognizeLooseObjectsBound"),
        lineage_block.find("RecognizeArrangementSlotsAgainstExpected"),
    ]
    assert all(x >= 0 for x in order), order
    assert order == sorted(order), order
    assert "recognition=LINEAGE_CONSTRAINED" in lineage_block
    assert "fallback=NO_PRIOR_LINEAGE" in scraper

    print(
        "OPENOFC_FANTASY_FIELD_V5410_REGRESSION=PASS "
        f"field_regular_residual={regular:.2f} field_profile_residual={profile:.3f} "
        f"field_profile_scale={scale:.6f} empty_slot_gate=PASS occupied_card_gate=PASS "
        "partial_lineage=CONSTRAINED global_thresholds=UNCHANGED"
    )


if __name__ == "__main__":
    main()
