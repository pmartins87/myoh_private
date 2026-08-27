from __future__ import annotations

from pathlib import Path
import tempfile

from audit_strategic_convergence import audit
from strategic_cfr import OutcomeSamplingMCCFR
from strategic_cfr_runner import (
    load_runner_checkpoint,
    run_chunked,
    save_runner_checkpoint,
    state_digest,
)
from strategic_suit_symmetry import SuitCanonicalOutcomeSamplingMCCFR


def _assert_same_solver(a: OutcomeSamplingMCCFR, b: OutcomeSamplingMCCFR) -> None:
    assert type(a) is type(b)
    assert a.iterations == b.iterations
    assert a.episodes == b.episodes
    assert a.epsilon == b.epsilon
    assert a.cfr_plus == b.cfr_plus
    assert a.rng.getstate() == b.rng.getstate()
    assert a.nodes.keys() == b.nodes.keys()
    for key in a.nodes:
        x, y = a.nodes[key], b.nodes[key]
        assert x.action_keys == y.action_keys
        assert x.cumulative_regrets == y.cumulative_regrets
        assert x.cumulative_policy == y.cumulative_policy
        assert x.visits == y.visits
    assert state_digest(a) == state_digest(b)


def _deterministic_resume_for(cls, seed: int, iterations: int) -> None:
    uninterrupted = cls(seed=seed, epsilon=0.6, cfr_plus=True)
    uninterrupted.run(iterations)

    first = iterations // 2
    split = cls(seed=seed, epsilon=0.6, cfr_plus=True)
    split.run(first)
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "checkpoint.json.gz"
        sha = save_runner_checkpoint(split, p)
        assert len(sha) == 64
        # Re-saving an unchanged state is byte-identical because gzip mtime is pinned.
        raw1 = p.read_bytes()
        sha2 = save_runner_checkpoint(split, p)
        raw2 = p.read_bytes()
        assert sha2 == sha and raw2 == raw1

        resumed, restored_sha = load_runner_checkpoint(p)
        assert restored_sha == sha
        resumed.run(iterations - first)
        _assert_same_solver(uninterrupted, resumed)


def test_deterministic_resume_equals_uninterrupted_raw() -> None:
    _deterministic_resume_for(OutcomeSamplingMCCFR, seed=101, iterations=6)


def test_deterministic_resume_equals_uninterrupted_suit24() -> None:
    _deterministic_resume_for(
        SuitCanonicalOutcomeSamplingMCCFR, seed=202, iterations=4
    )


def test_chunked_checkpoint_and_stability_audit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        p4 = root / "n4.json.gz"
        p8 = root / "n8.json.gz"
        solver = SuitCanonicalOutcomeSamplingMCCFR(
            seed=303, epsilon=0.6, cfr_plus=True
        )
        r4 = run_chunked(
            solver,
            additional_iterations=4,
            checkpoint_every=2,
            checkpoint=p4,
        )
        assert r4["iterations"] == 4 and r4["checkpoint_writes"] == 2
        assert r4["solver_kind"] == "suit24-exact"
        save_runner_checkpoint(solver, p4)
        solver.run(4)
        save_runner_checkpoint(solver, p8)
        report = audit(p4, p8)
        assert report["authority"] == "STABILITY_ONLY_NOT_EXPLOITABILITY"
        assert report["a"]["iterations"] == 4
        assert report["b"]["iterations"] == 8
        assert 0.0 <= report["weighted_mean_tv"] <= 1.0
        assert 0.0 <= report["weighted_greedy_overlap"] <= 1.0

        identical = audit(p8, p8)
        assert identical["weighted_mean_tv"] == 0.0
        assert identical["weighted_greedy_overlap"] == 1.0
        assert identical["new_infosets_in_b"] == 0
        assert identical["lost_infosets_from_a"] == 0


def main() -> None:
    test_deterministic_resume_equals_uninterrupted_raw()
    test_deterministic_resume_equals_uninterrupted_suit24()
    test_chunked_checkpoint_and_stability_audit()
    print("OPENOFC_STRATEGIC_RUNNER_TEST=PASS")


if __name__ == "__main__":
    main()
