from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(relative: str) -> None:
    print(f"V551_RUN={relative}", flush=True)
    proc = subprocess.run([sys.executable, str(ROOT / relative)], cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"v5.5.1 failed rc={proc.returncode}: {relative}")


def main() -> None:
    run("tools/run_openofc_fantasy_counted_text_v550.py")
    run("tools/apply_openofc_v551_paired_tablemap_ui.py")
    run("tools/test_openofc_v551_paired_field_bundle.py")
    print(
        "OPENOFC_V551_MATERIALIZATION=PASS "
        "runtime=V550_COUNTED_TEXT ui_contract=5 tablemap=PAIRED_IN_ARTIFACT"
    )


if __name__ == "__main__":
    main()
