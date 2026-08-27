from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANKS = ROOT / "OpenHoldem/COFCFantasyRecognizerBanks.generated.h"
RECOGNIZER = ROOT / "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
GEOMETRY = ROOT / "OpenHoldem/COFCFantasyDynamicGeometry.h"

GLYPH_W = 16
GLYPH_H = 24


def fail(message: str) -> None:
    raise AssertionError(message)


def parse_bank(text: str, name: str) -> list[tuple[str, tuple[int, ...]]]:
    m = re.search(
        rf"static const COFCRankTemplate\s+{re.escape(name)}\[\]\s*=\s*\{{(.*?)\n\}};",
        text,
        flags=re.S,
    )
    if not m:
        fail(f"bank not found/materialized as unsized array: {name}")
    body = m.group(1)
    entries: list[tuple[str, tuple[int, ...]]] = []
    for em in re.finditer(r"\{'(.)',\s*\{([^}]*)\}\}", body, flags=re.S):
        label = em.group(1)
        rows = tuple(int(x.strip()) for x in em.group(2).split(",") if x.strip())
        if len(rows) != GLYPH_H:
            fail(f"{name}/{label}: expected {GLYPH_H} rows, got {len(rows)}")
        entries.append((label, rows))
    if not entries:
        fail(f"no entries parsed from {name}")
    return entries


def popcount16(value: int) -> int:
    return int(value & 0xFFFF).bit_count()


def translate_rows(source: tuple[int, ...], dx: int, dy: int) -> tuple[int, ...]:
    out = [0] * GLYPH_H
    for sy in range(GLYPH_H):
        ty = sy + dy
        if ty < 0 or ty >= GLYPH_H:
            continue
        if dx >= 0:
            if dx >= GLYPH_W:
                continue
            out[ty] = (source[sy] << dx) & 0xFFFF
        else:
            if -dx >= GLYPH_W:
                continue
            out[ty] = (source[sy] >> (-dx)) & 0xFFFF
    return tuple(out)


