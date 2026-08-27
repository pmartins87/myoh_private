from __future__ import annotations

import random

from engine import Board, score_heads_up
from fantasy_counterfactual_frontier import build_fantasy_counterfactual_frontier
from fantasy_fantasy_kernel import FantasyFantasyWorld, sample_fantasy_fantasy_plan
from fantasy_response_frontier import evaluate_fantasy_response_frontier
from fantasy_response_frontier_onepass import build_fantasy_response_frontier_onepass
from hu_continuation import (
    HUContinuationState,
    next_state_from_terminal_boards,
    zero_continuation_values,
)
from normal_fantasy_kernel import (
    NormalFantasyState,
    child_normal_state,
    legal_normal_actions,
    sample_normal_fantasy_plan,
)


def completed_normal_board(seed: int = 20260827):
    meta = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)
    plan = sample_normal_fantasy_plan(random.Random(seed), 14)
    state = NormalFantasyState(current_meta=meta, plan=plan)
    while not state.terminal():
        state = child_normal_state(state, legal_normal_actions(state)[0])
    return meta, plan.fantasy_packet, state.normal_board


def packet_board(packet) -> Board:
    return Board(
        top=tuple(packet[0:3]),
        middle=tuple(packet[3:8]),
        bottom=tuple(packet[8:13]),
    )


def candidate_signature(candidate):
    if candidate is None:
        return None
    return (
        candidate.qualifies_refantasy,
        candidate.board,
        candidate.discarded,
        candidate.immediate_points,
        candidate.next_state,
    )


def test_asymmetric_is_exact_m4h_parity() -> None:
    meta, packet, opponent = completed_normal_board()
    direct = build_fantasy_response_frontier_onepass(
        packet, opponent, current_state=meta, hero_player=0
    )
    teacher = build_fantasy_counterfactual_frontier(
        packet, opponent, current_state=meta, hero_player=0
    )
    assert candidate_signature(teacher.no_refantasy) == candidate_signature(direct.no_refantasy)
    assert candidate_signature(teacher.refantasy) == candidate_signature(direct.refantasy)


def test_fantasy_fantasy_next_states_are_actual_meta_transitions() -> None:
    meta = HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=14)
    world = FantasyFantasyWorld(
        meta, sample_fantasy_fantasy_plan(random.Random(731), meta)
    )
    opponent_board = packet_board(world.plan.packet_for(1))
    frontier = build_fantasy_counterfactual_frontier(
        world.plan.packet_for(0),
        opponent_board,
        current_state=meta,
        hero_player=0,
    )
    for candidate in (frontier.no_refantasy, frontier.refantasy):
        if candidate is None:
            continue
        expected = next_state_from_terminal_boards(
            meta, candidate.board, opponent_board
        )
        assert candidate.next_state == expected
        assert candidate.immediate_points == score_heads_up(
            candidate.board, opponent_board
        ).points


def test_counterfactual_evaluation_uses_real_fantasy_fantasy_continuation() -> None:
    meta = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=14)
    world = FantasyFantasyWorld(
        meta, sample_fantasy_fantasy_plan(random.Random(9911), meta)
    )
    opponent_board = packet_board(world.plan.packet_for(0))
    frontier = build_fantasy_counterfactual_frontier(
        world.plan.packet_for(1),
        opponent_board,
        current_state=meta,
        hero_player=1,
    )
    values = zero_continuation_values()
    candidates = [
        c for c in (frontier.no_refantasy, frontier.refantasy) if c is not None
    ]
    assert candidates
    for index, candidate in enumerate(candidates):
        values[candidate.next_state] = 7.0 + 11.0 * index
    evaluated = evaluate_fantasy_response_frontier(frontier, values)
    expected_options = []
    for candidate in candidates:
        hero_continuation = -values[candidate.next_state]
        expected_options.append(
            (candidate.immediate_points + hero_continuation, candidate.immediate_points, candidate)
        )
    expected = max(
        expected_options,
        key=lambda row: (row[0], row[1], -int(row[2].qualifies_refantasy)),
    )
    assert evaluated.utility == float(expected[0])
    assert evaluated.candidate == expected[2]


def main() -> None:
    test_asymmetric_is_exact_m4h_parity()
    test_fantasy_fantasy_next_states_are_actual_meta_transitions()
    test_counterfactual_evaluation_uses_real_fantasy_fantasy_continuation()
    print(
        "OPENOFC_M4N_COUNTERFACTUAL_FRONTIER=PASS "
        "normal_fantasy=M4H_PARITY fantasy_fantasy=ACTUAL_META_TRANSITION "
        "sealed_policy_input=UNCHANGED"
    )


if __name__ == "__main__":
    main()
