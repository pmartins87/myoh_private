from __future__ import annotations

"""Stable identity checks for the paired OpenOFC v5.5.2 TableMap.

Raw SHA-256 values are useful for artifact provenance but are not a portable
source contract for a text TableMap: checkout newline policy may change the raw
bytes without changing any OpenScrape semantics.  The authoritative safety
contract is therefore two-layered:

1. validate the required v5.5.2 semantic markers/regions;
2. when a materializer claims the TableMap is unchanged, snapshot the raw bytes
   before and after that materializer on the *same checkout* and require exact
   identity.

Artifact assembly still records its actual raw SHA-256.
"""

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TM_RELATIVE = "OpenOFC/TableMaps/KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm"
TM = ROOT / TM_RELATIVE


REQUIRED_LINES = (
    "s$ofc_tablemap_stage        openofc_v5_5_2_fantasy_live_recovery",
    "s$openofc_contract          5",
    "s$openofc_field_revision    552",
    "s$openofc_fantasy_live_recovery 1",
    "s$openofc_fantasy_tablemap_text_by_count 1",
    "s$ofc_fantasy_min_cards     14",
    "s$ofc_fantasy_max_cards     17",
    "s$ofc_players               2",
    "s$nchairs                   2",
    "r$ofc_confirm_button",
    "r$ofc_confirm_visible",
    "r$ofc_drop_top0",
    "r$ofc_drop_top1",
    "r$ofc_drop_top2",
    "r$ofc_drop_middle0",
    "r$ofc_drop_middle1",
    "r$ofc_drop_middle2",
    "r$ofc_drop_middle3",
    "r$ofc_drop_middle4",
    "r$ofc_drop_bottom0",
    "r$ofc_drop_bottom1",
    "r$ofc_drop_bottom2",
    "r$ofc_drop_bottom3",
    "r$ofc_drop_bottom4",
)


def raw_sha256(path: Path = TM) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logical_sha256(path: Path = TM) -> str:
    text = path.read_text(encoding="utf-8-sig")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_v552_semantic_contract(path: Path = TM) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"paired v5.5.2 TableMap missing: {path}")
    text = path.read_text(encoding="utf-8-sig")
    missing = [line for line in REQUIRED_LINES if line not in text]
    if missing:
        raise ValueError(
            "paired v5.5.2 TableMap semantic contract missing: " + ", ".join(missing)
        )
    # Guard against a stale asset that happens to retain a few string markers.
    region_count = sum(1 for line in text.splitlines() if line.startswith("r$"))
    if region_count < 250:
        raise ValueError(
            f"paired v5.5.2 TableMap unexpectedly sparse: regions={region_count}"
        )
    return {
        "path": str(path),
        "raw_sha256": raw_sha256(path),
        "logical_sha256": logical_sha256(path),
        "regions": region_count,
        "stage": "openofc_v5_5_2_fantasy_live_recovery",
        "contract": 5,
        "field_revision": 552,
    }


def assert_unchanged(before_raw_sha256: str, path: Path = TM) -> dict[str, object]:
    after = raw_sha256(path)
    if after != before_raw_sha256:
        raise RuntimeError(
            "field materialization changed paired TableMap bytes on the same checkout: "
            f"before={before_raw_sha256} after={after}"
        )
    return validate_v552_semantic_contract(path)
