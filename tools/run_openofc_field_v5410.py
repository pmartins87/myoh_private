from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(rel: str) -> None:
    print(f"V5410_RUN={rel}", flush=True)
    proc = subprocess.run([sys.executable, str(ROOT / rel)], cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"v5.4.10 failed rc={proc.returncode}: {rel}")


def main() -> None:
    # Preserve the entire authoritative v5.3 -> v5.4.9 lineage first.
    run("tools/run_openofc_field_v549.py")
    run("tools/apply_openofc_fantasy_field_v5410.py")
    run("tools/apply_openofc_fantasy_lineage_match_v5410b.py")
    run("tools/test_openofc_fantasy_field_v5410.py")
    print(
        "OPENOFC_V5410_MATERIALIZATION=PASS "
        "v549_lineage=PASS field_fan_profile=PASS "
        "empty_slot_gate=PASS partial_lineage=PASS weak_glyph_lineage=PASS"
    )


if __name__ == "__main__":
    main()
