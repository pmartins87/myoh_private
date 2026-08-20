from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from materialize_openofc_fantasy_v5_tablemap import materialize as materialize_v5

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "OpenOFC/TableMaps/KKPoker_OpenOFC_JokerUltimate_v5_1.tm"


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
    "s$t2type",
    "s$t4type",
    "s$t6type",
    "s$t7type",
}


def region_name(line: str) -> str:
    return line.split(None, 1)[0] if line.startswith("r$") else ""


def is_zero_rect_region(line: str) -> bool:
    if not line.startswith("r$"):
        return False
    parts = line.split()
    if len(parts) < 5:
        return False
    return parts[1:5] == ["0", "0", "0", "0"]


def remove_region(name: str, line: str) -> bool:
    if not name:
        return False
    # OpenOFC heartbeat/scraper bypasses legacy Hold'em regions completely.
    if not name.startswith("r$ofc_"):
        return True
    # Generic zero-area placeholders have no physical or recognition meaning.
    if is_zero_rect_region(line):
        return True
    # Hero/opponent discard identities are state-derived and no longer scraped.
    if name.startswith("r$ofc_hero_discard"):
        return True
    if re.match(r"r\$ofc_p\d+_discard\d+", name):
        return True
    # Turn is deliberately non-authoritative in simultaneous OFC.
    if re.fullmatch(r"r\$ofc_p\d+_turn", name):
        return True
    # Fantasy loose sources reflow and are detected from each fresh bitmap.
    if name.startswith("r$ofc_fantasy15_src"):
        return True
    if name == "r$ofc_fantasy15_unused_span":
        return True
    # v5 uses select-card + contextual row action, not fixed Fantasy drag targets.
    if name.startswith("r$ofc_fantasy15_drop_"):
        return True
    return False


def clean_tablemap(text: str) -> tuple[str, dict[str, int]]:
    stats = {
        "legacy_strings": 0,
        "legacy_regions": 0,
        "zero_regions": 0,
        "discard_regions": 0,
        "turn_regions": 0,
        "fantasy_fixed_sources": 0,
        "fantasy_fixed_drops": 0,
        "unused_fonts": 0,
    }
    out: list[str] = []
    for line in text.replace("\r\n", "\n").splitlines():
        stripped = line.strip()
        key = stripped.split(None, 1)[0] if stripped else ""
        if key in LEGACY_STRING_KEYS:
            stats["legacy_strings"] += 1
            continue
        if stripped.startswith("t2$") or stripped.startswith("t4$"):
            stats["unused_fonts"] += 1
            continue
        if stripped.startswith("r$"):
            name = region_name(stripped)
            if remove_region(name, stripped):
                if not name.startswith("r$ofc_"):
                    stats["legacy_regions"] += 1
                elif is_zero_rect_region(stripped):
                    stats["zero_regions"] += 1
                elif "discard" in name:
                    stats["discard_regions"] += 1
                elif name.endswith("_turn"):
                    stats["turn_regions"] += 1
                elif name.startswith("r$ofc_fantasy15_src") or name == "r$ofc_fantasy15_unused_span":
                    stats["fantasy_fixed_sources"] += 1
                elif name.startswith("r$ofc_fantasy15_drop_"):
                    stats["fantasy_fixed_drops"] += 1
                continue
        out.append(line)

    cleaned = "\n".join(out).rstrip() + "\n"
    if "s$openofc_tablemap_clean" not in cleaned:
        cleaned += "s$openofc_tablemap_clean 1\n"
    cleaned = re.sub(
        r"s\$ofc_tablemap_stage\s+\S+",
        "s$ofc_tablemap_stage        openofc_v5_1_dynamic_fantasy",
        cleaned,
    )
    return cleaned, stats


def materialize(output: Path) -> None:
    temp = output.with_suffix(output.suffix + ".v5tmp")
    materialize_v5(temp)
    text = temp.read_text(encoding="utf-8")
    cleaned, stats = clean_tablemap(text)
    temp.unlink(missing_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(cleaned, encoding="utf-8", newline="\n")

    validator = ROOT / "tools/validate_openofc_tablemap.py"
    subprocess.run(
        [sys.executable, str(validator), str(output), "--require-contract", "4"],
        cwd=str(ROOT),
        check=True,
    )

    verify = output.read_text(encoding="utf-8")
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
        "t2$",
        "t4$",
    ]
    leaked = [item for item in forbidden if item in verify]
    if leaked:
        raise RuntimeError("v5.1 cleanup leak: " + ", ".join(leaked))
    required = [
        "s$openofc_tablemap_clean 1",
        "r$ofc_confirm_button",
        "r$ofc_confirm_visible",
        "r$ofc_fantasy15_confirm_button",
        "r$ofc_fantasy15_confirm_visible",
        "r$ofc_fantasy_row_action_top",
        "r$ofc_fantasy_row_action_middle",
        "r$ofc_fantasy_row_action_bottom",
        "r$ofc_menu_button",
        "r$ofc_leave_next_hand_menu_item",
    ]
    missing = [item for item in required if item not in verify]
    if missing:
        raise RuntimeError("v5.1 required contract missing: " + ", ".join(missing))
    # Only active text banks should remain.
    for transform in ("T2", "T4", "T6", "T7"):
        if re.search(rf"^r\$.*\s{transform}\s", verify, flags=re.M):
            raise RuntimeError(f"unused transform still referenced: {transform}")

    print("OpenOFC Fantasy v5.1 clean TableMap materialized:", output)
    print("cleanup stats:", stats)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    materialize(Path(args.output))


if __name__ == "__main__":
    main()
