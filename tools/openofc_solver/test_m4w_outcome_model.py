from __future__ import annotations

import random

from engine import Board
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from fantasy_fantasy_policy_features import encode_policy_action, encode_policy_state
from hu_continuation import HUContinuationState, all_states, zero_continuation_values
from m4u_continuation_boundary import build_factorized_support_payoff
from m4v_continuation_targets import (
    build_continuation_linear_targets,
    materialize_target_values,
)
from m4w_outcome_model import (
    OUTCOME_COUNT,
    SparseFantasyOutcomeModel,
    build_outcome_examples,
    policy_api_has_hidden_opponent_argument,
    q_from_outcome,
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


def setup():
    meta = HUContinuationState(1, 14, 15)
    world = FantasyFantasyWorld(
        meta, sample_fantasy_fantasy_plan(random.Random(20260831), meta)
    )
    support0 = three_arrangements(world.plan.packet_for(0))
    support1 = three_arrangements(world.plan.packet_for(1))
    factor = build_factorized_support_payoff(world, support0, support1)
    linear = build_continuation_linear_targets(
        factor,
        p0_opponent_policy=(0.15, 0.35, 0.50),
        p1_opponent_policy=(0.55, 0.25, 0.20),
    )
    examples = build_outcome_examples(world, support0, support1, linear)
    return world, support0, support1, linear, examples


def assert_close(a, b, tol=1e-12):
    assert len(a) == len(b)
    assert all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def test_exact_outcome_labels_transport_q_across_v() -> None:
    world, support0, support1, linear, examples = setup()
    vectors = [zero_continuation_values()]
    changed = zero_continuation_values()
    for index, state in enumerate(all_states()):
        changed[state] = ((index * 11) % 23 - 11) * 0.17
    vectors.append(changed)

    for values in vectors:
        expected0, expected1 = materialize_target_values(linear, values)
        actual0 = []
        actual1 = []
        for example in examples:
            q = q_from_outcome(
                example.immediate_target,
                example.next_mode_distribution,
                current_meta=world.current_meta,
                player=example.player,
                continuation_values=values,
            )
            (actual0 if example.player == 0 else actual1).append(q)
        assert_close(actual0, expected0)
        assert_close(actual1, expected1)


def test_policy_api_is_own_information_only_and_v_aware() -> None:
    world, support0, _support1, _linear, _examples = setup()
    assert not policy_api_has_hidden_opponent_argument()
    model = SparseFantasyOutcomeModel(buckets=1024, seed=77)
    values = zero_continuation_values()
    policy = model.policy_for_private_support(
        world.plan.packet_for(0),
        support0,
        current_meta=world.current_meta,
        player=0,
        continuation_values=values,
    )
    assert_close(policy, (1 / 3, 1 / 3, 1 / 3))

    state = encode_policy_state(
        world.plan.packet_for(0), current_meta=world.current_meta, player=0
    )
    action = encode_policy_action(
        world.plan.packet_for(0),
        support0[0],
        current_meta=world.current_meta,
        player=0,
    )
    immediate, distribution = model.predict_features(state, action)
    assert immediate == 0.0
    assert len(distribution) == OUTCOME_COUNT
    assert_close(distribution, tuple(1 / OUTCOME_COUNT for _ in range(OUTCOME_COUNT)))


def test_training_is_deterministic_and_targets_remain_probabilities() -> None:
    _world, _support0, _support1, _linear, examples = setup()
    for example in examples:
        assert abs(sum(example.next_mode_distribution) - 1.0) <= 1e-12
        assert min(example.next_mode_distribution) >= 0.0

    a = SparseFantasyOutcomeModel(buckets=1024, seed=909)
    b = SparseFantasyOutcomeModel(buckets=1024, seed=909)
    ra = a.fit(examples, epochs=2)
    rb = b.fit(examples, epochs=2)
    assert ra == rb
    assert a.payload() == b.payload()
    assert ra["mean_immediate_huber_loss"] >= 0.0
    assert ra["mean_outcome_cross_entropy"] >= 0.0


def main() -> None:
    test_exact_outcome_labels_transport_q_across_v()
    test_policy_api_is_own_information_only_and_v_aware()
    test_training_is_deterministic_and_targets_remain_probabilities()
    print("OPENOFC_M4W_OUTCOME_MODEL=PASS")


if __name__ == "__main__":
    main()
