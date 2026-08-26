from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTELLIGENCE_FILES = (
    "OpenHoldem/COFCBaselinePolicy.cpp",
    "OpenHoldem/COFCDecisionPolicy.cpp",
    "OpenHoldem/COFCExactEvaluator.cpp",
    "OpenHoldem/COFCFantasyExactSolver.cpp",
    "OpenHoldem/COFCR4ExactTeacher.cpp",
)


def run(relative: str) -> None:
    print(f"V583_RUN={relative}", flush=True)
    process = subprocess.run(
        [sys.executable, str(ROOT / relative)], cwd=ROOT, check=False
    )
    if process.returncode != 0:
        raise SystemExit(f"v5.8.3 failed rc={process.returncode}: {relative}")


def snapshot() -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in INTELLIGENCE_FILES:
        data = (ROOT / relative).read_bytes()
        result[relative] = hashlib.sha256(data).hexdigest()
    return result


def main() -> None:
    run("tools/run_openofc_field_corrections_v582.py")
    before = snapshot()
    run("tools/apply_openofc_field_observability_v583.py")
    after = snapshot()
    if before != after:
        changed = sorted(k for k in before if before[k] != after[k])
        raise SystemExit(
            "v5.8.3 field-only layer changed intelligence sources: " + ", ".join(changed)
        )
    run("tools/test_openofc_field_observability_v583.py")
    print(
        "OPENOFC_V583_MATERIALIZATION=PASS "
        "track=FIELD_RELIABILITY product=5.8.3 tablemap_asset=5.5.2 "
        "ui=VERSIONED_STATUS_TRUTHFUL intelligence_hashes=UNCHANGED"
    )


if __name__ == "__main__":
    main()
