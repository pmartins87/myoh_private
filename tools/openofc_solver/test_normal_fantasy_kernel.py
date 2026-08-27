from __future__ import annotations

import random

from engine import full_deck
from fantasy_response_frontier import evaluate_fantasy_response_frontier
from hu_continuation import HUContinuationState, zero_continuation_values
from normal_fantasy_kernel import (
    NormalFantasyDealPlan,
    NormalFantasyState,
    child_normal_state,
    exact_terminal_frontier,
    exact_terminal_utility_for_normal,
    information_state_key,
    legal_normal_actions,
    sample_normal_fantasy_plan,
)


def test_sampled_plan_and_normal_progression_are_physically_valid() -> None:
    meta = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)
    plan = sample_normal_fantasy_plan(random.Random(1), 14)
    assert len(plan.fantasy_packet) == 14
    assert len(plan.all_cards()) == 31
    assert len(set(plan.all_cards())) == 31
    state = NormalFantasyState(current_meta=meta, plan=plan)
    for round_index in range(5):
        assert state.round_index == round_index
        actions = legal_normal_actions(state)
        assert actions
        state = child_normal_state(state, actions[0])
    assert state.terminal()
    assert state.normal_board.complete()
    assert len(state.normal_discards) == 4


def test_hidden_fantasy_packet_does_not_leak_into_normal_information_key() -> None:
    meta = HUContinuationState(button=1, p0_fantasy_cards=0, p1_fantasy_cards=14)
    original = sample_normal_fantasy_plan(random.Random(2), 14)
    normal_cards = (
        original.normal_opening
        + original.normal_rounds[0]
        + original.normal_rounds[1]
        + original.normal_rounds[2]
        + original.normal_rounds[3]
    )
    remaining = tuple(sorted(set(full_deck(2)) - set(normal_cards)))
    assert len(remaining) == 37
    alternative_packet = remaining[-14:]
    assert tuple(sorted(alternative_packet)) != tuple(sorted(original.fantasy_packet))
    alternative = NormalFantasyDealPlan(
        fantasy_packet=alternative_packet,
        normal_opening=original.normal_opening,
        normal_rounds=original.normal_rounds,
    )
    a = NormalFantasyState(current_meta=meta, plan=original)
    b = NormalFantasyState(current_meta=meta, plan=alternative)
    assert information_state_key(a) == information_state_key(b)

    # After identical visible actions the keys must remain identical as well.
    for _round in range(3):
        action_a = legal_normal_actions(a)[0]
        action_b = legal_normal_actions(b)[0]
        assert action_a == action_b
        a = child_normal_state(a, action_a)
        b = child_normal_state(b, action_b)
        assert information_state_key(a) == information_state_key(b)


def test_terminal_value_is_zero_sum_negative_of_exact_fantasy_frontier() -> None:
    meta = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)
    plan = sample_normal_fantasy_plan(random.Random(9), 14)
    state = NormalFantasyState(current_meta=meta, plan=plan)
    while not state.terminal():
        state = child_normal_state(state, legal_normal_actions(state)[0])
    frontier = exact_terminal_frontier(state)
    values = zero_continuation_values()
    fantasy = evaluate_fantasy_response_frontier(frontier, values)
    normal = exact_terminal_utility_for_normal(state, values, frontier=frontier)
    assert abs(normal + fantasy.utility) < 1e-12


def main() -> None:
    test_sampled_plan_and_normal_progression_are_physically_valid()
    test_hidden_fantasy_packet_does_not_leak_into_normal_information_key()
    test_terminal_value_is_zero_sum_negative_of_exact_fantasy_frontier()
    print(
        "OPENOFC_M4E_NORMAL_FANTASY_KERNEL=PASS "
        "hidden_packet=NO_LEAK normal_rounds=EXACT terminal=EXACT_FRONTIER_GIVEN_V"
    )


if __name__ == "__main__":
    main()
