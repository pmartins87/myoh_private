from __future__ import annotations

from strategic_advantage_model import DeterministicReservoir, SparseActionAdvantageModel
from strategic_policy_distillation import is_holdout_key
from strategic_teacher_anchors import (
    add_invariant_r4_teachers,
    evaluate_exact_r4_anchors,
    exact_r4_anchor,
    generate_exact_r4_anchors,
    reachable_dealer_r4_state,
)


def _find_partition(base_seed: int = 20260826):
    train = []
    holdout = []
    all_anchors = []
    # Search a deterministic bounded calibration stream.  Invariant R4 states
    # are common, but the test never assumes a particular SHA bucket assignment.
    for batch in range(8):
        anchors = generate_exact_r4_anchors(base_seed + batch * 1000003, 8)
        all_anchors.extend(anchors)
        for anchor in anchors:
            if not anchor.continuation_invariant:
                continue
            (holdout if is_holdout_key(anchor.key) else train).append(anchor)
        if train and holdout:
            return tuple(all_anchors), tuple(train), tuple(holdout)
    raise AssertionError("deterministic R4 calibration stream lacked train/holdout invariant states")


def test_reachable_dealer_r4_state_and_exact_surface() -> None:
    state = reachable_dealer_r4_state(11)
    assert state.round_index == 4
    assert state.actor == 1
    assert state.boards[0].count() == 13
    assert state.boards[1].count() == 11
    anchor = exact_r4_anchor(state)
    assert anchor.action_keys
    assert len(anchor.action_keys) == len(anchor.points) == len(anchor.fantasy_cards)
    assert anchor.best_points == max(anchor.points)
    assert anchor.optimal_indices
    assert all(0 <= index < len(anchor.points) for index in anchor.optimal_indices)


def test_bellman_safe_teacher_rejects_transition_variant_states() -> None:
    anchors, train, holdout = _find_partition()
    replay = DeterministicReservoir(capacity=20000, seed=1)
    report = add_invariant_r4_teachers(anchors, replay)
    expected_train = [
        anchor for anchor in anchors
        if anchor.continuation_invariant and not is_holdout_key(anchor.key)
    ]
    expected_actions = sum(len(anchor.action_keys) for anchor in expected_train)
    assert report["states"] == len(expected_train)
    assert report["action_examples"] == expected_actions
    assert report["skipped_holdout"] == len(holdout)
    assert all(item.source == "exact_r4_continuation_invariant" for item in replay.items)

    # Each admitted state has a policy target whose action probabilities sum to 1.
    cursor = 0
    for anchor in expected_train:
        count = len(anchor.action_keys)
        targets = [item.target for item in replay.items[cursor:cursor + count]]
        assert abs(sum(targets) - 1.0) < 1e-12
        optimal = set(anchor.optimal_indices)
        for index, target in enumerate(targets):
            assert (target > 0.0) == (index in optimal)
        cursor += count


def test_holdout_exact_r4_metrics_are_well_formed() -> None:
    anchors, _train, holdout = _find_partition(20260827)
    model = SparseActionAdvantageModel(buckets=1024, seed=9)
    metrics = evaluate_exact_r4_anchors(model, anchors, holdout_only=True)
    assert metrics.states == len(holdout)
    assert metrics.actions >= metrics.states
    assert 0.0 <= metrics.optimal_top1_accuracy <= 1.0
    assert 0.0 <= metrics.mean_optimal_probability_mass <= 1.0
    assert metrics.mean_greedy_point_regret >= 0.0
    assert metrics.mean_expected_point_regret >= -1e-12
    assert metrics.mean_uniform_point_regret >= -1e-12
    # An untrained model is uniform, so its expected regret must exactly match
    # the explicitly computed uniform-policy baseline.
    assert abs(
        metrics.mean_expected_point_regret - metrics.mean_uniform_point_regret
    ) < 1e-12


def main() -> None:
    test_reachable_dealer_r4_state_and_exact_surface()
    test_bellman_safe_teacher_rejects_transition_variant_states()
    test_holdout_exact_r4_metrics_are_well_formed()
    print(
        "OPENOFC_M4C3_EXACT_R4_ANCHORS=PASS "
        "scope=DEALER_R4 continuation=ACTION_INVARIANT_ONLY "
        "holdout=SHA256_DISJOINT authority=EXACT_ANY_CONTINUATION"
    )


if __name__ == "__main__":
    main()
