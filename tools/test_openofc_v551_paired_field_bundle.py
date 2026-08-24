from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TM = ROOT / "OpenOFC" / "TableMaps" / "KKPoker_Chines_v5_5_1_FANTASY_COUNTED_TEXT.tm"
COUNTS = (6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17)


def main() -> None:
    status = (ROOT / "OpenHoldem" / "COpenHoldemStatusbar.cpp").read_text(
        encoding="utf-8-sig"
    )
    view = (ROOT / "OpenHoldem" / "OpenHoldemView.cpp").read_text(
        encoding="utf-8-sig"
    )
    tm = TM.read_text(encoding="ascii")

    assert "const bool contract_ok = contract == 5;" in status
    assert "const bool contract_ok = contract == 1;" not in status
    assert "TM V551 REQUIRED" in status
    assert "paired_tablemap_ok" in status
    assert "TABLEMAP  PAIRED V551=OK" in view
    assert "COUNTED-TEXT V551 SYMBOL MISSING" in view
    assert "CONTRACT=%d EXPECTED=5" in view

    assert tm.count("s$openofc_contract          5") == 1
    assert tm.count("s$openofc_fantasy_tablemap_text_by_count 1") == 1
    assert tm.count("s$openofc_fantasy17_calibrated 0") == 1
    assert tm.count("s$ofc_tablemap_stage           openofc_v5_5_0_counted_text_field_test") == 1
    assert "r$IsFantasy15" in tm

    found = set()
    pattern = re.compile(r"^r\$ofc_fantasy(\d{2})_(\d{2})(rank|suit)\s+", re.MULTILINE)
    for match in pattern.finditer(tm):
        found.add((int(match.group(1)), int(match.group(2)), match.group(3)))
    expected = {
        (count, index, kind)
        for count in COUNTS
        for index in range(count)
        for kind in ("rank", "suit")
    }
    assert found == expected, (sorted(expected - found), sorted(found - expected))
    assert len(found) == 256
    assert not any(count in (1, 2, 3, 4, 5, 10) for count, _, _ in found)

    begin = tm.count("// BEGIN OPENOFC_V550_STABLE_REPLAY_T7")
    end = tm.count("// END OPENOFC_V550_STABLE_REPLAY_T7")
    assert begin == 1 and end == 1

    print(
        "OPENOFC_V551_PAIRED_FIELD_BUNDLE=PASS "
        "ui_contract=5 tm_optin=1 regions=256 stable_counts="
        "6,7,8,9,11,12,13,14,15,16,17 fantasy17=FAIL_CLOSED"
    )


if __name__ == "__main__":
    main()
