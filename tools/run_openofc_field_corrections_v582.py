from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from openofc_tablemap_identity import assert_unchanged, raw_sha256, validate_v552_semantic_contract


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V582_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.8.2 failed rc={process.returncode}: {relative}")


def main() -> None:
    # Source-level authority: validate the paired v5.5.2 asset first, then prove
    # this entire v5.8.2 materialization leaves its bytes unchanged on the same
    # checkout. This is stronger and more portable than comparing a Windows
    # checkout against an old SHA captured under a different newline policy.
    source_tm = validate_v552_semantic_contract()
    before_tm_sha = raw_sha256()
    print(
        "V582_TABLEMAP_SOURCE "
        f"raw_sha256={source_tm['raw_sha256']} "
        f"logical_sha256={source_tm['logical_sha256']} "
        f"regions={source_tm['regions']}",
        flush=True,
    )

    run("tools/run_openofc_field_corrections_v581.py")
    run("tools/normalize_openofc_v582_runtime_gate.py")
    run("tools/apply_openofc_field_corrections_v582.py")
    run("tools/test_openofc_field_corrections_v582.py")

    final_tm = assert_unchanged(before_tm_sha)
    print(
        "V582_TABLEMAP_UNCHANGED=PASS "
        f"raw_sha256={final_tm['raw_sha256']} logical_sha256={final_tm['logical_sha256']}",
        flush=True,
    )
    print(
        "OPENOFC_V582_MATERIALIZATION=PASS "
        "field_failure=FANTASY_BOOTSTRAP_AND_STALE_TRANSACTION "
        "count_alignment=MISSING1_EXTRA2 "
        "bootstrap=EMPTY_OCCUPANCY_FIRST "
        "runtime=F14_17_SEMANTIC_NEW_HAND_RELEASE "
        "strategy=V581_PRESERVED tablemap=UNCHANGED_SAME_CHECKOUT"
    )


if __name__ == "__main__":
    main()
