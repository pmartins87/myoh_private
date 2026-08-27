from __future__ import annotations

"""Exact HU game boundary for hands where both players are in Fantasy.

KKPoker's published OFC rule states that a Fantasy player's cards are not
exposed until the other players have completed their hands.  For the two-player
both-Fantasy state this module therefore models placement as a sealed,
simultaneous private decision: each player knows only their own Fantasy packet
and the public meta-state before both completed boards are revealed.

This module is exact plumbing, not a solved Fantasy-vs-Fantasy policy.
"""

from dataclasses import dataclass
import json
import random
from typing import Iterable, Mapping, Sequence

from engine import Board, Card, full_deck
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    continuation_adjusted_terminal_utility,
    hand_kernel_kind,
)
from strategic_suit_symmetry import SUIT_PERMUTATIONS, permute_card

AUTHORITY = "EXACT_FANTASY_FANTASY_SEALED_GAME_BOUNDARY_GIVEN_KKPOKER_TIMING"
TIMING_CONTRACT = "SEALED_SIMULTANEOUS_HIDDEN_UNTIL_BOTH_COMPLETE"
SOLVER_KIND = "fantasy-fantasy-sealed-suit24"


def _sorted(cards: Iterable[Card]) -> tuple[Card, ...]:
    return tuple(sorted(cards))


@dataclass(frozen=True)
class FantasyFantasyDealPlan:
    packets: tuple[tuple[Card, ...], tuple[Card, ...]]

    def packet_for(self, player: int) -> tuple[Card, ...]:
        if player not in (0, 1):
            raise ValueError("HU player must be 0 or 1")
        return self.packets[player]

    def all_cards(self) -> tuple[Card, ...]:
        return self.packets[0] + self.packets[1]


def sample_fantasy_fantasy_plan(
    rng: random.Random,
    current_meta: HUContinuationState,
) -> FantasyFantasyDealPlan:
    if hand_kernel_kind(current_meta) != KERNEL_FANTASY_FANTASY:
        raise ValueError("Fantasy/Fantasy plan requires both players in Fantasy")
    counts = (
        current_meta.p0_fantasy_cards,
        current_meta.p1_fantasy_cards,
    )
    deck = list(full_deck(2))
    rng.shuffle(deck)
    cursor = 0

    def draw(count: int) -> tuple[Card, ...]:
        nonlocal cursor
        cards = _sorted(deck[cursor:cursor + count])
        cursor += count
        return cards

    plan = FantasyFantasyDealPlan((draw(counts[0]), draw(counts[1])))
    cards = plan.all_cards()
    if len(cards) != sum(counts) or len(set(cards)) != len(cards):
        raise AssertionError("Fantasy/Fantasy deal must contain unique physical cards")
    return plan


@dataclass(frozen=True)
class FantasyFantasyWorld:
    current_meta: HUContinuationState
    plan: FantasyFantasyDealPlan

    def __post_init__(self) -> None:
        if hand_kernel_kind(self.current_meta) != KERNEL_FANTASY_FANTASY:
            raise ValueError("Fantasy/Fantasy world requires both players in Fantasy")
        for player in (0, 1):
            expected = self.current_meta.mode_for(player)
            packet = self.plan.packet_for(player)
            if len(packet) != expected:
                raise ValueError("Fantasy packet count does not match meta-state")
        cards = self.plan.all_cards()
        if len(set(cards)) != len(cards):
            raise ValueError("Fantasy/Fantasy world contains duplicate physical cards")


@dataclass(frozen=True)
class FantasyArrangement:
    board: Board
    discarded: tuple[Card, ...]


def validate_arrangement(
    packet: Sequence[Card],
    arrangement: FantasyArrangement,
) -> None:
    cards = tuple(packet)
    if len(cards) not in (14, 15, 16, 17):
        raise ValueError("Fantasy arrangement requires a 14..17-card packet")
    if not arrangement.board.complete():
        raise ValueError("Fantasy arrangement board must contain 3/5/5 cards")
    placed = tuple(card for row in arrangement.board.rows() for card in row)
    discarded = tuple(arrangement.discarded)
    if len(placed) != 13 or len(discarded) != len(cards) - 13:
        raise ValueError("Fantasy arrangement has wrong placed/discard cardinality")
    if len(set(placed + discarded)) != len(cards):
        raise ValueError("Fantasy arrangement duplicates a physical card")
    if set(placed) | set(discarded) != set(cards):
        raise ValueError("Fantasy arrangement does not partition its private packet")


def arrangement_from_board(
    packet: Sequence[Card],
    board: Board,
) -> FantasyArrangement:
    if not board.complete():
        raise ValueError("Fantasy board must be complete")
    placed = {card for row in board.rows() for card in row}
    discarded = tuple(card for card in packet if card not in placed)
    arrangement = FantasyArrangement(board=board, discarded=discarded)
    validate_arrangement(packet, arrangement)
    return arrangement


def terminal_utility(
    world: FantasyFantasyWorld,
    arrangement0: FantasyArrangement,
    arrangement1: FantasyArrangement,
    continuation_values: Mapping[HUContinuationState, float],
    *,
    update_player: int,
) -> float:
    if update_player not in (0, 1):
        raise ValueError("HU player must be 0 or 1")
    validate_arrangement(world.plan.packet_for(0), arrangement0)
    validate_arrangement(world.plan.packet_for(1), arrangement1)
    return continuation_adjusted_terminal_utility(
        world.current_meta,
        arrangement0.board,
        arrangement1.board,
        continuation_values,
        update_player=update_player,
    )


def _token(card: Card, suit_map: Sequence[int]) -> str:
    return str(permute_card(card, suit_map))


def information_key_under_suit_map(
    world: FantasyFantasyWorld,
    player: int,
    suit_map: Sequence[int],
) -> str:
    if player not in (0, 1):
        raise ValueError("HU player must be 0 or 1")
    payload = {
        "v": 1,
        "kernel": SOLVER_KIND,
        "timing": TIMING_CONTRACT,
        "player": player,
        "button": world.current_meta.button,
        "p0_fantasy_count": world.current_meta.p0_fantasy_cards,
        "p1_fantasy_count": world.current_meta.p1_fantasy_cards,
        "own_packet": tuple(
            sorted(_token(card, suit_map) for card in world.plan.packet_for(player))
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def canonical_information_key(
    world: FantasyFantasyWorld,
    player: int,
) -> tuple[str, tuple[int, int, int, int]]:
    return min(
        (
            information_key_under_suit_map(world, player, suit_map),
            suit_map,
        )
        for suit_map in SUIT_PERMUTATIONS
    )


def arrangement_key_under_suit_map(
    arrangement: FantasyArrangement,
    suit_map: Sequence[int],
) -> str:
    payload = {
        "top": tuple(sorted(_token(card, suit_map) for card in arrangement.board.top)),
        "middle": tuple(sorted(_token(card, suit_map) for card in arrangement.board.middle)),
        "bottom": tuple(sorted(_token(card, suit_map) for card in arrangement.board.bottom)),
        "discarded": tuple(sorted(_token(card, suit_map) for card in arrangement.discarded)),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def canonical_action_key(
    world: FantasyFantasyWorld,
    player: int,
    arrangement: FantasyArrangement,
) -> str:
    validate_arrangement(world.plan.packet_for(player), arrangement)
    _key, suit_map = canonical_information_key(world, player)
    return arrangement_key_under_suit_map(arrangement, suit_map)
