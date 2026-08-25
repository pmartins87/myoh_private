from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V570_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.7.0 failed rc={process.returncode}: {relative}")


def main() -> None:
    run("tools/openofc_solver/apply_m1b_joker_semantics.py")
    run("tools/run_openofc_exact_r4_teacher_v560.py")
    run("tools/apply_openofc_exact_fantasy_v570.py")
    run("tools/test_openofc_exact_fantasy_v570.py")
    print(
        "OPENOFC_V570_MATERIALIZATION=PASS "
        "fantasy_14_17=EXACT_SEARCH authority=UNIVERSAL_DOMINANCE "
        "r4=PARETO_SAFE tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
