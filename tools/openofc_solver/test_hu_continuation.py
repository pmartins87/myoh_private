from __future__ import annotations

from engine import Board, Card, score_heads_up
from hu_continuation import (
    AUTHORITY,
    HUContinuationState,
    STATE_COUNT,
    all_states,
    continuation_adjusted_terminal_utility,
    next_state_from_terminal_boards,
    normalize_relative_values,
    zero_continuation_values,
)


def C(text: str) -> Card:
    return Card.parse(text)


def _normal_qq_board() -> Board:
    return Board(
        top=(C("Qc"), C("Qd"), C("2s")),
        middle=(C("Kc"), C("Kd"), C("3h"), C("4s"), C("5c")),
        bottom=(C("Ac"), C("Ad"), C("6h"), C("7s"), C("8c")),
    )


def _refantasy_board() -> Board:
    return Board(
        top=(C("Jh"), C("Jd"), C("Js")),
        middle=(C("4c"), C("5d"), C("6c"), C("7d"), C("8d")),
        bottom=(C("Tc"), C("Td"), C("Th"), C("9s"), C("9d")),
    )


def test_catalog_is_exactly_50_hu_states() -> None:
    states = all_states()
    assert AUTHORITY == "EXACT_HU_CONTINUATION_STATE_TRANSITION"
    assert STATE_COUNT == 50
    assert len(states) == len(set(states)) == 50
    assert {state.button for state in states} == {0, 1}
    assert {state.p0_fantasy_cards for state in states} == {0, 14, 15, 16, 17}
    assert {state.p1_fantasy_cards for state in states} == {0, 14, 15, 16, 17}


def test_exact_dual_player_transition() -> None:
    current = HUContinuationState(button=0, p0_fantasy_cards=0, p1_fantasy_cards=16)
    nxt = next_state_from_terminal_boards(
        current,
        _normal_qq_board(),
        _refantasy_board(),
    )
    # Standard helper alternates the HU button; p0 enters F14 and p1 keeps F16.
    assert nxt == HUContinuationState(1, 14, 16)


def test_parameterized_terminal_backup_is_zero_sum() -> None:
    current = HUContinuationState(0, 0, 16)
    board0 = _normal_qq_board()
    board1 = _refantasy_board()
    values = zero_continuation_values()
    nxt = next_state_from_terminal_boards(current, board0, board1)
    values[nxt] = 2.75
    immediate = float(score_heads_up(board0, board1).points)
    u0 = continuation_adjusted_terminal_utility(
        current, board0, board1, values, update_player=0
    )
    u1 = continuation_adjusted_terminal_utility(
        current, board0, board1, values, update_player=1
    )
    assert abs(u0 - (immediate + 2.75)) < 1e-12
    assert abs(u0 + u1) < 1e-12


def test_relative_value_normalization_covers_all_states() -> None:
    states = all_states()
    raw = {state: float(i) / 10.0 for i, state in enumerate(states)}
    reference = HUContinuationState(0, 0, 0)
    anchor, normalized = normalize_relative_values(raw, reference=reference)
    assert anchor == raw[reference]
    assert normalized[reference] == 0.0
    assert len(normalized) == 50
    for state in states:
        assert abs(normalized[state] - (raw[state] - anchor)) < 1e-12


def main() -> None:
    test_catalog_is_exactly_50_hu_states()
    test_exact_dual_player_transition()
    test_parameterized_terminal_backup_is_zero_sum()
    test_relative_value_normalization_covers_all_states()
    print("OPENOFC_HU_CONTINUATION_TEST=PASS")


if __name__ == "__main__":
    main()
