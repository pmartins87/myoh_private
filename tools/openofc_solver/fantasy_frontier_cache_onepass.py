from __future__ import annotations

"""Value-only cache backed by the M4H one-pass exact Fantasy frontier."""

from typing import Mapping, Sequence

from engine import Board, Card
from fantasy_frontier_cache import (
    FantasyFrontierValueRecord,
    FrontierValueEvaluation,
    canonical_frontier_key,
    evaluate_value_record,
)
from fantasy_response_frontier_onepass import build_fantasy_response_frontier_onepass
from fantasy_transition import VARIANT_ULTIMATE
from hu_continuation import HUContinuationState


ONEPASS_RECORD_AUTHORITY = "EXACT_DELAYED_FANTASY_IMMEDIATE_FRONTIER_ONEPASS"


def build_value_record_onepass(
    incoming: Sequence[Card],
    normal_board: Board,
    *,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyFrontierValueRecord:
    cards = tuple(incoming)
    normalized = HUContinuationState(
        button=0,
        p0_fantasy_cards=len(cards),
        p1_fantasy_cards=0,
    )
    frontier = build_fantasy_response_frontier_onepass(
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
        authority=ONEPASS_RECORD_AUTHORITY,
    )


class OnePassExactFantasyFrontierCache:
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
        record = build_value_record_onepass(incoming, normal_board, variant=variant)
        if record.key != key:
            raise AssertionError("one-pass frontier cache key changed during exact build")
        self.records[key] = record
        self.misses += 1
        return record

    def evaluate(
        self,
        record: FantasyFrontierValueRecord,
        normal_board: Board,
        *,
        current_meta: HUContinuationState,
        fantasy_player: int,
        continuation_values: Mapping[HUContinuationState, float],
        variant: str = VARIANT_ULTIMATE,
    ) -> FrontierValueEvaluation:
        return evaluate_value_record(
            record,
            normal_board,
            current_meta=current_meta,
            fantasy_player=fantasy_player,
            continuation_values=continuation_values,
            variant=variant,
        )
