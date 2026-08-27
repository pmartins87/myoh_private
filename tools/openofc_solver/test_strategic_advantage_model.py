from __future__ import annotations

import json
import tempfile
from pathlib import Path
import random

from strategic_advantage_model import (
    DeterministicReservoir,
    ReplayExample,
    SparseActionAdvantageModel,
    interaction_terms,
    load_checkpoint,
    save_checkpoint,
)
from strategic_cfr import HUState, sample_deal_plan
from strategic_feature_encoder import (
    encode_canonical_action_key,
    encode_canonical_state_key,
)
from strategic_policy_distillation import (
    distill_solver_nodes,
    evaluate_model_on_solver,
)
from strategic_suit_symmetry import SuitCanonicalOutcomeSamplingMCCFR, canonical_node_view


def opening_features(seed: int = 1):
    state = HUState(plan=sample_deal_plan(random.Random(seed)))
    key, pairs, _ = canonical_node_view(state)
    return key, encode_canonical_state_key(key), [
        encode_canonical_action_key(action_key) for action_key, _ in pairs
    ]


def test_interactions_are_action_conditioned_and_bounded() -> None:
    _key, state_features, actions = opening_features(1)
    first = interaction_terms(state_features, actions[0], buckets=256)
    second = interaction_terms(state_features, actions[1], buckets=256)
    assert first != second
    assert min(index for index, _ in first) >= 0
    # 1 bias + 216 direct action coordinates + 256 interaction buckets.
    assert max(index for index, _ in first) < 1 + 216 + 256


def test_public_history_changes_cross_terms_for_same_action() -> None:
    key, state_features, actions = opening_features(2)
    payload = json.loads(key)
    card = payload["incoming"][0]
    payload["public_history"] = [[0, 0, [[card, 0]]]]
    changed_key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    changed_state = encode_canonical_state_key(changed_key)
    assert state_features != changed_state
    assert interaction_terms(state_features, actions[0], buckets=1024) != interaction_terms(
        changed_state, actions[0], buckets=1024
    )


def make_example(seed: int, target: float) -> ReplayExample:
    _key, state_features, actions = opening_features(seed)
    return ReplayExample(
        state_features=state_features,
        action_features=actions[0],
        target=target,
        source="selftest",
    )


def test_deterministic_reservoir_resume_identity() -> None:
    left = DeterministicReservoir(capacity=5, seed=99)
    for i in range(12):
        left.add(make_example(10 + i, (i % 3) / 2.0))
    resumed = DeterministicReservoir.from_payload(left.payload())
    for i in range(12, 24):
        example = make_example(10 + i, (i % 3) / 2.0)
        left.add(example)
        resumed.add(example)
    assert left.payload() == resumed.payload()


def test_sparse_model_learns_action_specific_target() -> None:
    _key, state_features, actions = opening_features(40)
    replay = DeterministicReservoir(capacity=16, seed=1)
    replay.add(ReplayExample(state_features, actions[0], 1.0, source="positive"))
    replay.add(ReplayExample(state_features, actions[1], 0.0, source="negative"))
    model = SparseActionAdvantageModel(buckets=1024, learning_rate=0.12, seed=7)
    model.fit(replay, epochs=30)
    p0 = model.predict_features(state_features, actions[0])
    p1 = model.predict_features(state_features, actions[1])
    assert p0 > p1
    policy = model.policy(state_features, actions[:2])
    assert policy[0] > policy[1]
    assert abs(sum(policy) - 1.0) < 1e-12


def test_checkpoint_is_exactly_resumable() -> None:
    replay = DeterministicReservoir(capacity=8, seed=123)
    for i in range(6):
        replay.add(make_example(60 + i, i / 5.0))
    model = SparseActionAdvantageModel(buckets=512, seed=321)
    model.fit(replay, epochs=3)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "m4c2.json.gz"
        save_checkpoint(path, model, replay)
        restored_model, restored_replay = load_checkpoint(path)
        assert restored_model.payload() == model.payload()
        assert restored_replay.payload() == replay.payload()
        model.fit(replay, epochs=2)
        restored_model.fit(restored_replay, epochs=2)
        assert restored_model.payload() == model.payload()


def test_exact_tabular_distillation_has_disjoint_holdout() -> None:
    solver = SuitCanonicalOutcomeSamplingMCCFR(seed=20260826, epsilon=0.6)
    solver.run(12)
    assert solver.nodes
    replay = DeterministicReservoir(capacity=768, seed=20260826)
    report = distill_solver_nodes(solver, replay, max_nodes=4)
    assert report["nodes"] == 4
    assert report["action_examples"] > 0
    assert replay.items
    model = SparseActionAdvantageModel(buckets=2048, learning_rate=0.06, seed=20260826)
    model.fit(replay, epochs=2)
    metrics = evaluate_model_on_solver(model, solver, holdout_only=True, max_nodes=8)
    assert metrics.nodes > 0
    assert metrics.actions >= metrics.nodes
    assert 0.0 <= metrics.top1_accuracy <= 1.0
    assert metrics.mean_policy_l1 >= 0.0
    assert metrics.mean_policy_rmse >= 0.0


def main() -> None:
    test_interactions_are_action_conditioned_and_bounded()
    test_public_history_changes_cross_terms_for_same_action()
    test_deterministic_reservoir_resume_identity()
    test_sparse_model_learns_action_specific_target()
    test_checkpoint_is_exactly_resumable()
    test_exact_tabular_distillation_has_disjoint_holdout()
    print(
        "OPENOFC_M4C2_ACTION_ADVANTAGE=PASS "
        "cross=STATE_X_ACTION replay=BOUNDED_DETERMINISTIC checkpoint=EXACT_RESUME "
        "teacher=EXACT_TABULAR holdout=DISJOINT"
    )


if __name__ == "__main__":
    main()
