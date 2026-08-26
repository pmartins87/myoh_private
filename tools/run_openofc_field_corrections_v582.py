from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V582_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.8.2 failed rc={process.returncode}: {relative}")


def main() -> None:
    run("tools/run_openofc_field_corrections_v581.py")
    run("tools/normalize_openofc_v582_runtime_gate.py")
    run("tools/apply_openofc_field_corrections_v582.py")
    run("tools/test_openofc_field_corrections_v582.py")
    print(
        "OPENOFC_V582_MATERIALIZATION=PASS "
        "field_failure=FANTASY_BOOTSTRAP_AND_STALE_TRANSACTION "
        "count_alignment=MISSING1_EXTRA2 "
        "bootstrap=EMPTY_OCCUPANCY_FIRST "
        "runtime=F14_17_SEMANTIC_NEW_HAND_RELEASE "
        "strategy=V581_PRESERVED tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
