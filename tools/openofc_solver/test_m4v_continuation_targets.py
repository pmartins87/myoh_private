from __future__ import annotations

import random

from engine import Board
from fantasy_fantasy_bootstrap import build_bootstrap_targets
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from hu_continuation import HUContinuationState, all_states, zero_continuation_values
from m4u_continuation_boundary import (
    build_factorized_support_payoff,
    materialize_factorized_payoff,
)
from m4v_continuation_targets import (
    build_continuation_linear_targets,
    materialize_target_values,
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


def assert_close(a, b):
    assert len(a) == len(b)
    assert all(abs(float(x) - float(y)) <= 1e-12 for x, y in zip(a, b))


def test_linear_targets_match_existing_bootstrap_for_multiple_v() -> None:
    meta = HUContinuationState(1, 14, 15)
    world = FantasyFantasyWorld(
        meta, sample_fantasy_fantasy_plan(random.Random(20260830), meta)
    )
    support0 = three_arrangements(world.plan.packet_for(0))
    support1 = three_arrangements(world.plan.packet_for(1))
    factor = build_factorized_support_payoff(world, support0, support1)

    p0_opp = (0.15, 0.35, 0.50)
    p1_opp = (0.55, 0.25, 0.20)
    linear = build_continuation_linear_targets(
        factor,
        p0_opponent_policy=p0_opp,
        p1_opponent_policy=p1_opp,
    )

    vectors = [zero_continuation_values()]
    changed = zero_continuation_values()
    for index, state in enumerate(all_states()):
        changed[state] = ((index * 7) % 19 - 9) * 0.2
    vectors.append(changed)

    for values in vectors:
        matrix = materialize_factorized_payoff(factor, values)
        bootstrap = build_bootstrap_targets(
            world,
            support0,
            support1,
            matrix,
            p0_opponent_policy=p0_opp,
            p1_opponent_policy=p1_opp,
            source="m4v-regression",
        )
        q0, q1 = materialize_target_values(linear, values)
        assert_close(q0, tuple(x.target for x in bootstrap.p0_examples))
        assert_close(q1, tuple(x.target for x in bootstrap.p1_examples))


def test_coefficients_keep_zero_sum_perspective() -> None:
    meta = HUContinuationState(0, 14, 14)
    world = FantasyFantasyWorld(
        meta, sample_fantasy_fantasy_plan(random.Random(404), meta)
    )
    support0 = three_arrangements(world.plan.packet_for(0))
    support1 = three_arrangements(world.plan.packet_for(1))
    factor = build_factorized_support_payoff(world, support0, support1)
    batch = build_continuation_linear_targets(
        factor,
        p0_opponent_policy=(1, 1, 1),
        p1_opponent_policy=(1, 1, 1),
    )
    for target in batch.p0_targets:
        assert abs(sum(value for _state, value in target.coefficients) - 1.0) <= 1e-12
    for target in batch.p1_targets:
        assert abs(sum(value for _state, value in target.coefficients) + 1.0) <= 1e-12


def main() -> None:
    test_linear_targets_match_existing_bootstrap_for_multiple_v()
    test_coefficients_keep_zero_sum_perspective()
    print("OPENOFC_M4V_CONTINUATION_TARGETS=PASS")


if __name__ == "__main__":
    main()
