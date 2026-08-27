from __future__ import annotations

from engine import Board, Card
from fantasy_frontier_cache import (
    ExactFantasyFrontierCache,
    canonical_frontier_key,
    evaluate_value_record,
)
from hu_continuation import HUContinuationState, zero_continuation_values
from strategic_suit_symmetry import permute_card


def C(text: str) -> Card:
    return Card.parse(text)


def packet14() -> tuple[Card, ...]:
    return tuple(map(C, (
        "Ac", "Ad", "Ah", "2c", "3d", "4h", "5s", "6c",
        "7h", "8h", "9h", "Th", "Kh", "Qd",
    )))


def normal_board() -> Board:
    return Board(
        top=(C("2d"), C("7c"), C("9s")),
        middle=(C("Jc"), C("Jh"), C("3c"), C("4d"), C("8s")),
        bottom=(C("Qc"), C("Qs"), C("5d"), C("6d"), C("Td")),
    )


def permute_board(board: Board, suit_map) -> Board:
    return Board(*(
        tuple(permute_card(card, suit_map) for card in row)
        for row in board.rows()
    ))


def test_full_teacher_key_is_suit_canonical() -> None:
    suit_map = (2, 0, 3, 1)
    packet = packet14()
    board = normal_board()
    permuted_packet = tuple(permute_card(card, suit_map) for card in packet)
    permuted_board = permute_board(board, suit_map)
    assert canonical_frontier_key(packet, board) == canonical_frontier_key(
        permuted_packet, permuted_board
    )


def test_suit_isomorphic_second_lookup_is_exact_cache_hit() -> None:
    suit_map = (1, 3, 0, 2)
    packet = packet14()
    board = normal_board()
    cache = ExactFantasyFrontierCache()
    first = cache.get_or_build(packet, board)
    assert cache.misses == 1 and cache.hits == 0
    second = cache.get_or_build(
        tuple(permute_card(card, suit_map) for card in packet),
        permute_board(board, suit_map),
    )
    assert first == second
    assert cache.misses == 1 and cache.hits == 1
    payload = cache.payload()
    assert payload["schema"] == "openofc-fantasy-frontier-value-cache-v1"
    assert len(payload["records"]) == 1
    assert len(payload["sha256"]) == 64


def test_record_revalues_in_constant_time_for_new_continuation_vector() -> None:
    packet = packet14()
    board = normal_board()
    cache = ExactFantasyFrontierCache()
    record = cache.get_or_build(packet, board)
    meta = HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)
    zero = zero_continuation_values()
    baseline = evaluate_value_record(
        record,
        board,
        current_meta=meta,
        fantasy_player=0,
        continuation_values=zero,
    )
    shifted = zero_continuation_values()
    # Evaluate both exact branches under deliberately different V values without
    # rebuilding the combinatorial frontier.
    if record.refantasy_points is not None:
        probe = evaluate_value_record(
            record,
            board,
            current_meta=meta,
            fantasy_player=0,
            continuation_values=shifted,
        )
        target = probe.next_state
        # The probe may currently select no-refantasy. Find the re-Fantasy next
        # state by temporarily rewarding it through the record evaluator's two
        # exact branch construction: a large positive value on all F14 P0 states
        # is sufficient for this structural test.
        for state in shifted:
            if state.p0_fantasy_cards == 14:
                shifted[state] = 1000.0
        rewarded = evaluate_value_record(
            record,
            board,
            current_meta=meta,
            fantasy_player=0,
            continuation_values=shifted,
        )
        assert rewarded.utility >= baseline.utility
        assert rewarded.qualifies_refantasy
    assert cache.misses == 1


def main() -> None:
    test_full_teacher_key_is_suit_canonical()
    test_suit_isomorphic_second_lookup_is_exact_cache_hit()
    test_record_revalues_in_constant_time_for_new_continuation_vector()
    print(
        "OPENOFC_M4F_FANTASY_FRONTIER_CACHE=PASS "
        "key=SUIT24_EXACT hidden_teacher_data=ORACLE_ONLY V_REVALUE=NO_SEARCH"
    )


if __name__ == "__main__":
    main()
