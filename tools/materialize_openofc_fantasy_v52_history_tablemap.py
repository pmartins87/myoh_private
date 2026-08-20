from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from materialize_openofc_fantasy_v5_tablemap import materialize as materialize_v5

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "OpenOFC/TableMaps/KKPoker_OpenOFC_JokerUltimate_v5_2.tm"

LEGACY_STRING_KEYS = {
    "s$allinconfirmationmethod",
    "s$betsizeconfirmationmethod",
    "s$betsizedeletionmethod",
    "s$betsizeinterpretationmethod",
    "s$betsizeselectionmethod",
    "s$buttonclickmethod",
    "s$i0buttondefaultlabel",
    "s$i4buttondefaultlabel",
    "s$i5buttondefaultlabel",
    "s$i6buttondefaultlabel",
    "s$i7buttondefaultlabel",
    "s$potmethod",
    "s$t0type",
    "s$t6type",
    "s$t7type",
}


def append_if_missing(text: str, key: str, line: str) -> str:
    if key not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    return text


def region_name(line: str) -> str:
    return line.split(None, 1)[0] if line.startswith("r$") else ""


def is_zero_rect_region(line: str) -> bool:
    if not line.startswith("r$"):
        return False
    parts = line.split()
    return len(parts) >= 5 and parts[1:5] == ["0", "0", "0", "0"]


def keep_opponent_discard(name: str) -> bool:
    # Current KKPoker HU layout fixes Hero at p1 and the opponent/result discard
    # strip at p0. These regions are passive history evidence only.
    return re.match(r"r\$ofc_p0_discard[0-3](empty|back|rank|suit)$", name) is not None


def should_remove_region(name: str, line: str) -> bool:
    if not name:
        return False
    if not name.startswith("r$ofc_"):
        return True
    if is_zero_rect_region(line):
        return True
    # Hero discard thumbnails remain unnecessary: Hero's discard is derived
    # from the exact incoming set and board transition.
    if name.startswith("r$ofc_hero_discard"):
        return True
    # Opponent result discards are intentionally preserved as database evidence.
    if re.match(r"r\$ofc_p\d+_discard\d+", name):
        return not keep_opponent_discard(name)
    if re.fullmatch(r"r\$ofc_p\d+_turn", name):
        return True
    # Fantasy loose-card locations are dynamic and redetected after each reflow.
    if name.startswith("r$ofc_fantasy15_src"):
        return True
    if name == "r$ofc_fantasy15_unused_span":
        return True
    if name.startswith("r$ofc_fantasy15_drop_"):
        return True
    return False


def materialize(output: Path) -> None:
    temp = output.with_suffix(output.suffix + ".v5tmp")
    materialize_v5(temp)
    text = temp.read_text(encoding="utf-8").replace("\r\n", "\n")
    temp.unlink(missing_ok=True)

    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        key = stripped.split(None, 1)[0] if stripped else ""
        if key in LEGACY_STRING_KEYS:
            continue
        if stripped.startswith("r$") and should_remove_region(region_name(stripped), stripped):
            continue
        # T2/T4 are deliberately retained: the opponent's face-up result discard
        # glyphs use these smaller-font banks. Missing glyphs are a calibration
        # debt, never a gameplay gate; the evidence frame is always archived.
        out.append(line)

    cleaned = "\n".join(out).rstrip() + "\n"
    cleaned = re.sub(
        r"s\$ofc_tablemap_stage\s+\S+",
        "s$ofc_tablemap_stage        openofc_v5_2_opponent_history",
        cleaned,
    )
    cleaned = append_if_missing(cleaned, "s$openofc_tablemap_clean", "s$openofc_tablemap_clean 1")
    cleaned = append_if_missing(cleaned, "s$openofc_opponent_history", "s$openofc_opponent_history 1")
    cleaned = append_if_missing(cleaned, "s$openofc_opponent_reveal_scrape", "s$openofc_opponent_reveal_scrape 1")
    cleaned = append_if_missing(cleaned, "s$openofc_history_schema", "s$openofc_history_schema 1")

    # Preserve name geometry without bringing the legacy Hold'em player-name
    # graph back into OpenOFC. A0 remains only an OCR transform for these two
    # explicit OFC identity regions.
    cleaned = append_if_missing(
        cleaned,
        "r$ofc_p0_name",
        "r$ofc_p0_name 351 272 411 282 696969 50 A0 1 125 0 40 3",
    )
    cleaned = append_if_missing(
        cleaned,
        "r$ofc_p1_name",
        "r$ofc_p1_name 312 470 371 480 ff201b16 50 A0 1 125 0 40 3",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(cleaned, encoding="utf-8", newline="\n")

    validator = ROOT / "tools/validate_openofc_tablemap.py"
    subprocess.run(
        [sys.executable, str(validator), str(output), "--require-contract", "4"],
        cwd=str(ROOT),
        check=True,
    )

    verify = output.read_text(encoding="utf-8")
    required = [
        "s$openofc_tablemap_clean 1",
        "s$openofc_opponent_history 1",
        "s$openofc_opponent_reveal_scrape 1",
        "r$ofc_p0_name",
        "r$ofc_p1_name",
        "r$ofc_p0_discard0empty",
        "r$ofc_p0_discard0back",
        "r$ofc_p0_discard0rank",
        "r$ofc_p0_discard0suit",
        "r$ofc_p0_discard1rank",
        "r$ofc_p0_discard2rank",
        "r$ofc_p0_discard3rank",
        "t2$",
        "t4$",
        "r$ofc_fantasy_row_action_top",
        "r$ofc_confirm_visible",
        "r$ofc_fantasy15_confirm_visible",
    ]
    missing = [item for item in required if item not in verify]
    if missing:
        raise RuntimeError("v5.2 history TableMap missing: " + ", ".join(missing))

    forbidden = [
        "r$ofc_hero_discard",
        "r$ofc_fantasy15_src",
        "r$ofc_fantasy15_drop_",
        "r$ofc_fantasy15_unused_span",
        "r$ofc_p0_turn",
        "r$ofc_p1_turn",
        "r$c0cardface",
        "r$i0button",
        "r$p0name",
    ]
    leaked = [item for item in forbidden if item in verify]
    if leaked:
        raise RuntimeError("v5.2 cleanup leak: " + ", ".join(leaked))

    zero = [line for line in verify.splitlines() if is_zero_rect_region(line.strip())]
    if zero:
        raise RuntimeError(f"v5.2 still contains {len(zero)} zero-area regions")

    print(f"OpenOFC Fantasy v5.2 opponent-history TableMap materialized: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    materialize(Path(args.output))


if __name__ == "__main__":
    main()
