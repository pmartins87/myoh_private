from __future__ import annotations

import inspect
import random

from engine import Board
from fantasy_fantasy_kernel import (
    FantasyArrangement,
    FantasyFantasyDealPlan,
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
    terminal_utility,
)
from fantasy_fantasy_payoff import (
    build_exact_support_payoff_matrix,
    expected_p0_value,
    support_deviation_diagnostic,
    uniform_policy,
)
from fantasy_fantasy_policy_features import (
    STATE_FEATURE_LIMIT,
    encode_policy_action,
    encode_policy_state,
    encode_policy_state_action,
)
from fantasy_fantasy_proposals import canonical_visible_packet
from hu_continuation import HUContinuationState, zero_continuation_values
from strategic_suit_symmetry import permute_card


def meta() -> HUContinuationState:
    return HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=14)


def two_arrangements(packet):
    cards = list(packet)
    board_a = Board(
        top=tuple(cards[0:3]),
        middle=tuple(cards[3:8]),
        bottom=tuple(cards[8:13]),
    )
    cards[2], cards[3] = cards[3], cards[2]
    board_b = Board(
        top=tuple(cards[0:3]),
        middle=tuple(cards[3:8]),
        bottom=tuple(cards[8:13]),
    )
    return (
        arrangement_from_board(packet, board_a),
        arrangement_from_board(packet, board_b),
    )


def permute_arrangement(arrangement: FantasyArrangement, suit_map):
    def row(cards):
        return tuple(sorted(permute_card(card, suit_map) for card in cards))
    return FantasyArrangement(
        Board(
            top=row(arrangement.board.top),
            middle=row(arrangement.board.middle),
            bottom=row(arrangement.board.bottom),
        ),
        row(arrangement.discarded),
    )


def test_policy_feature_api_has_no_opponent_input() -> None:
    names = set(inspect.signature(encode_policy_state_action).parameters)
    assert all("opponent" not in name for name in names)


def test_policy_features_are_suit_equivariant_and_partitioned() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(20260828), current)
    )
    own = world.plan.packet_for(0)
    arrangement = two_arrangements(own)[0]
    state = encode_policy_state(own, current_meta=current, player=0)
    action = encode_policy_action(
        own, arrangement, current_meta=current, player=0
    )
    combined = encode_policy_state_action(
        own, arrangement, current_meta=current, player=0
    )
    assert state + action == combined
    assert max(state) < STATE_FEATURE_LIMIT <= min(action)

    suit_map = (2, 0, 3, 1)
    permuted_packet = tuple(sorted(permute_card(card, suit_map) for card in own))
    permuted_arrangement = permute_arrangement(arrangement, suit_map)
    assert encode_policy_state_action(
        permuted_packet,
        permuted_arrangement,
        current_meta=current,
        player=0,
    ) == combined
    assert canonical_visible_packet(own, current, 0)[0] == canonical_visible_packet(
        permuted_packet, current, 0
    )[0]


def test_distinct_arrangements_have_distinct_action_features() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(9001), current)
    )
    own = world.plan.packet_for(1)
    a, b = two_arrangements(own)
    assert encode_policy_action(
        own, a, current_meta=current, player=1
    ) != encode_policy_action(
        own, b, current_meta=current, player=1
    )


def test_exact_support_matrix_and_zero_sum_parity() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(7319), current)
    )
    support0 = two_arrangements(world.plan.packet_for(0))
    support1 = two_arrangements(world.plan.packet_for(1))
    values = zero_continuation_values()
    matrix = build_exact_support_payoff_matrix(world, support0, support1, values)
    assert matrix.shape == (2, 2)
    for i, arrangement0 in enumerate(support0):
        for j, arrangement1 in enumerate(support1):
            p0 = terminal_utility(
                world, arrangement0, arrangement1, values, update_player=0
            )
            p1 = terminal_utility(
                world, arrangement0, arrangement1, values, update_player=1
            )
            assert matrix.p0_values[i][j] == p0
            assert abs(p0 + p1) <= 1e-9

    sigma0 = uniform_policy(2)
    sigma1 = uniform_policy(2)
    expected = sum(sum(row) for row in matrix.p0_values) / 4.0
    assert abs(expected_p0_value(matrix, sigma0, sigma1) - expected) <= 1e-9
    diagnostic = support_deviation_diagnostic(matrix, sigma0, sigma1)
    assert diagnostic.p0_deviation_gain >= 0.0
    assert diagnostic.p1_deviation_gain >= 0.0
    assert abs(
        diagnostic.total_support_deviation_gain
        - diagnostic.p0_deviation_gain
        - diagnostic.p1_deviation_gain
    ) <= 1e-9


def test_exact_support_matrix_is_global_suit_invariant() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(182), current)
    )
    support0 = two_arrangements(world.plan.packet_for(0))
    support1 = two_arrangements(world.plan.packet_for(1))
    values = zero_continuation_values()
    original = build_exact_support_payoff_matrix(world, support0, support1, values)

    suit_map = (1, 3, 0, 2)
    plan = FantasyFantasyDealPlan(
        (
            tuple(sorted(permute_card(card, suit_map) for card in world.plan.packet_for(0))),
            tuple(sorted(permute_card(card, suit_map) for card in world.plan.packet_for(1))),
        )
    )
    transformed_world = FantasyFantasyWorld(current, plan)
    transformed = build_exact_support_payoff_matrix(
        transformed_world,
        tuple(permute_arrangement(x, suit_map) for x in support0),
        tuple(permute_arrangement(x, suit_map) for x in support1),
        values,
    )
    assert transformed.p0_values == original.p0_values
    assert transformed.p0_action_keys == original.p0_action_keys
    assert transformed.p1_action_keys == original.p1_action_keys


def main() -> None:
    test_policy_feature_api_has_no_opponent_input()
    test_policy_features_are_suit_equivariant_and_partitioned()
    test_distinct_arrangements_have_distinct_action_features()
    test_exact_support_matrix_and_zero_sum_parity()
    test_exact_support_matrix_is_global_suit_invariant()
    print(
        "OPENOFC_M4P_SEALED_SUPPORT_MATRIX=PASS "
        "policy_features=OWN_INFO_ONLY suit24=INVARIANT payoff=EXACT_ZERO_SUM "
        "diagnostic=SUPPORT_RESTRICTED_DEVIATION"
    )


if __name__ == "__main__":
    main()
