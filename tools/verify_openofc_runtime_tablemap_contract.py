from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_tm(path: Path):
    symbols: dict[str, str] = {}
    regions: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("s$"):
            parts = line.split(None, 1)
            symbols[parts[0][2:]] = parts[1].strip() if len(parts) > 1 else ""
        elif line.startswith("r$"):
            regions.append(line.split(None, 1)[0][2:])
    return symbols, regions


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fail closed if OpenOFC runtime and packaged TableMap contracts diverge"
    )
    ap.add_argument("tablemap", type=Path)
    args = ap.parse_args()

    heartbeat = (ROOT / "OpenHoldem/CHeartbeatThread.cpp").read_text(
        encoding="utf-8-sig", errors="strict"
    )
    matches = re.findall(r"const int kOpenOFCContractVersion = (\d+);", heartbeat)
    if len(matches) != 1:
        raise RuntimeError(
            f"runtime OpenOFC contract declaration must be unique, got {matches}"
        )
    runtime_contract = int(matches[0])

    symbols, regions = parse_tm(args.tablemap)
    try:
        tablemap_contract = int(symbols.get("openofc_contract", ""))
    except ValueError as exc:
        raise RuntimeError(
            f"TableMap openofc_contract is not an integer: {symbols.get('openofc_contract')!r}"
        ) from exc

    print(
        f"OPENOFC_RUNTIME_TABLEMAP_CONTRACT runtime={runtime_contract} "
        f"tablemap={tablemap_contract} path={args.tablemap}"
    )
    if runtime_contract != tablemap_contract:
        raise RuntimeError(
            f"runtime/TableMap contract mismatch: runtime={runtime_contract} "
            f"tablemap={tablemap_contract}"
        )
    if runtime_contract != 5:
        raise RuntimeError(
            f"v5.4.3 field package must use contract 5, got {runtime_contract}"
        )

    required_symbols = {
        "ofc_variant": "joker_ultimate",
        "openofc_tablemap_clean": "1",
        "ofc_fantasy_geometry_measured": "1",
        "ofc_fantasy_recognizer_calibrated": "1",
        "ofc_drag_targets_calibrated": "1",
        "ofc_executor_enabled": "1",
    }
    for key, expected in required_symbols.items():
        got = symbols.get(key)
        if got != expected:
            raise RuntimeError(f"s${key} expected {expected!r}, got {got!r}")

    required_regions = {
        "ofc_confirm_button",
        "ofc_confirm_visible",
        "ofc_fantasy_confirm_button",
        "ofc_fantasy_confirm_visible",
        "ofc_fantasy_row_action_top",
        "ofc_fantasy_row_action_middle",
        "ofc_fantasy_row_action_bottom",
    }
    required_regions.update(f"ofc_fantasy_arrange_top{i}" for i in range(3))
    required_regions.update(f"ofc_fantasy_arrange_middle{i}" for i in range(5))
    required_regions.update(f"ofc_fantasy_arrange_bottom{i}" for i in range(5))
    missing = sorted(required_regions.difference(regions))
    if missing:
        raise RuntimeError("packaged TableMap missing generic runtime regions: " + ", ".join(missing))

    legacy = sorted(name for name in regions if not name.startswith("ofc_"))
    if legacy:
        raise RuntimeError(
            "packaged TableMap reintroduced non-OFC/legacy gameplay regions: "
            + ", ".join(legacy[:30])
        )

    runtime_controller = (ROOT / "OpenHoldem/COFCRuntimeController.cpp").read_text(
        encoding="utf-8-sig", errors="strict"
    )
    scraper = (ROOT / "OpenHoldem/COFCScraper.cpp").read_text(
        encoding="utf-8-sig", errors="strict"
    )
    runtime_markers = [
        "ofc_fantasy_confirm_button",
        "state.hero_incoming_count >= 14",
        "state.hero_incoming_count <= 17",
        "OPENOFC_NEVER_TERMINAL_RUNTIME_V54",
    ]
    for marker in runtime_markers:
        if marker not in runtime_controller:
            raise RuntimeError(f"runtime marker missing: {marker}")
    scraper_markers = [
        "ofc_fantasy_arrange_",
        "OFCFantasyGeometryMeasured",
        "COFCFantasyPixelRecognizer",
    ]
    for marker in scraper_markers:
        if marker not in scraper:
            raise RuntimeError(f"scraper marker missing: {marker}")

    print("OPENOFC_RUNTIME_TABLEMAP_COMPATIBILITY=PASS")
    print("LEGACY_HOLDEM_TABLEMAP_REGIONS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
