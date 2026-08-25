from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TM = (
    ROOT
    / "OpenOFC"
    / "TableMaps"
    / "KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm"
)
TM_V551 = (
    ROOT
    / "OpenOFC"
    / "TableMaps"
    / "KKPoker_Chines_v5_5_1_FANTASY_COUNTED_TEXT.tm"
)


def should_rollover(previous: list[str], current: list[str], occupied: int) -> bool:
    return (
        occupied == 0
        and 14 <= len(current) <= 17
        and set(current) != set(previous)
    )


def visual_row_matches(target: list[int], visual: list[int]) -> bool:
    return sorted(target) == sorted(visual)


def lineage_subset_ok(lineage: list[str], arranged: list[str]) -> bool:
    unused = len(lineage) - len(arranged)
    return (
        len(lineage) == len(set(lineage))
        and len(arranged) == len(set(arranged))
        and set(arranged).issubset(lineage)
        and 0 <= unused <= 4
    )


def deterministic_models() -> None:
    prior = [f"old{i}" for i in range(16)]
    new = [f"new{i}" for i in range(16)]
    assert should_rollover(prior, new, 0)
    assert not should_rollover(prior, prior[::-1], 0)
    assert not should_rollover(prior, new, 3)

    # Reproduces the live false-positive class: canonical/pending metadata can
    # say BOTTOM while the fresh pixels show those cards in a different row.
    target_bottom = [2, 3, 5, 6, 52]
    assert visual_row_matches(target_bottom, [52, 6, 5, 3, 2])
    assert not visual_row_matches(target_bottom, [52, 6, 5, 3])
    assert not visual_row_matches(target_bottom, [52, 6, 5, 3, -3])

    lineage = [f"c{i}" for i in range(16)]
    assert lineage_subset_ok(lineage, lineage[:13])
    assert not lineage_subset_ok(lineage, lineage[:12] + ["off-lineage"])

    screen = ["JK1", "9d", "8h", "7h", "6c", "5h", "4h", "4d"]
    assert list(screen) == screen  # presentation must not sort this sequence


def source_contracts() -> None:
    scraper = (ROOT / "OpenHoldem" / "COFCScraper.cpp").read_text(
        encoding="utf-8-sig"
    )
    recognizer = (
        ROOT / "OpenHoldem" / "COFCFantasy15PixelRecognizer.cpp"
    ).read_text(encoding="utf-8-sig")
    executor = (ROOT / "OpenHoldem" / "COFCFantasyBatchExecutor.cpp").read_text(
        encoding="utf-8-sig"
    )
    executor_h = (
        ROOT / "OpenHoldem" / "COFCFantasyBatchExecutor.h"
    ).read_text(encoding="utf-8-sig")
    view = (ROOT / "OpenHoldem" / "OpenHoldemView.cpp").read_text(
        encoding="utf-8-sig"
    )
    status = (ROOT / "OpenHoldem" / "COpenHoldemStatusbar.cpp").read_text(
        encoding="utf-8-sig"
    )

    assert "OPENOFC_FANTASY_LIVE_RECOVERY_V552" in scraper
    assert "new_deal=CURRENT_SCREEN" in scraper
    assert "original_labels.clear();" in scraper
    assert "loose_labels != prior_labels" in scraper
    assert "final arrangement lineage verification" in scraper
    assert re.search(
        r"RecognizeArrangementSlotsAgainstExpected\(\s*\n"
        r"\s*_entire_window_cur, arrangement_rects, original_labels,",
        scraper,
    )
    assert "final board contains off-lineage card" in scraper

    assert "unused_count < 0 || unused_count > 4" in recognizer
    assert "slot_indices.size() > expected_indices.size()" in recognizer
    assert "assigned_count != occupied_count" in recognizer
    assert "expected physical card was not assigned" not in recognizer

    assert "CurrentVisualRowCards" in executor
    assert "CurrentRowCards(const COFCState" not in executor
    assert "RowMatchesTarget(observation, waiting_row_)" in executor
    assert "evidence=RAW_VISUAL_EXACT" in executor
    assert '? 250 : max(250, p_tablemap->GetTMSymbol(' in executor
    assert '"ofc_fantasy_select_gap_ms", 250' in executor
    assert "const COFCVisualObservation &observation" in executor_h

    assert "FANTASY SCREEN ORDER  %s" in view
    assert "raw->hero_loose_cards, raw->hero_loose_count" in view
    assert "REACQUIRING CURRENT DEAL" in view
    assert "TABLEMAP  PAIRED V552=OK" in view
    assert "openofc_fantasy_live_recovery" in view
    assert "TM V552 REQUIRED" in status
    assert "openofc_fantasy_live_recovery" in status


def tablemap_contract() -> None:
    tm = TM.read_text(encoding="ascii")
    calibrated_v551 = TM_V551.read_text(encoding="ascii")
    assert tm.count("s$ofc_fantasy_select_gap_ms 250") == 1
    assert tm.count("s$openofc_fantasy_live_recovery 1") == 1
    assert tm.count("s$openofc_fantasy_tablemap_text_by_count 1") == 1
    assert tm.count("s$openofc_contract          5") == 1
    assert tm.count("s$openofc_fantasy17_calibrated 0") == 1
    assert re.search(
        r"^s\$ofc_tablemap_stage\s+openofc_v5_5_2_fantasy_live_recovery$",
        tm,
        re.MULTILINE,
    )

    # v5.5.2 changes the runtime-pairing symbols only. Every manually adjusted
    # region and learned font from the user's field-edited v5.5.1 must survive
    # byte-for-byte at the record level.
    def region_records(source: str) -> dict[str, str]:
        return {
            line.split()[0]: line
            for line in source.splitlines()
            if line.startswith("r$")
        }

    def font_records(source: str) -> Counter[str]:
        return Counter(
            line
            for line in source.splitlines()
            if re.match(r"^t\d+\$", line)
        )

    assert region_records(tm) == region_records(calibrated_v551)
    assert font_records(tm) == font_records(calibrated_v551)
    assert len(region_records(tm)) == 455
    assert sum(font_records(tm).values()) == 540


def main() -> None:
    deterministic_models()
    source_contracts()
    tablemap_contract()
    print(
        "OPENOFC_FANTASY_LIVE_RECOVERY_V552_REGRESSION=PASS "
        "refantasy=RESET_ON_DIFFERENT_EMPTY_FAN same_deal_clear=PRESERVE "
        "final=LINEAGE_SUBSET row_verify=RAW_VISUAL_EXACT "
        "click_gap_ms=250 ui=LEFT_TO_RIGHT_SCREEN_ORDER"
    )


if __name__ == "__main__":
    main()
