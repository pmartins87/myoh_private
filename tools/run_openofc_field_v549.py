from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import tools.apply_openofc_runtime_repair as runtime_repair

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = [
    "tools/apply_openofc_log248_repair.py",
    "tools/run_openofc_gameflow_v2.py",
    "tools/apply_openofc_normal_flow_v3.py",
    "tools/apply_openofc_phase_flow_v4.py",
    "tools/apply_openofc_phase_flow_v41.py",
    "tools/apply_openofc_round_discard_exit_v42.py",
    "tools/apply_openofc_normal_completion_v43.py",
    "tools/apply_openofc_simultaneous_dealer_v44.py",
    "tools/run_openofc_fantasy_v5.py",
    "tools/apply_openofc_opponent_history_v52.py",
    "tools/run_openofc_smart_policy_v53.py",
    "tools/run_openofc_runtime_continuity_v54.py",
    "tools/apply_openofc_partial_reconnect_v542b.py",
    "tools/apply_openofc_dealer_recovery_v542c.py",
    "tools/normalize_openofc_dealer_recovery_v542c.py",
    "tools/run_openofc_generic_fantasy_v543.py",
    "tools/normalize_openofc_generic_fantasy_v543.py",
    "tools/apply_openofc_fantasy_source_identity_v543g.py",
    "tools/apply_openofc_fantasy_confirm_guard_v543h.py",
    "tools/apply_openofc_field_recovery_v544.py",
    "tools/apply_openofc_field_recovery_v544b.py",
    "tools/apply_openofc_full_replan_v544c.py",
    "tools/apply_openofc_provisional_supersession_v544d.py",
    "tools/apply_openofc_identity_refinement_v544e.py",
    "tools/normalize_openofc_observability_input_v545pre.py",
    "tools/apply_openofc_observability_deghost_v545.py",
    "tools/normalize_openofc_observability_deghost_v545a.py",
    "tools/apply_openofc_fantasy_field_v546.py",
    "tools/test_openofc_fantasy_field_v546.py",
    "tools/apply_openofc_fantasy_bounded_click_v547.py",
    "tools/test_openofc_fantasy_bounded_click_v547.py",
    "tools/apply_openofc_fantasy_bounded_input_guard_v548.py",
    "tools/test_openofc_fantasy_bounded_input_guard_v548.py",
    "tools/apply_openofc_fantasy_opponent_occlusion_v549.py",
    "tools/test_openofc_fantasy_opponent_occlusion_v549.py",
]


def run_script(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        raise SystemExit(f"v5.4.9 materialization missing script: {rel}")
    print(f"V549_RUN={rel}", flush=True)
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"v5.4.9 materialization failed rc={proc.returncode}: {rel}")


def main() -> None:
    # The historical runtime repair module exposes functions rather than a
    # single script entrypoint. Apply it exactly as the prior authoritative
    # gates do before executing the frozen materialization sequence.
    runtime_repair.patch_transform()
    runtime_repair.patch_opponent_discards()
    runtime_repair.patch_capture()
    print("V549_RUN=tools.apply_openofc_runtime_repair:PASS", flush=True)

    for rel in SCRIPTS:
        run_script(rel)

    print(
        "OPENOFC_V549_MATERIALIZATION=PASS "
        "v548_regression=PASS opponent_occlusion=PASS"
    )


if __name__ == "__main__":
    main()
