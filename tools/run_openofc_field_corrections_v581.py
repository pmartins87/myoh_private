from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V581_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.8.1 failed rc={process.returncode}: {relative}")


def main() -> None:
    run("tools/run_openofc_active_identity_recovery_v580.py")
    run("tools/apply_openofc_field_corrections_v581.py")
    run("tools/test_openofc_field_corrections_v581.py")
    print(
        "OPENOFC_V581_MATERIALIZATION=PASS "
        "fantasy_stage=SINGLE_DELTA_EXACT "
        "r4=HIDDEN_OPPONENT_NONFOUL_SAFETY "
        "intelligence=V570_PLUS_R4_SAFETY tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
