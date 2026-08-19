from __future__ import annotations

import argparse
import base64
import gzip
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OpenOFC/TableMaps/KKPoker_OpenOFC_JokerUltimate_v4.tm.gz.b64"
DEFAULT_OUTPUT = ROOT / "OpenOFC/TableMaps/KKPoker_OpenOFC_JokerUltimate_v5.tm"


def append_if_missing(text: str, key: str, line: str) -> str:
    if key not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    return text


def materialize(output: Path) -> None:
    compressed = base64.b64decode(SOURCE.read_text(encoding="utf-8").strip())
    text = gzip.decompress(compressed).decode("utf-8-sig").replace("\r\n", "\n")

    text = re.sub(
        r"s\$openofc_safe_exit_calibrated\s+1",
        "s$openofc_safe_exit_calibrated 0",
        text,
    )
    text = re.sub(
        r"s\$openofc_stop_enabled\s+0",
        "s$openofc_stop_enabled       1",
        text,
    )
    text = re.sub(
        r"s\$openofc_stop_local_hhmm\s+0",
        "s$openofc_stop_local_hhmm    -1",
        text,
    )
    if re.search(r"s\$openofc_field_revision\s+\d+", text):
        text = re.sub(
            r"s\$openofc_field_revision\s+\d+",
            "s$openofc_field_revision 50",
            text,
        )
    else:
        text = append_if_missing(
            text, "s$openofc_field_revision", "s$openofc_field_revision 50"
        )

    text = append_if_missing(
        text,
        "s$openofc_exit_mode_leave_next_hand",
        "s$openofc_exit_mode_leave_next_hand 1",
    )
    text = append_if_missing(
        text, "s$openofc_hero_discard_scrape", "s$openofc_hero_discard_scrape 0"
    )
    text = append_if_missing(
        text, "s$openofc_turn_semantics", "s$openofc_turn_semantics 0"
    )
    text = append_if_missing(
        text,
        "s$openofc_fantasy_row_batch_click",
        "s$openofc_fantasy_row_batch_click 1",
    )
    text = append_if_missing(
        text, "s$ofc_fantasy_select_gap_ms", "s$ofc_fantasy_select_gap_ms 110"
    )
    text = append_if_missing(
        text,
        "r$ofc_menu_button",
        "r$ofc_menu_button 15 55 45 90 ff000000 0 N 1 0 0 0 -1",
    )
    text = append_if_missing(
        text,
        "r$ofc_leave_next_hand_menu_item",
        "r$ofc_leave_next_hand_menu_item 12 252 237 306 ff000000 0 N 1 0 0 0 -1",
    )

    # Measured from the two supplied 450x830 Fantasy replay sessions. The same
    # contextual control is a yellow check on an empty row and a red X on a
    # populated row.
    measured = {
        "top": "397 428 431 461",
        "middle": "397 500 431 533",
        "bottom": "397 573 431 606",
    }
    for row, rect in measured.items():
        key = f"r$ofc_fantasy_row_action_{row}"
        text = append_if_missing(
            text, key, f"{key} {rect} ff000000 0 N 1 0 0 0 -1"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="\n")

    validator = ROOT / "tools/validate_openofc_tablemap.py"
    subprocess.run(
        [sys.executable, str(validator), str(output), "--require-contract", "4"],
        cwd=str(ROOT),
        check=True,
    )

    verify = output.read_text(encoding="utf-8")
    required = [
        "s$openofc_fantasy_row_batch_click 1",
        "s$ofc_fantasy_select_gap_ms 110",
        "r$ofc_fantasy_row_action_top 397 428 431 461",
        "r$ofc_fantasy_row_action_middle 397 500 431 533",
        "r$ofc_fantasy_row_action_bottom 397 573 431 606",
    ]
    missing = [item for item in required if item not in verify]
    if missing:
        raise RuntimeError("v5 TableMap missing: " + ", ".join(missing))
    print(f"OpenOFC Fantasy v5 TableMap materialized: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    materialize(Path(args.output))


if __name__ == "__main__":
    main()
