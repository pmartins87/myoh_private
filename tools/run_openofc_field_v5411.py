from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        raise SystemExit(f"v5.4.11 missing script: {rel}")
    print(f"V5411_RUN={rel}", flush=True)
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"v5.4.11 failed rc={proc.returncode}: {rel}")


def main() -> None:
    # v5.4.11 deliberately pivots from the experimental v5.4.10 native-pixel
    # branch. Start from the last field-proven runtime lineage (v5.4.9), then
    # add only the count-selected TableMap text route.
    run("tools/run_openofc_field_v549.py")
    run("tools/apply_openofc_fantasy_tablemap_text_v5411.py")
    run("tools/test_openofc_fantasy_tablemap_text_v5411.py")
    print(
        "OPENOFC_V5411_MATERIALIZATION=PASS "
        "base=v5.4.9 text_route=COUNT_SELECTED native_fallback=PRESERVED "
        "final_unused=LINEAGE_CARRY"
    )


if __name__ == "__main__":
    main()
