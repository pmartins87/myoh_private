from __future__ import annotations

import random

from engine import Board
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from hu_continuation import (
    HUContinuationState,
    all_states,
    zero_continuation_values,
)
from m4w_outcome_model import SparseFantasyOutcomeModel
from m5b_fantasy_selfplay import (
    ContinuationAwareEpisode,
    exact_outcome_targets_for_snapshot,
    snapshot_policy,
    train_selfplay_iteration,
)


def three_arrangements(packet):
    cards = list(packet)
    out = []
    for left, right in ((0, 9), (1, 10), (2, 11)):
        x = list(cards)
        x[left], x[right] = x[right], x[left]
        out.append(
            arrangement_from_board(
                packet,
                Board(
                    top=tuple(x[0:3]),
                    middle=tuple(x[3:8]),
                    bottom=tuple(x[8:13]),
                ),
            )
        )
    return tuple(out)


def setup_episode():
    meta = HUContinuationState(1, 14, 15)
    world = FantasyFantasyWorld(
        meta,
        sample_fantasy_fantasy_plan(random.Random(20260901), meta),
    )
    return ContinuationAwareEpisode.build(
        world,
        three_arrangements(world.plan.packet_for(0)),
        three_arrangements(world.plan.packet_for(1)),
    )


def test_exact_targets_are_frozen_from_current_sealed_policy() -> None:
    episode = setup_episode()
    model = SparseFantasyOutcomeModel(buckets=1024, seed=71)
    values = zero_continuation_values()
    snapshot = snapshot_policy(model, episode, values)
    assert snapshot.p0_policy == (1 / 3, 1 / 3, 1 / 3)
    assert snapshot.p1_policy == (1 / 3, 1 / 3, 1 / 3)
    examples = exact_outcome_targets_for_snapshot(episode, snapshot)
    assert len(examples) == 6
    assert all(
        abs(sum(row.next_mode_distribution) - 1.0) <= 1e-12
        for row in examples
    )


def test_training_is_deterministic_and_continuation_aware() -> None:
    episode = setup_episode()
    values = zero_continuation_values()
    changed = zero_continuation_values()
    for index, state in enumerate(all_states()):
        changed[state] = ((index * 7) % 13 - 6) * 0.11

    a = SparseFantasyOutcomeModel(buckets=1024, seed=99)
    b = SparseFantasyOutcomeModel(buckets=1024, seed=99)
    report_a = train_selfplay_iteration(a, (episode,), values, epochs=2)
    report_b = train_selfplay_iteration(b, (episode,), values, epochs=2)
    assert report_a == report_b
    assert a.payload() == b.payload()
    assert report_a.examples == 6
    assert report_a.mean_immediate_huber_loss >= 0.0
    assert report_a.mean_outcome_cross_entropy >= 0.0

    # Same continuation-independent learned outcome model can be re-scored under V'.
    snapshot_changed = snapshot_policy(a, episode, changed)
    assert snapshot_changed.diagnostic.total_support_deviation_gain >= 0.0


def main() -> None:
    test_exact_targets_are_frozen_from_current_sealed_policy()
    test_training_is_deterministic_and_continuation_aware()
    print("OPENOFC_M5B_FANTASY_SELFPLAY_GATE=PASS")


if __name__ == "__main__":
    main()
