from __future__ import annotations

from hu_continuation import HUContinuationState, zero_continuation_values
from strategic_advantage_model import DeterministicReservoir
from strategic_continuation_r4_teacher import (
    add_continuation_r4_teacher,
    solve_dealer_r4_given_continuation,
)
from strategic_teacher_anchors import reachable_dealer_r4_state
from teacher_search import solve_r4_exact


def test_zero_continuation_matches_exact_current_hand_oracle() -> None:
    state = reachable_dealer_r4_state(2026082601)
    meta = HUContinuationState(button=1, p0_fantasy_cards=0, p1_fantasy_cards=0)
    values = zero_continuation_values()
    result = solve_dealer_r4_given_continuation(
        state, current_meta=meta, continuation_values=values
    )
    incoming = state.plan.incoming(4, 1)
    plain = solve_r4_exact(state.boards[1], state.boards[0], incoming)
    assert result.best_utility == float(plain.best_points)
    assert all(abs(action.continuation_utility) < 1e-12 for action in result.actions)
    assert set(result.optimal_indices)


def _find_transition_variant_state():
    for offset in range(256):
        state = reachable_dealer_r4_state(7000000 + offset * 104729)
        meta = HUContinuationState(button=0, p0_fantasy_cards=0, p1_fantasy_cards=0)
        baseline = solve_dealer_r4_given_continuation(
            state, current_meta=meta, continuation_values=zero_continuation_values()
        )
        next_states = {action.next_state for action in baseline.actions}
        if len(next_states) > 1:
            return state, meta, baseline
    raise AssertionError("deterministic search found no transition-variant dealer R4 state")


def test_supplied_continuation_can_change_exact_r4_choice() -> None:
    state, meta, baseline = _find_transition_variant_state()
    values = zero_continuation_values()
    # Hero is persistent player 0 because button=0. Pick a next state that is
    # not produced by every baseline-optimal action and reward it overwhelmingly.
    baseline_opt_states = {baseline.actions[i].next_state for i in baseline.optimal_indices}
    candidates = [
        action.next_state for action in baseline.actions
        if action.next_state not in baseline_opt_states
    ]
    if not candidates:
        # A transition-variant state may still have all variants represented in
        # an immediate-point tie. Reward the least frequent state and verify the
        # exact optimal set collapses to that transition.
        counts = {}
        for action in baseline.actions:
            counts[action.next_state] = counts.get(action.next_state, 0) + 1
        target = min(counts, key=lambda state: (counts[state], state))
    else:
        target = candidates[0]
    values[target] = 10000.0
    shifted = solve_dealer_r4_given_continuation(
        state, current_meta=meta, continuation_values=values
    )
    assert all(shifted.actions[i].next_state == target for i in shifted.optimal_indices)
    assert shifted.best_utility >= 9990.0


def test_teacher_respects_holdout_boundary() -> None:
    replay = DeterministicReservoir(capacity=1000, seed=1)
    values = zero_continuation_values()
    trained = 0
    skipped = 0
    for offset in range(20):
        state = reachable_dealer_r4_state(9000000 + offset * 104729)
        meta = HUContinuationState(button=offset % 2, p0_fantasy_cards=0, p1_fantasy_cards=0)
        result = solve_dealer_r4_given_continuation(
            state, current_meta=meta, continuation_values=values
        )
        report = add_continuation_r4_teacher(result, replay)
        trained += report["states"]
        skipped += report["skipped_holdout"]
    assert trained > 0
    assert skipped > 0
    assert replay.items
    assert all(item.source == "exact_dealer_r4_given_continuation" for item in replay.items)


def main() -> None:
    test_zero_continuation_matches_exact_current_hand_oracle()
    test_supplied_continuation_can_change_exact_r4_choice()
    test_teacher_respects_holdout_boundary()
    print(
        "OPENOFC_M4C4_CONTINUATION_R4=PASS "
        "zero_vector=PARITY point_for_fantasy=EXACT_WHEN_V_SUPPLIED holdout=DISJOINT"
    )


if __name__ == "__main__":
    main()
