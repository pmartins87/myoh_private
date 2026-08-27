from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V560_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.6.0 failed rc={process.returncode}: {relative}")


def main() -> None:
    run("tools/run_openofc_fantasy_live_recovery_v552.py")
    run("tools/apply_openofc_exact_r4_teacher_v560.py")
    run("tools/test_openofc_exact_r4_teacher_v560.py")
    print(
        "OPENOFC_V560_MATERIALIZATION=PASS "
        "terminal_oracle=EXACT r4=EXHAUSTIVE_27 "
        "replacement=PARETO_SAFE tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
