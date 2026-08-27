from __future__ import annotations

import random

from fantasy_frontier_cache import build_value_record
from fantasy_frontier_cache_onepass import build_value_record_onepass
from fantasy_response_frontier import build_fantasy_response_frontier
from fantasy_response_frontier_onepass import build_fantasy_response_frontier_onepass
from hu_continuation import HUContinuationState
from normal_fantasy_kernel import (
    NormalFantasyState,
    child_normal_state,
    legal_normal_actions,
    sample_normal_fantasy_plan,
)


def terminal_state(seed: int, fantasy_count: int = 14) -> NormalFantasyState:
    fantasy_player = seed & 1
    meta = HUContinuationState(
        button=(seed >> 1) & 1,
        p0_fantasy_cards=fantasy_count if fantasy_player == 0 else 0,
        p1_fantasy_cards=fantasy_count if fantasy_player == 1 else 0,
    )
    rng = random.Random(seed)
    action_rng = random.Random(seed ^ 0x9E3779B97F4A7C15)
    state = NormalFantasyState(
        current_meta=meta,
        plan=sample_normal_fantasy_plan(rng, fantasy_count),
    )
    while not state.terminal():
        actions = legal_normal_actions(state)
        state = child_normal_state(state, actions[action_rng.randrange(len(actions))])
    return state


def branch_signature(frontier):
    out = []
    for candidate in (frontier.no_refantasy, frontier.refantasy):
        if candidate is None:
            out.append(None)
        else:
            out.append((
                candidate.immediate_points,
                candidate.next_state,
                tuple(sorted(str(c) for row in candidate.board.rows() for c in row)),
                tuple(sorted(str(c) for c in candidate.discarded)),
            ))
    return tuple(out)


def test_onepass_matches_two_pass_exact_frontier() -> None:
    # Two deterministic physical worlds exercise both identity orientations.
    for seed in (20260826, 20260827):
        state = terminal_state(seed, 14)
        reference = build_fantasy_response_frontier(
            state.plan.fantasy_packet,
            state.normal_board,
            current_state=state.current_meta,
            hero_player=state.fantasy_player,
        )
        onepass = build_fantasy_response_frontier_onepass(
            state.plan.fantasy_packet,
            state.normal_board,
            current_state=state.current_meta,
            hero_player=state.fantasy_player,
        )
        assert branch_signature(onepass) == branch_signature(reference)


def test_value_record_matches_reference_and_key() -> None:
    for seed in (20260828, 20260829):
        state = terminal_state(seed, 14)
        reference = build_value_record(state.plan.fantasy_packet, state.normal_board)
        onepass = build_value_record_onepass(state.plan.fantasy_packet, state.normal_board)
        assert onepass.key == reference.key
        assert onepass.incoming_count == reference.incoming_count
        assert onepass.no_refantasy_points == reference.no_refantasy_points
        assert onepass.refantasy_points == reference.refantasy_points


def main() -> None:
    test_onepass_matches_two_pass_exact_frontier()
    test_value_record_matches_reference_and_key()
    print(
        "OPENOFC_M4H_ONEPASS_FRONTIER=PASS "
        "authority=EXACT parity=TWO_PASS_REFERENCE F14_worlds=4"
    )


if __name__ == "__main__":
    main()
