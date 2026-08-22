from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from materialize_openofc_fantasy_v52_history_tablemap import materialize as materialize_v52

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "OpenOFC/TableMaps/KKPoker_OpenOFC_JokerUltimate_v5_4_3.tm"


def replace_symbol(text: str, key: str, value: str) -> str:
    pattern = rf"(?m)^s\${re.escape(key)}\s+\S+\s*$"
    replacement = f"s${key:<28} {value}"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"missing or duplicate symbol s${key}: {count}")
    return updated


def append_symbol_after(text: str, anchor_key: str, key: str, value: str) -> str:
    if re.search(rf"(?m)^s\${re.escape(key)}\s+", text):
        return text
    pattern = rf"(?m)^(s\${re.escape(anchor_key)}\s+\S+\s*)$"
    replacement = rf"\1\ns${key:<28} {value}"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"anchor symbol s${anchor_key} missing or duplicate: {count}")
    return updated


def add_generic_region_aliases(text: str) -> str:
    lines = text.splitlines()
    existing = {
        line.split(None, 1)[0]
        for line in lines
        if line.strip().startswith("r$")
    }
    out: list[str] = []
    aliases_added = 0
    for line in lines:
        out.append(line)
        stripped = line.strip()
        if not stripped.startswith("r$"):
            continue
        old_name = stripped.split(None, 1)[0]
        new_name = None
        if old_name.startswith("r$ofc_fantasy15_arrange_"):
            new_name = old_name.replace(
                "r$ofc_fantasy15_arrange_", "r$ofc_fantasy_arrange_", 1
            )
        elif old_name == "r$ofc_fantasy15_confirm_button":
            new_name = "r$ofc_fantasy_confirm_button"
        elif old_name == "r$ofc_fantasy15_confirm_visible":
            new_name = "r$ofc_fantasy_confirm_visible"
        if new_name is None or new_name in existing:
            continue
        out.append(line.replace(old_name, new_name, 1))
        existing.add(new_name)
        aliases_added += 1

    if aliases_added != 15:
        raise RuntimeError(
            f"expected 15 generic Fantasy region aliases (13 arrangement + 2 confirm), got {aliases_added}"
        )
    return "\n".join(out).rstrip() + "\n"


def region_names(text: str) -> list[str]:
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("r$"):
            names.append(line.split(None, 1)[0][2:])
    return names


def parse_symbols(text: str) -> dict[str, str]:
    symbols: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("s$"):
            continue
        parts = line.split(None, 1)
        key = parts[0][2:]
        value = parts[1].strip() if len(parts) > 1 else ""
        if key in symbols:
            raise RuntimeError(f"duplicate TableMap symbol s${key}")
        symbols[key] = value
    return symbols


def materialize(output: Path) -> None:
    # v5.2 is the latest clean TableMap lineage: it already removed legacy
    # Hold'em gameplay regions and retained only OFC-native regions plus the
    # minimal generic OpenHoldem symbols needed to load the map.
    temp = output.with_suffix(output.suffix + ".v52tmp")
    materialize_v52(temp)
    text = temp.read_text(encoding="utf-8").replace("\r\n", "\n")
    temp.unlink(missing_ok=True)

    text = replace_symbol(text, "openofc_contract", "5")
    text = replace_symbol(
        text, "ofc_tablemap_stage", "openofc_v5_4_3_contract5_generic_runtime"
    )
    text = append_symbol_after(
        text,
        "ofc_fantasy15_geometry_measured",
        "ofc_fantasy_geometry_measured",
        "1",
    )
    text = add_generic_region_aliases(text)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="\n")

    validator = ROOT / "tools/validate_openofc_tablemap.py"
    subprocess.run(
        [sys.executable, str(validator), str(output), "--require-contract", "5"],
        cwd=str(ROOT),
        check=True,
    )

    verify = output.read_text(encoding="utf-8")
    symbols = parse_symbols(verify)
    expected_symbols = {
        "openofc_contract": "5",
        "openofc_tablemap_clean": "1",
        "openofc_opponent_history": "1",
        "openofc_opponent_reveal_scrape": "1",
        "ofc_fantasy_geometry_measured": "1",
    }
    wrong_symbols = [
        f"s${key} expected={expected!r} got={symbols.get(key)!r}"
        for key, expected in expected_symbols.items()
        if symbols.get(key) != expected
    ]
    if wrong_symbols:
        raise RuntimeError(
            "v5.4.3 contract-5 TableMap symbol mismatch: " + "; ".join(wrong_symbols)
        )

    names = set(region_names(verify))
    required_regions = {
        "ofc_fantasy_arrange_top0",
        "ofc_fantasy_arrange_middle0",
        "ofc_fantasy_arrange_bottom0",
        "ofc_fantasy_confirm_button",
        "ofc_fantasy_confirm_visible",
        "ofc_fantasy_row_action_top",
        "ofc_fantasy_row_action_middle",
        "ofc_fantasy_row_action_bottom",
        "ofc_confirm_button",
        "ofc_confirm_visible",
        "ofc_p0_name",
        "ofc_p1_name",
    }
    missing_regions = sorted(required_regions.difference(names))
    if missing_regions:
        raise RuntimeError(
            "v5.4.3 contract-5 TableMap missing regions: " + ", ".join(missing_regions)
        )

    # The field regression being fixed here was a release downgrade to v3,
    # which reintroduced ordinary Hold'em gameplay regions. Contract 5 refuses
    # any such region: every region in this TableMap must be explicitly OFC.
    non_ofc = sorted(name for name in names if not name.startswith("ofc_"))
    if non_ofc:
        raise RuntimeError(
            "contract-5 TableMap contains non-OFC/legacy gameplay regions: "
            + ", ".join(non_ofc[:20])
        )

    forbidden = [
        "r$c0cardface",
        "r$c0pot",
        "r$i0button",
        "r$p0cardface",
        "r$p0bet",
        "r$p0balance",
        "r$p0name",
        "r$p1cardface",
        "r$p1bet",
        "r$p1balance",
        "r$p1name",
    ]
    leaked = [item for item in forbidden if item in verify]
    if leaked:
        raise RuntimeError("legacy Hold'em TableMap leak: " + ", ".join(leaked))

    print(f"OPENOFC_TABLEMAP_V543_CONTRACT5=PASS path={output}")
    print(f"OPENOFC_TABLEMAP_REGION_COUNT={len(names)}")
    print("LEGACY_HOLDEM_TABLEMAP_REGIONS=0")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    materialize(Path(args.output))


if __name__ == "__main__":
    main()
