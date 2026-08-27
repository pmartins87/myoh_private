from __future__ import annotations

from engine import Board, Card, resolve_board, score_heads_up
from fantasy_delayed_response import (
    AUTHORITY,
    solve_delayed_fantasy_best_response,
)
from hu_continuation import HUContinuationState, zero_continuation_values


def C(text: str) -> Card:
    return Card.parse(text)


def _fantasy14_packet() -> tuple[Card, ...]:
    # Contains an explicit legal re-Fantasy construction:
    # AAA top / 2-6 straight middle / heart flush bottom, plus one discard.
    return tuple(map(C, (
        "Ac", "Ad", "Ah",
        "2c", "3d", "4h", "5s", "6c",
        "7h", "8h", "9h", "Th", "Kh",
        "Qd",
    )))


def _normal_opponent_board() -> Board:
    board = Board(
        top=(C("2d"), C("7c"), C("9s")),
        middle=(C("Jc"), C("Jh"), C("3c"), C("4d"), C("8s")),
        bottom=(C("Qc"), C("Qs"), C("5d"), C("6d"), C("Td")),
    )
    assert resolve_board(board) is not None
    return board


def test_exact_delayed_response_uses_continuation_without_guessing_bonus() -> None:
    current = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)
    values = zero_continuation_values()
    # Standard next button is player 1. Reward actual F14 persistence heavily in
    # this artificial continuation vector so the test exercises the continuation
    # seam rather than relying on an immediate-score coincidence.
    qualified_next = HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=0)
    values[qualified_next] = 1000.0

    result = solve_delayed_fantasy_best_response(
        _fantasy14_packet(),
        _normal_opponent_board(),
        current_state=current,
        hero_player=0,
        continuation_values=values,
    )
    assert result.authority == AUTHORITY
    assert result.incoming_count == 14
    assert result.board.complete()
    assert resolve_board(result.board) is not None
    assert len(result.discarded) == 1
    assert result.next_state == qualified_next
    assert result.continuation_utility == 1000.0
    assert result.immediate_points == score_heads_up(
        result.board, _normal_opponent_board()
    ).points
    assert abs(result.utility - (result.immediate_points + 1000.0)) < 1e-12
    assert result.mask_pairs == 252252  # C(14,5) * C(9,5), no sampling.
    assert 0 < result.legal_pairs <= result.mask_pairs
    assert result.row5_cache_entries > 0
    assert result.row3_cache_entries > 0
    assert result.top_frontiers > 0
    assert result.top_envelopes > 0


def test_delayed_response_rejects_wrong_meta_state() -> None:
    values = zero_continuation_values()
    try:
        solve_delayed_fantasy_best_response(
            _fantasy14_packet(),
            _normal_opponent_board(),
            current_state=HUContinuationState(0, 14, 14),
            hero_player=0,
            continuation_values=values,
        )
    except ValueError as exc:
        assert "exactly one HU Fantasy player" in str(exc)
    else:
        raise AssertionError("both-Fantasy state must not use delayed normal-vs-Fantasy kernel")


def main() -> None:
    test_exact_delayed_response_uses_continuation_without_guessing_bonus()
    test_delayed_response_rejects_wrong_meta_state()
    print("OPENOFC_FANTASY_DELAYED_RESPONSE_TEST=PASS")


if __name__ == "__main__":
    main()
