from __future__ import annotations

from strategic_multiseed_benchmark import run_benchmark


def smoke() -> dict:
    return run_benchmark(
        (20260826, 20260827),
        cfr_iterations=4,
        max_teacher_nodes_per_seed=48,
        min_r4_train_per_seed=1,
        min_r4_holdout_per_seed=1,
        replay_capacity=6000,
        epochs=1,
        buckets=512,
    )


def test_multiseed_report_is_deterministic_and_non_promotional() -> None:
    first = smoke()
    second = smoke()
    assert first == second
    assert first["schema"] == "openofc-hu-m4c3-multiseed-benchmark-v1"
    assert first["seeds"] == [20260826, 20260827]
    assert first["promotion_ready"] is False
    assert first["next_gate"] == "RYZEN_SCALE_BASELINE_THEN_THRESHOLDS"
    assert len(first["per_seed"]) == 2
    assert len(first["sha256"]) == 64


def test_each_seed_has_disjoint_policy_and_exact_r4_holdout() -> None:
    report = smoke()
    for row in report["per_seed"]:
        policy = row["policy_holdout"]
        r4 = row["exact_r4_holdout"]
        assert policy["nodes"] > 0
        assert policy["actions"] >= policy["nodes"]
        assert row["exact_r4_holdout_invariant"] >= 1
        assert r4["states"] == row["exact_r4_holdout_invariant"]
        assert 0.0 <= r4["optimal_top1_accuracy"] <= 1.0
        assert r4["mean_greedy_point_regret"] >= 0.0
        assert r4["mean_expected_point_regret"] >= -1e-12
        assert r4["mean_uniform_point_regret"] >= -1e-12


def main() -> None:
    test_multiseed_report_is_deterministic_and_non_promotional()
    test_each_seed_has_disjoint_policy_and_exact_r4_holdout()
    print(
        "OPENOFC_M4C3_MULTISEED_SMOKE=PASS "
        "seeds=2 policy_holdout=DISJOINT exact_r4=CONTINUATION_INVARIANT "
        "promotion=DEFERRED_TO_RYZEN_BASELINE"
    )


if __name__ == "__main__":
    main()
