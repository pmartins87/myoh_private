from __future__ import annotations

import random
import tempfile
from pathlib import Path

from engine import Board
from fantasy_fantasy_bootstrap import build_bootstrap_targets
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from fantasy_fantasy_payoff import build_exact_support_payoff_matrix
from fantasy_fantasy_policy_model import (
    AUTHORITY,
    DeterministicFantasyReplay,
    SparseFantasyActionValueModel,
    load_checkpoint,
    save_checkpoint,
)
from hu_continuation import HUContinuationState, zero_continuation_values


def meta() -> HUContinuationState:
    return HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=14)


def two_arrangements(packet):
    cards = list(packet)
    a = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    cards[1], cards[8] = cards[8], cards[1]
    b = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    return a, b


def fixture():
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(20260828), current)
    )
    support0 = two_arrangements(world.plan.packet_for(0))
    support1 = two_arrangements(world.plan.packet_for(1))
    matrix = build_exact_support_payoff_matrix(
        world, support0, support1, zero_continuation_values()
    )
    return world, support0, support1, matrix


def test_bootstrap_targets_equal_exact_matrix_expectations() -> None:
    world, support0, support1, matrix = fixture()
    batch = build_bootstrap_targets(world, support0, support1, matrix)
    assert batch.example_count == 4
    assert batch.p0_opponent_policy == (0.5, 0.5)
    assert batch.p1_opponent_policy == (0.5, 0.5)
    for i, example in enumerate(batch.p0_examples):
        expected = 0.5 * (matrix.p0_values[i][0] + matrix.p0_values[i][1])
        assert abs(example.target - expected) <= 1e-9
    for j, example in enumerate(batch.p1_examples):
        expected = -0.5 * (matrix.p0_values[0][j] + matrix.p0_values[1][j])
        assert abs(example.target - expected) <= 1e-9


def test_declared_nonuniform_opponent_mixtures_change_targets_exactly() -> None:
    world, support0, support1, matrix = fixture()
    batch = build_bootstrap_targets(
        world,
        support0,
        support1,
        matrix,
        p0_opponent_policy=(3.0, 1.0),
        p1_opponent_policy=(1.0, 3.0),
    )
    assert batch.p0_opponent_policy == (0.75, 0.25)
    assert batch.p1_opponent_policy == (0.25, 0.75)
    assert abs(
        batch.p0_examples[0].target
        - (0.75 * matrix.p0_values[0][0] + 0.25 * matrix.p0_values[0][1])
    ) <= 1e-9
    assert abs(
        batch.p1_examples[0].target
        + (0.25 * matrix.p0_values[0][0] + 0.75 * matrix.p0_values[1][0])
    ) <= 1e-9


def test_sparse_model_training_is_deterministic_and_policy_is_valid() -> None:
    world, support0, support1, matrix = fixture()
    batch = build_bootstrap_targets(world, support0, support1, matrix)
    examples = batch.p0_examples + batch.p1_examples

    def train_once():
        replay = DeterministicFantasyReplay(capacity=16, seed=77)
        replay.extend(examples)
        model = SparseFantasyActionValueModel(buckets=1024, seed=991)
        stats = model.fit(replay, epochs=4)
        return model, replay, stats

    model_a, replay_a, stats_a = train_once()
    model_b, replay_b, stats_b = train_once()
    assert model_a.payload() == model_b.payload()
    assert replay_a.payload() == replay_b.payload()
    assert stats_a == stats_b
    assert model_a.payload()["authority"] == AUTHORITY

    state = batch.p0_examples[0].state_features
    actions = [example.action_features for example in batch.p0_examples]
    policy = model_a.policy(state, actions)
    assert len(policy) == len(actions)
    assert all(0.0 < p < 1.0 for p in policy)
    assert abs(sum(policy) - 1.0) <= 1e-12


def test_checkpoint_roundtrip_preserves_model_and_replay() -> None:
    world, support0, support1, matrix = fixture()
    batch = build_bootstrap_targets(world, support0, support1, matrix)
    replay = DeterministicFantasyReplay(capacity=16, seed=19)
    replay.extend(batch.p0_examples + batch.p1_examples)
    model = SparseFantasyActionValueModel(buckets=1024, seed=20)
    model.fit(replay, epochs=2)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "m4q.json.gz"
        save_checkpoint(path, model, replay)
        loaded_model, loaded_replay = load_checkpoint(path)
        assert loaded_model.payload() == model.payload()
        assert loaded_replay.payload() == replay.payload()


def main() -> None:
    test_bootstrap_targets_equal_exact_matrix_expectations()
    test_declared_nonuniform_opponent_mixtures_change_targets_exactly()
    test_sparse_model_training_is_deterministic_and_policy_is_valid()
    test_checkpoint_roundtrip_preserves_model_and_replay()
    print(
        "OPENOFC_M4Q_SEALED_POLICY_BOOTSTRAP=PASS "
        "targets=EXACT_GIVEN_DECLARED_MIXTURE model=OWN_INFO_ONLY "
        "resume=DETERMINISTIC authority=BOOTSTRAP_NOT_EQUILIBRIUM"
    )


if __name__ == "__main__":
    main()
