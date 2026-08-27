from __future__ import annotations

import random

from engine import Board
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from fantasy_fantasy_payoff import build_exact_support_payoff_matrix
from fantasy_fantasy_policy_model import (
    DeterministicFantasyReplay,
    SparseFantasyActionValueModel,
)
from fantasy_fantasy_selfplay import (
    AUTHORITY,
    SealedSupportEpisode,
    exact_selfplay_targets,
    policy_api_has_hidden_opponent_argument,
    snapshot_episode_policy,
    train_selfplay_iteration,
)
from hu_continuation import HUContinuationState, zero_continuation_values


def meta() -> HUContinuationState:
    return HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=14)


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
    cards[0], cards[9] = cards[9], cards[0]
    b = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    return a, b


def episode(seed: int) -> SealedSupportEpisode:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(seed), current)
    )
    support0 = two_arrangements(world.plan.packet_for(0))
    support1 = two_arrangements(world.plan.packet_for(1))
    matrix = build_exact_support_payoff_matrix(
        world, support0, support1, zero_continuation_values()
    )
    return SealedSupportEpisode(world, support0, support1, matrix)


def test_inference_api_has_no_hidden_opponent_surface() -> None:
    assert not policy_api_has_hidden_opponent_argument()


def test_untrained_model_is_uniform_and_targets_use_frozen_policy() -> None:
    row = episode(20260828)
    model = SparseFantasyActionValueModel(buckets=1024, seed=77)
    snapshot, batch = exact_selfplay_targets(model, row)
    assert snapshot.p0_policy == (0.5, 0.5)
    assert snapshot.p1_policy == (0.5, 0.5)
    assert batch.p0_opponent_policy == snapshot.p1_policy
    assert batch.p1_opponent_policy == snapshot.p0_policy
    for i, example in enumerate(batch.p0_examples):
        expected = 0.5 * (row.matrix.p0_values[i][0] + row.matrix.p0_values[i][1])
        assert abs(example.target - expected) <= 1e-9


def test_selfplay_iteration_is_deterministic_and_keeps_bootstrap_authority() -> None:
    rows = (episode(3001), episode(3002))

    def run_once():
        model = SparseFantasyActionValueModel(buckets=1024, seed=1234)
        replay = DeterministicFantasyReplay(capacity=64, seed=4321)
        report = train_selfplay_iteration(
            model,
            replay,
            rows,
            epochs=3,
            temperature=1.0,
        )
        return model, replay, report

    model_a, replay_a, report_a = run_once()
    model_b, replay_b, report_b = run_once()
    assert model_a.payload() == model_b.payload()
    assert replay_a.payload() == replay_b.payload()
    assert report_a == report_b
    assert report_a.authority == AUTHORITY
    assert report_a.episodes == 2
    assert report_a.examples_added == 8
    assert report_a.replay_seen == 8
    assert report_a.mean_support_deviation_before >= 0.0
    assert report_a.mean_support_deviation_after >= 0.0


def test_second_iteration_uses_updated_sealed_policy() -> None:
    row = episode(919)
    model = SparseFantasyActionValueModel(buckets=1024, seed=919)
    replay = DeterministicFantasyReplay(capacity=64, seed=920)
    before = snapshot_episode_policy(model, row)
    train_selfplay_iteration(model, replay, (row,), epochs=4)
    after = snapshot_episode_policy(model, row)
    assert before.p0_policy == (0.5, 0.5)
    assert before.p1_policy == (0.5, 0.5)
    assert abs(sum(after.p0_policy) - 1.0) <= 1e-12
    assert abs(sum(after.p1_policy) - 1.0) <= 1e-12
    _snapshot2, batch2 = exact_selfplay_targets(model, row)
    assert batch2.p0_opponent_policy == after.p1_policy
    assert batch2.p1_opponent_policy == after.p0_policy


def main() -> None:
    test_inference_api_has_no_hidden_opponent_surface()
    test_untrained_model_is_uniform_and_targets_use_frozen_policy()
    test_selfplay_iteration_is_deterministic_and_keeps_bootstrap_authority()
    test_second_iteration_uses_updated_sealed_policy()
    print(
        "OPENOFC_M4R_GENERALIZED_SEALED_SELFPLAY=PASS "
        "inference=OWN_INFO_ONLY labels=EXACT_CURRENT_POLICY_MATRIX "
        "updates=SYNCHRONOUS deterministic=YES authority=NOT_EQUILIBRIUM"
    )


if __name__ == "__main__":
    main()
