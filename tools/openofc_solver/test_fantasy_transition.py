from __future__ import annotations

from engine import Board, Card, resolve_board
from fantasy_transition import (
    VARIANT_PROGRESSIVE,
    VARIANT_ULTIMATE,
    qualifies_for_refantasy,
    transition_from_board,
    transition_from_resolved,
)


def C(text: str) -> Card:
    return Card.parse(text)


def test_normal_qq_enters_14() -> None:
    board = Board(
        top=(C("Qc"), C("Qd"), C("2s")),
        middle=(C("Kc"), C("Kd"), C("3h"), C("4s"), C("5c")),
        bottom=(C("Ac"), C("Ad"), C("6h"), C("7s"), C("8c")),
    )
    resolved = resolve_board(board)
    assert resolved is not None
    assert resolved.fantasy_cards == 14
    t = transition_from_resolved(resolved, current_fantasy_cards=0)
    assert t.entered and not t.refantasy and not t.foul
    assert t.next_cards == 14


def test_ultimate_refantasy_keeps_current_count() -> None:
    board = Board(
        top=(C("Ac"), C("Ad"), C("Ah")),
        middle=(C("2c"), C("3d"), C("4h"), C("5s"), C("6c")),
        bottom=(C("7h"), C("8h"), C("9h"), C("Th"), C("Jh")),
    )
    resolved = resolve_board(board)
    assert resolved is not None
    assert qualifies_for_refantasy(resolved)
    for current in (14, 15, 16, 17):
        t = transition_from_resolved(
            resolved,
            current_fantasy_cards=current,
            variant=VARIANT_ULTIMATE,
        )
        assert t.refantasy and t.next_cards == current


def test_progressive_refantasy_returns_14() -> None:
    board = Board(
        top=(C("2c"), C("3d"), C("4s")),
        middle=(C("5c"), C("5d"), C("6h"), C("7s"), C("8c")),
        bottom=(C("9c"), C("9d"), C("9h"), C("9s"), C("Tc")),
    )
    resolved = resolve_board(board)
    assert resolved is not None
    assert qualifies_for_refantasy(resolved)
    t = transition_from_resolved(
        resolved,
        current_fantasy_cards=17,
        variant=VARIANT_PROGRESSIVE,
    )
    assert t.refantasy and t.next_cards == 14


def test_fantasy_without_qualifier_exits() -> None:
    board = Board(
        top=(C("2c"), C("3d"), C("4s")),
        middle=(C("5c"), C("5d"), C("6h"), C("7s"), C("8c")),
        bottom=(C("9c"), C("9d"), C("Th"), C("Js"), C("Qc")),
    )
    resolved = resolve_board(board)
    assert resolved is not None
    assert not qualifies_for_refantasy(resolved)
    t = transition_from_resolved(
        resolved,
        current_fantasy_cards=16,
        variant=VARIANT_ULTIMATE,
    )
    assert not t.refantasy and t.next_cards == 0


def test_foul_clears_fantasy() -> None:
    # Deliberately impossible ordering: top trips A over weak middle/bottom.
    board = Board(
        top=(C("Ac"), C("Ad"), C("Ah")),
        middle=(C("2c"), C("3d"), C("4h"), C("5s"), C("7c")),
        bottom=(C("8c"), C("9d"), C("Th"), C("Js"), C("Kc")),
    )
    assert resolve_board(board) is None
    t = transition_from_board(
        board,
        current_fantasy_cards=17,
        variant=VARIANT_ULTIMATE,
    )
    assert t.foul and t.next_cards == 0 and not t.refantasy


def main() -> None:
    test_normal_qq_enters_14()
    test_ultimate_refantasy_keeps_current_count()
    test_progressive_refantasy_returns_14()
    test_fantasy_without_qualifier_exits()
    test_foul_clears_fantasy()
    print("OPENOFC_FANTASY_TRANSITION_TEST=PASS")


if __name__ == "__main__":
    main()
