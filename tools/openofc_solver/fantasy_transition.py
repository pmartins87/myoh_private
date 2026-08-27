from __future__ import annotations

"""Exact KKPoker Fantasy / re-Fantasy state transitions.

This module contains *rule semantics only*.  It deliberately does not attach an
arbitrary point bonus to Fantasy.  The strategic solver can therefore carry the
next-hand state as a real continuation state instead of distorting current-hand
points with a hand-written heuristic.

Rule surface captured from KKPoker OFC Joker Ultimate:
- a normal valid hand enters Fantasy with QQ/KK/AA on top for 14/15/16 cards;
- top trips enters 17-card Fantasy in Ultimate + Jokers;
- while already in Fantasy, re-Fantasy requires top trips OR bottom quads or
  better;
- in Ultimate, a successful re-Fantasy keeps the same Fantasy card count;
- in Progressive, re-Fantasy receives 14 cards.
"""

from dataclasses import dataclass

from engine import (
    Board,
    CAT_QUADS,
    CAT_TRIPS,
    ResolvedBoard,
    resolve_board,
)

VARIANT_ULTIMATE = "ultimate"
VARIANT_PROGRESSIVE = "progressive"
VALID_FANTASY_COUNTS = (14, 15, 16, 17)


@dataclass(frozen=True)
class FantasyTransition:
    current_cards: int
    next_cards: int
    entered: bool
    refantasy: bool
    qualified: bool
    foul: bool
    variant: str


def _validate_variant(variant: str) -> str:
    value = str(variant).strip().lower()
    if value not in (VARIANT_ULTIMATE, VARIANT_PROGRESSIVE):
        raise ValueError(f"unsupported OFC Fantasy variant: {variant!r}")
    return value


def qualifies_for_refantasy(resolved: ResolvedBoard | None) -> bool:
    """Return the exact visible hand-condition for remaining in Fantasy."""
    if resolved is None:
        return False
    top, _middle, bottom = resolved.ranks
    return top.category == CAT_TRIPS or bottom.category >= CAT_QUADS


def transition_from_resolved(
    resolved: ResolvedBoard | None,
    *,
    current_fantasy_cards: int = 0,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyTransition:
    """Compute the next-hand Fantasy state without inventing continuation EV.

    ``current_fantasy_cards == 0`` means the player is in a normal hand.  A
    positive value means the player is currently setting that many Fantasy
    cards.  The function returns only the next state; its value in points must
    be learned/solved by the long-horizon game solver.
    """
    variant = _validate_variant(variant)
    current = int(current_fantasy_cards)
    if current not in (0, *VALID_FANTASY_COUNTS):
        raise ValueError(
            "current_fantasy_cards must be 0, 14, 15, 16, or 17"
        )

    if resolved is None:
        return FantasyTransition(
            current_cards=current,
            next_cards=0,
            entered=False,
            refantasy=False,
            qualified=False,
            foul=True,
            variant=variant,
        )

    if current == 0:
        next_cards = int(resolved.fantasy_cards)
        if next_cards not in (0, *VALID_FANTASY_COUNTS):
            raise AssertionError(
                f"engine returned invalid Fantasy award: {next_cards}"
            )
        return FantasyTransition(
            current_cards=0,
            next_cards=next_cards,
            entered=next_cards > 0,
            refantasy=False,
            qualified=next_cards > 0,
            foul=False,
            variant=variant,
        )

    qualified = qualifies_for_refantasy(resolved)
    if not qualified:
        next_cards = 0
    elif variant == VARIANT_ULTIMATE:
        next_cards = current
    else:
        next_cards = 14

    return FantasyTransition(
        current_cards=current,
        next_cards=next_cards,
        entered=False,
        refantasy=qualified,
        qualified=qualified,
        foul=False,
        variant=variant,
    )


def transition_from_board(
    board: Board,
    *,
    current_fantasy_cards: int = 0,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyTransition:
    """Resolve a complete 3/5/5 board and compute its Fantasy transition."""
    return transition_from_resolved(
        resolve_board(board),
        current_fantasy_cards=current_fantasy_cards,
        variant=variant,
    )