def binary_union_xor_distance(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    xor_pixels = 0
    union_pixels = 0
    for a, b in zip(left, right):
        xor_pixels += popcount16(a ^ b)
        union_pixels += popcount16(a | b)
    return 0.0 if union_pixels == 0 else xor_pixels / union_pixels


def aligned_distance(observed: tuple[int, ...], reference: tuple[int, ...], max_shift: int = 2) -> float:
    best = math.inf
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            best = min(best, binary_union_xor_distance(observed, translate_rows(reference, dx, dy)))
    return best


def classify(
    observed: tuple[int, ...],
    bank: list[tuple[str, tuple[int, ...]]],
    max_distance: float,
    min_margin: float,
) -> tuple[str | None, float, float]:
    # Mirrors COFCFantasyRecognitionCore::ClassifyRank: multiple exemplars of
    # the same rank collapse to that rank's best distance before margin is
    # computed, so adding a same-rank exemplar cannot destroy the class margin.
    per_label: dict[str, float] = {}
    for label, rows in bank:
        d = aligned_distance(observed, rows, 2)
        per_label[label] = min(per_label.get(label, math.inf), d)
    ordered = sorted(per_label.items(), key=lambda kv: (kv[1], ord(kv[0])))
    if len(ordered) < 2:
        fail("classifier needs at least two rank classes")
    best_label, best = ordered[0]
    second = ordered[1][1]
    margin = second - best
    if best > max_distance or margin < min_margin:
        return None, best, margin
    return best_label, best, margin


FIELD_FAN = [
    ("K", (0,0,0,0,0,896,480,504,446,412,440,1008,2016,1504,32192,31168,7616,8064,896,0,0,0,0,0)),
    ("Q", (0,0,0,96,248,766,942,798,1806,1806,3342,3598,7736,7672,8188,16348,32760,31968,32224,8160,2976,0,0,0)),
    ("T", (0,0,0,0,1024,2816,7936,12696,12700,12702,25380,25376,25440,25440,18016,31936,16320,960,112,0,0,0,0,0)),
    ("T", (0,0,0,0,0,7680,16128,15128,13214,25022,25440,25440,25440,25440,25440,28384,32704,16320,248,0,0,0,0,0)),
    ("8", (0,480,2032,2040,4092,3644,7224,7224,7288,8184,4080,8176,7288,6264,6264,6264,7280,8176,8128,8064,512,3584,8064,0)),
    ("7", (0,8188,8188,16380,7196,7196,7168,7168,7168,3072,3840,3840,3840,3840,3840,1920,1920,1920,1920,1920,960,960,960,0)),
    ("7", (0,8184,8184,16382,16382,15390,7198,7168,7680,7680,7680,3584,3968,3968,1920,1920,1920,1984,1984,960,992,992,480,0)),
    ("7", (0,8190,8190,16382,16382,7198,7168,7680,3584,3584,3584,3968,3968,1920,1984,960,960,960,992,480,480,496,96,0)),
    ("6", (0,31744,31744,32640,32704,2016,240,120,56,56,2040,8190,8190,7294,15422,15422,15422,15390,7230,7998,8184,2046,1016,0)),
    ("3", (0,192,16320,16320,32704,31744,32256,3968,1984,1984,4032,8064,7680,7680,7168,7182,3854,1950,2044,1016,1008,96,0,0)),
    ("3", (0,0,1920,8128,32704,32256,31744,32256,16128,1984,4032,3968,3584,7168,7168,5646,3598,3870,1982,2044,1008,0,0,0)),
    ("3", (0,0,7936,7936,28544,31744,30720,32256,32512,5888,3968,3968,3584,7168,7168,3598,3854,3902,2046,988,248,0,0,0)),
    ("2", (0,0,0,3584,16128,32512,29440,28672,24576,24576,28672,12288,7936,4064,248,190,30,380,956,496,448,0,0,0)),
    ("K", (0,0,0,2048,3968,1952,958,792,408,440,480,992,992,4064,5856,14528,30912,31168,3040,480,0,0,0,0)),
    ("K", (0,0,0,2048,4024,4030,1982,1854,1840,1968,1008,1008,2032,2032,2016,7904,27840,30912,31728,7152,0,0,0,0)),
    ("7", (0,8184,8184,16382,16382,7198,7192,7168,7680,7680,7680,3584,3584,3968,3968,1920,1920,1920,1920,1984,1984,960,896,0)),
    ("7", (0,8188,8188,16380,16380,15388,7196,7168,7936,7936,7936,3840,3840,3968,1920,1920,1920,1984,1984,960,960,992,224,0)),
    ("4", (0,3072,3072,16128,16128,8064,8128,8128,8160,8160,7392,7408,7280,7288,7422,32766,32766,32760,16256,3840,16320,16352,16320,0)),
    ("2", (0,0,3840,16320,16352,32736,30944,14448,14336,15360,15360,7680,7936,3968,1984,992,496,1274,3646,2046,2044,2040,0,0)),
]

FIELD_UPRIGHT = [
    ("A", (0,0,896,896,960,960,1984,1984,1984,1984,2016,4064,3808,3808,3680,4080,8176,8176,7280,32510,32510,32510,0,0)),
    ("J", (0,16256,16256,16320,16256,7168,7168,7168,7168,7168,7168,7168,7168,7168,7196,7196,7196,7196,3900,3900,4092,2032,992,0)),
    ("T", (0,0,0,0,0,7168,15928,32318,25404,25392,25520,25520,25520,25520,25520,25392,25392,30718,16126,0,0,0,0,0)),
    ("Q", (0,1984,1984,8176,8176,14392,14392,14392,14392,14392,14392,14392,14398,14590,15358,16376,16376,16312,16184,15480,32752,32752,18368,0)),
    ("Q", (0,896,896,4064,8176,15472,14392,14392,14392,14392,14392,14392,14392,14462,15358,16376,16376,16312,16184,15480,31984,32752,28640,0)),
    ("Q", (0,0,384,384,4064,4080,7920,7280,6192,6192,6192,6192,6200,6270,6654,7160,8112,7984,7792,16112,32752,30688,0,0)),
    ("8", (0,1984,1984,8160,16368,14448,14384,14384,14448,14448,15472,8160,8160,16368,14448,14396,14396,12348,14384,15472,16368,8160,1920,0)),
]


def assert_fixture_bank(
    name: str,
    fixtures: list[tuple[str, tuple[int, ...]]],
    bank: list[tuple[str, tuple[int, ...]]],
    max_distance: float,
    min_margin: float,
) -> None:
    for i, (expected, rows) in enumerate(fixtures):
        label, distance, margin = classify(rows, bank, max_distance, min_margin)
        if label != expected:
            fail(
                f"{name}[{i}] expected {expected}, got {label}; "
                f"distance={distance:.6f} margin={margin:.6f}"
            )


def main() -> None:
    banks_text = BANKS.read_text(encoding="utf-8-sig")
    recognizer_text = RECOGNIZER.read_text(encoding="utf-8-sig")
    geometry_text = GEOMETRY.read_text(encoding="utf-8-sig")

    fan = parse_bank(banks_text, "kDeepOFCFantasy15FanRankTemplates")
    upright = parse_bank(banks_text, "kDeepOFCUprightLargeRankTemplates")
    if len(fan) != 32:
        fail(f"expected 32 fan exemplars (13 original + 19 field), got {len(fan)}")
    if len(upright) != 20:
        fail(f"expected 20 upright exemplars (13 original + 7 field), got {len(upright)}")

    if "kDeepOFCFantasy15FanRankTemplateCount" not in banks_text:
        fail("fan template-count constant missing")
    if "kDeepOFCUprightLargeRankTemplateCount" not in banks_text:
        fail("upright template-count constant missing")
    if "upright ? kDeepOFCUprightLargeRankTemplateCount" not in recognizer_text:
        fail("CardFromFeature does not consume the complete upright bank")
    if ": kDeepOFCFantasy15FanRankTemplateCount" not in recognizer_text:
        fail("CardFromFeature does not consume the complete fan bank")

    # Thresholds are intentionally frozen. v5.4.6 improves evidence rather than
    # weakening fail-closed confidence gates.
    if "static const double kDeepOFCFanRankMaxDistance = 0.5;" not in banks_text:
        fail("fan max-distance threshold changed")
    if "static const double kDeepOFCFanRankMinMargin = 0.040000000000000001;" not in banks_text:
        fail("fan min-margin threshold changed")
    if "upright ? 0.36 : kDeepOFCFanRankMaxDistance" not in recognizer_text:
        fail("upright max-distance threshold changed")
    if "upright ? 0.04 : kDeepOFCFanRankMinMargin" not in recognizer_text:
        fail("upright min-margin threshold changed")

    # The original calibrated exemplar for every rank must remain accepted after
    # adding field samples. This catches accidental cross-rank bank pollution.
    if len({label for label, _ in fan[:13]}) != 13:
        fail("first 13 fan entries no longer form the original 13-rank bank")
    if len({label for label, _ in upright[:13]}) != 13:
        fail("first 13 upright entries no longer form the original 13-rank bank")
    assert_fixture_bank("original_fan", fan[:13], fan, 0.50, 0.04)
    assert_fixture_bank("original_upright", upright[:13], upright, 0.36, 0.04)

    # Field fixtures: frame000002 is the 14-card Fantasy fan; frame000020 is a
    # partially arranged 14-card Fantasy state with six reflow loose cards and
    # seven upright arranged cards. Joker identity is color-driven and therefore
    # is deliberately outside the rank-bank fixture list.
    assert_fixture_bank("field_fan", FIELD_FAN, fan, 0.50, 0.04)
    assert_fixture_bank("field_upright", FIELD_UPRIGHT, upright, 0.36, 0.04)

    # frame000020 geometry regression: suit 7d (area=106,height=17) was able to
    # pair with an unrelated one-pixel line (area=20,height=1), impersonate a
    # rank, and suppress the true rank (area=88) in the same x-band. The new
    # lower-glyph floor must reject the one-pixel line without rejecting a real
    # suit-sized component.
    def lower_eligible(area: int, width: int, height: int) -> bool:
        return not (area < 12 or width < 3 or height < 5)

    if lower_eligible(20, 20, 1):
        fail("frame000020 one-pixel lower line is still eligible")
    if not lower_eligible(106, 14, 17):
        fail("frame000020 real suit-sized component was over-filtered")
    if "lower.bounds.Height() < 5" not in geometry_text:
        fail("lower-glyph height floor is not materialized")

    # frame000002 split 8c regression: the fallback used to return the first
    # containing component even if that component contributed zero ink pixels
    # inside the split rank anchor. Selection must maximize actual overlap.
    candidates = [
        ("broad_background", 0, 410 * 105),
        ("merged_8c_rank_suit", 171, 19 * 35),
    ]
    chosen = max(candidates, key=lambda item: (item[1], -item[2]))
    if chosen[0] != "merged_8c_rank_suit":
        fail("frame000002 overlap-safe split-component model failed")
    if "best_overlap" not in recognizer_text or "bounds_area < best_bounds_area" not in recognizer_text:
        fail("overlap-safe FindComponent fallback is not materialized")

    print("OPENOFC_FANTASY_FIELD_V546_REGRESSION=PASS")
    print(f"fan_exemplars={len(fan)} upright_exemplars={len(upright)} thresholds=UNCHANGED")
    print("frame000002_14card=PASS frame000020_partial=PASS")


if __name__ == "__main__":
    main()
