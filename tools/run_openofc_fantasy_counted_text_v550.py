from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(rel: str) -> None:
    print(f"V550_RUN={rel}", flush=True)
    proc = subprocess.run([sys.executable, str(ROOT / rel)], cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"v5.5.0 failed rc={proc.returncode}: {rel}")


def main() -> None:
    # v5.5.0 is deliberately an identity-routing change ON TOP OF the complete
    # field-certified source lineage through v5.4.10. It does not bypass any of
    # the bounded-input, opponent-occlusion, arrangement or continuity gates.
    run("tools/run_openofc_field_v5410.py")
    run("tools/apply_openofc_fantasy_counted_text_v550.py")
    run("tools/apply_openofc_fantasy_counted_text_optin_v550a.py")
    run("tools/test_openofc_fantasy_counted_text_v550.py")
    print(
        "OPENOFC_V550_MATERIALIZATION=PASS "
        "v5410_lineage=PASS loose_count=GEOMETRY_ONLY identity=TABLEMAP_T7 "
        "tablemap_opt_in=EXPLICIT stable_counts=6,7,8,9,11,12,13,14,15,16,17 "
        "final_1_4=LINEAGE_COMPLEMENT"
    )


if __name__ == "__main__":
    main()
