from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V552_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.5.2 failed rc={process.returncode}: {relative}")


def main() -> None:
    run("tools/run_openofc_fantasy_paired_bundle_v551.py")
    run("tools/apply_openofc_fantasy_live_recovery_v552.py")
    run("tools/test_openofc_fantasy_live_recovery_v552.py")
    print(
        "OPENOFC_V552_MATERIALIZATION=PASS "
        "refantasy=CURRENT_SCREEN_RESET final=LINEAGE_SUBSET "
        "row_verify=RAW_VISUAL_EXACT pacing_ms=250 ui=SCREEN_ORDER"
    )


if __name__ == "__main__":
    main()
