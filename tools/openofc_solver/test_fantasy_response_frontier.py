from __future__ import annotations

from engine import Board, Card
from fantasy_delayed_response import solve_delayed_fantasy_best_response
from fantasy_response_frontier import (
    FORCE_MARGIN,
    MAX_IMMEDIATE_SPAN,
    build_fantasy_response_frontier,
    evaluate_fantasy_response_frontier,
    mask_pair_count,
)
from hu_continuation import HUContinuationState, zero_continuation_values


def C(text: str) -> Card:
    return Card.parse(text)


def packet14() -> tuple[Card, ...]:
    return tuple(map(C, (
        "Ac", "Ad", "Ah",
        "2c", "3d", "4h", "5s", "6c",
        "7h", "8h", "9h", "Th", "Kh", "Qd",
    )))


def normal_board() -> Board:
    return Board(
        top=(C("2d"), C("7c"), C("9s")),
        middle=(C("Jc"), C("Jh"), C("3c"), C("4d"), C("8s")),
        bottom=(C("Qc"), C("Qs"), C("5d"), C("6d"), C("Td")),
    )


def test_mask_pair_growth_is_explicit() -> None:
    assert mask_pair_count(14) == 252252
    assert mask_pair_count(15) == 756756
    assert mask_pair_count(16) == 2018016
    assert mask_pair_count(17) == 4900896
    assert FORCE_MARGIN > MAX_IMMEDIATE_SPAN


def test_frontier_matches_fresh_exact_solve_for_arbitrary_continuation() -> None:
    current = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)
    frontier = build_fantasy_response_frontier(
        packet14(), normal_board(), current_state=current, hero_player=0
    )
    assert frontier.candidate_count >= 1

    values = zero_continuation_values()
    # Use deliberately asymmetric values for the two possible Hero qualifier
    # branches. The opponent's next mode is fixed by the completed normal board.
    if frontier.no_refantasy is not None:
        values[frontier.no_refantasy.next_state] = -17.25
    if frontier.refantasy is not None:
        values[frontier.refantasy.next_state] = 43.75

    factored = evaluate_fantasy_response_frontier(frontier, values)
    direct = solve_delayed_fantasy_best_response(
        packet14(),
        normal_board(),
        current_state=current,
        hero_player=0,
        continuation_values=values,
    )
    assert abs(factored.utility - direct.utility) < 1e-9
    assert factored.candidate.immediate_points == direct.immediate_points
    assert factored.candidate.next_state == direct.next_state
    assert abs(factored.continuation_utility - direct.continuation_utility) < 1e-9


def test_same_frontier_revalues_without_new_combinatorial_search() -> None:
    current = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)
    frontier = build_fantasy_response_frontier(
        packet14(), normal_board(), current_state=current, hero_player=0
    )
    zero = zero_continuation_values()
    first = evaluate_fantasy_response_frontier(frontier, zero)
    shifted = zero_continuation_values()
    if frontier.refantasy is not None:
        shifted[frontier.refantasy.next_state] = 1000.0
    second = evaluate_fantasy_response_frontier(frontier, shifted)
    if frontier.refantasy is not None:
        assert second.candidate.qualifies_refantasy
        assert second.utility >= 1000.0 - 103.0
    assert first.candidate in (frontier.no_refantasy, frontier.refantasy)


def main() -> None:
    test_mask_pair_growth_is_explicit()
    test_frontier_matches_fresh_exact_solve_for_arbitrary_continuation()
    test_same_frontier_revalues_without_new_combinatorial_search()
    print(
        "OPENOFC_M4D_FANTASY_FRONTIER=PASS "
        "factorization=EXACT branches=REFANTASY_BOOLEAN V_REEVALUATION=O1_SEARCH_FREE"
    )


if __name__ == "__main__":
    main()
