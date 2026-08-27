from __future__ import annotations

"""Exact value-only cache for delayed Fantasy terminal frontiers.

This cache is an oracle/training component, not a policy input. It is therefore
allowed to key on the hidden Fantasy packet. The key is canonicalized over all
24 global suit permutations, allowing exact reuse across suit-isomorphic
terminal worlds. Stored records contain only the best immediate score for each
reachable re-Fantasy branch; changing the outer continuation vector requires no
new combinatorial arrangement search.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Sequence

from engine import Board, Card
from fantasy_response_frontier import build_fantasy_response_frontier
from fantasy_transition import VARIANT_ULTIMATE, transition_from_board
from hu_continuation import HUContinuationState, default_next_button
from strategic_suit_symmetry import SUIT_PERMUTATIONS, permute_card

SCHEMA = "openofc-fantasy-frontier-value-cache-v1"
RECORD_AUTHORITY = "EXACT_DELAYED_FANTASY_IMMEDIATE_FRONTIER"


def _token(card: Card, suit_map: Sequence[int]) -> str:
    return str(permute_card(card, suit_map))


def canonical_frontier_key(
    incoming: Sequence[Card],
    normal_board: Board,
    *,
    variant: str = VARIANT_ULTIMATE,
) -> str:
    cards = tuple(incoming)
    if len(cards) not in (14, 15, 16, 17):
        raise ValueError("frontier cache requires 14..17 Fantasy cards")
    if not normal_board.complete():
        raise ValueError("frontier cache requires completed normal board")
    if set(cards) & {card for row in normal_board.rows() for card in row}:
        raise ValueError("Fantasy packet overlaps normal board")

    def payload(suit_map):
        return {
            "v": 1,
            "variant": variant,
            "fantasy_count": len(cards),
            "packet": tuple(sorted(_token(card, suit_map) for card in cards)),
            "normal_board": tuple(
                tuple(sorted(_token(card, suit_map) for card in row))
                for row in normal_board.rows()
            ),
        }

    return min(
        json.dumps(payload(suit_map), sort_keys=True, separators=(",", ":"))
        for suit_map in SUIT_PERMUTATIONS
    )


@dataclass(frozen=True)
class FantasyFrontierValueRecord:
    key: str
    incoming_count: int
    no_refantasy_points: int | None
    refantasy_points: int | None
    authority: str = RECORD_AUTHORITY

    def __post_init__(self) -> None:
        if self.incoming_count not in (14, 15, 16, 17):
            raise ValueError("invalid Fantasy frontier record count")
        if self.no_refantasy_points is None and self.refantasy_points is None:
            raise ValueError("frontier record requires at least one reachable branch")

    def payload(self) -> dict:
        return {
            "key": self.key,
            "incoming_count": self.incoming_count,
            "no_refantasy_points": self.no_refantasy_points,
            "refantasy_points": self.refantasy_points,
            "authority": self.authority,
        }


def build_value_record(
    incoming: Sequence[Card],
    normal_board: Board,
    *,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyFrontierValueRecord:
    cards = tuple(incoming)
    # Normalize identity/button only for generating the immediate frontier. The
    # immediate Hero score and branch reachability are independent of persistent
    # identity. Actual next-state values are added later with the real meta-state.
    normalized = HUContinuationState(
        button=0,
        p0_fantasy_cards=len(cards),
        p1_fantasy_cards=0,
    )
    frontier = build_fantasy_response_frontier(
        cards,
        normal_board,
        current_state=normalized,
        hero_player=0,
        variant=variant,
    )
    return FantasyFrontierValueRecord(
        key=canonical_frontier_key(cards, normal_board, variant=variant),
        incoming_count=len(cards),
        no_refantasy_points=(
            None if frontier.no_refantasy is None
            else int(frontier.no_refantasy.immediate_points)
        ),
        refantasy_points=(
            None if frontier.refantasy is None
            else int(frontier.refantasy.immediate_points)
        ),
    )


def _next_state(
    current_meta: HUContinuationState,
    normal_board: Board,
    *,
    fantasy_player: int,
    qualifies: bool,
    variant: str,
) -> HUContinuationState:
    normal_player = 1 - fantasy_player
    hero_mode = current_meta.mode_for(fantasy_player)
    if hero_mode not in (14, 15, 16, 17) or current_meta.mode_for(normal_player) != 0:
        raise ValueError("record evaluation requires exactly one Fantasy player")
    normal_transition = transition_from_board(
        normal_board,
        current_fantasy_cards=0,
        variant=variant,
    )
    modes = [0, 0]
    modes[normal_player] = normal_transition.next_cards
    modes[fantasy_player] = (
        hero_mode if qualifies and variant == VARIANT_ULTIMATE
        else 14 if qualifies
        else 0
    )
    return HUContinuationState(
        default_next_button(current_meta.button), modes[0], modes[1]
    )


@dataclass(frozen=True)
class FrontierValueEvaluation:
    qualifies_refantasy: bool
    immediate_points: int
    continuation_utility: float
    utility: float
    next_state: HUContinuationState


def evaluate_value_record(
    record: FantasyFrontierValueRecord,
    normal_board: Board,
    *,
    current_meta: HUContinuationState,
    fantasy_player: int,
    continuation_values: Mapping[HUContinuationState, float],
    variant: str = VARIANT_ULTIMATE,
) -> FrontierValueEvaluation:
    if record.incoming_count != current_meta.mode_for(fantasy_player):
        raise ValueError("frontier record count does not match current Fantasy mode")
    options = []
    for qualifies, immediate in (
        (False, record.no_refantasy_points),
        (True, record.refantasy_points),
    ):
        if immediate is None:
            continue
        nxt = _next_state(
            current_meta,
            normal_board,
            fantasy_player=fantasy_player,
            qualifies=qualifies,
            variant=variant,
        )
        if nxt not in continuation_values:
            raise KeyError(f"continuation value missing for {nxt.as_key()}")
        p0 = float(continuation_values[nxt])
        continuation = p0 if fantasy_player == 0 else -p0
        options.append((float(immediate) + continuation, int(immediate), qualifies, continuation, nxt))
    if not options:
        raise ValueError("frontier record has no evaluable branch")
    utility, immediate, qualifies, continuation, nxt = max(
        options, key=lambda row: (row[0], row[1], -int(row[2]))
    )
    return FrontierValueEvaluation(
        qualifies_refantasy=qualifies,
        immediate_points=immediate,
        continuation_utility=continuation,
        utility=utility,
        next_state=nxt,
    )


class ExactFantasyFrontierCache:
    def __init__(self) -> None:
        self.records: dict[str, FantasyFrontierValueRecord] = {}
        self.hits = 0
        self.misses = 0

    def get_or_build(
        self,
        incoming: Sequence[Card],
        normal_board: Board,
        *,
        variant: str = VARIANT_ULTIMATE,
    ) -> FantasyFrontierValueRecord:
        key = canonical_frontier_key(incoming, normal_board, variant=variant)
        old = self.records.get(key)
        if old is not None:
            self.hits += 1
            return old
        record = build_value_record(incoming, normal_board, variant=variant)
        if record.key != key:
            raise AssertionError("frontier cache key changed during exact build")
        self.records[key] = record
        self.misses += 1
        return record

    def payload(self) -> dict:
        base = {
            "schema": SCHEMA,
            "records": [self.records[key].payload() for key in sorted(self.records)],
        }
        base["sha256"] = hashlib.sha256(
            json.dumps(base, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest()
        return base
