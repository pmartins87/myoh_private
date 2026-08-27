from __future__ import annotations

"""Exact-resume tests for the continuation-coupled strategic runner."""

from pathlib import Path
import tempfile

from hu_continuation import HUContinuationState, zero_continuation_values
from strategic_continuation_cfr import ContinuationObjective, SuitCanonicalContinuationMCCFR
from strategic_continuation_runner import (
    load_checkpoint,
    save_checkpoint,
    state_digest,
)


def make_solver() -> SuitCanonicalContinuationMCCFR:
    return SuitCanonicalContinuationMCCFR(
        objective=ContinuationObjective(
            HUContinuationState(1, 0, 0), zero_continuation_values()
        ),
        seed=20260825,
        epsilon=0.6,
        cfr_plus=True,
    )


def test_exact_resume_matches_uninterrupted_random_stream() -> None:
    uninterrupted = make_solver()
    uninterrupted.run(2)
    uninterrupted_digest = state_digest(uninterrupted)

    split = make_solver()
    split.run(1)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "m4b.json.gz"
        digest_n1 = save_checkpoint(split, path)
        restored, restored_digest = load_checkpoint(path)
        assert restored_digest == digest_n1
        assert restored.objective.fingerprint == split.objective.fingerprint
        restored.run(1)
        resumed_digest = state_digest(restored)

    assert resumed_digest == uninterrupted_digest


def test_checkpoint_rejects_objective_replacement_by_construction() -> None:
    solver = make_solver()
    solver.run(1)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "m4b.json.gz"
        save_checkpoint(solver, path)
        restored, _ = load_checkpoint(path)
        assert restored.objective.current_state == HUContinuationState(1, 0, 0)
        assert dict(restored.objective.values) == zero_continuation_values()


def main() -> None:
    test_exact_resume_matches_uninterrupted_random_stream()
    test_checkpoint_rejects_objective_replacement_by_construction()
    print(
        "OPENOFC_M4B_CONTINUATION_RUNNER=PASS "
        "resume=BIT_EXACT_RANDOM_STREAM objective=PINNED_SHA256 solver=suit24-continuation-exact"
    )


if __name__ == "__main__":
    main()
