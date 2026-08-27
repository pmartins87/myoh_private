from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V580_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.8.0 failed rc={process.returncode}: {relative}")


def main() -> None:
    run("tools/run_openofc_exact_fantasy_v570.py")
    run("tools/apply_openofc_active_identity_recovery_v580.py")
    run("tools/test_openofc_active_identity_recovery_v580.py")
    print(
        "OPENOFC_V580_MATERIALIZATION=PASS "
        "identity_recovery=ACTIVE_BOUNDED_REPLAYED "
        "reacquire=NONABSORBING intelligence=V570_PRESERVED "
        "tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
