from __future__ import annotations

"""One-pass exact delayed-Fantasy response frontier.

M4D originally obtained the two continuation branches (leave Fantasy / remain
in Fantasy) by running the complete 14..17-card optimizer twice with a dominant
continuation bonus.  That proof is exact, but it duplicates almost all row-rank
and bottom/middle enumeration work.

This module computes the same two exact immediate-score branches in one
bottom/middle traversal.  It is an optimization only: no action abstraction,
no sampling and no learned value enter this routine.
"""

from bisect import bisect_right
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from engine import (
    Board,
    Card,
    CAT_QUADS,
    CAT_TRIPS,
    HandRank,
    ROW_BOTTOM,
    ROW_MIDDLE,
    ROW_TOP,
    resolve_board,
    royalty,
    score_heads_up,
)
from fantasy_delayed_response import (
    _RowRankCache,
    _compare,
    _indices_for_mask,
    _mask_for_indices,
    _validate_physical_cards,
)
from fantasy_response_frontier import (
    AUTHORITY,
    FantasyFrontierCandidate,
    FantasyResponseFrontier,
    _next_states_by_qualifier,
)
from fantasy_transition import VARIANT_ULTIMATE
from hu_continuation import HUContinuationState

ONEPASS_AUTHORITY = "EXACT_FANTASY_RESPONSE_FRONTIER_ONEPASS"


@dataclass(frozen=True)
class _TopChoice:
    variable_points: int
    rank: HandRank
    mask: int
    qualifies_refantasy: bool


class _BranchTopEnvelopeOracle:
    """Return best top choice separately for both re-Fantasy branches.

    The envelope is indexed by the maximum legal top rank (the chosen middle
    rank).  For each physical 3-card top mask, Joker semantics select the
    strongest interpretation not exceeding that bound, exactly like
    ``resolve_board``.  We maintain separate maxima for qualifier=False/True.
    """

    def __init__(
        self,
        incoming: Sequence[Card],
        rows: _RowRankCache,
        opponent_resolved,
    ) -> None:
        self.incoming = tuple(incoming)
        self.rows = rows
        self.opponent = opponent_resolved
        self.frontiers: dict[int, tuple[tuple[HandRank, tuple[int, ...]], ...]] = {}
        self.envelopes: dict[
            tuple[int, bool, int],
            tuple[
                tuple[HandRank, ...],
                tuple[tuple[_TopChoice | None, _TopChoice | None], ...],
            ],
        ] = {}

    def _frontier(self, remaining: int):
        old = self.frontiers.get(remaining)
        if old is not None:
            return old
        indices = _indices_for_mask(remaining, len(self.incoming))
        if len(indices) < 3:
            raise AssertionError("Fantasy remaining set cannot fill top")
        events: dict[HandRank, list[int]] = {}
        for combo in combinations(indices, 3):
            top_mask = _mask_for_indices(combo)
            for rank in self.rows.ranks(top_mask, top=True):
                events.setdefault(rank, []).append(top_mask)
        built = tuple(
            (rank, tuple(sorted(set(events[rank]))))
            for rank in sorted(events)
        )
        if not built:
            raise AssertionError("Fantasy top frontier is empty")
        self.frontiers[remaining] = built
        return built

    @staticmethod
    def _better(candidate: _TopChoice, old: _TopChoice | None) -> bool:
        if old is None:
            return True
        if candidate.variable_points != old.variable_points:
            return candidate.variable_points > old.variable_points
        if candidate.rank != old.rank:
            return candidate.rank > old.rank
        return candidate.mask < old.mask

    def _variable_points(self, rank: HandRank, scoop_context: int) -> int:
        value = int(royalty(rank, ROW_TOP))
        if self.opponent is not None:
            top_point = _compare(rank, self.opponent.ranks[ROW_TOP])
            value += top_point
            if scoop_context == 1 and top_point == 1:
                value += 3
            elif scoop_context == -1 and top_point == -1:
                value -= 3
        return value

    def _build_envelope(
        self,
        remaining: int,
        bottom_qualifies: bool,
        scoop_context: int,
    ):
        key = (remaining, bool(bottom_qualifies), int(scoop_context))
        old = self.envelopes.get(key)
        if old is not None:
            return old

        current: dict[int, HandRank] = {}
        event_ranks: list[HandRank] = []
        event_choices: list[tuple[_TopChoice | None, _TopChoice | None]] = []
        for event_rank, masks in self._frontier(remaining):
            for top_mask in masks:
                current[top_mask] = event_rank
            best: list[_TopChoice | None] = [None, None]
            for top_mask, effective_rank in current.items():
                qualifies = bool(bottom_qualifies or effective_rank.category == CAT_TRIPS)
                candidate = _TopChoice(
                    variable_points=self._variable_points(effective_rank, scoop_context),
                    rank=effective_rank,
                    mask=top_mask,
                    qualifies_refantasy=qualifies,
                )
                slot = int(qualifies)
                if self._better(candidate, best[slot]):
                    best[slot] = candidate
            event_ranks.append(event_rank)
            event_choices.append((best[0], best[1]))

        built = (tuple(event_ranks), tuple(event_choices))
        self.envelopes[key] = built
        return built

    def query(
        self,
        remaining: int,
        middle_rank: HandRank,
        *,
        bottom_qualifies: bool,
        scoop_context: int,
    ) -> tuple[_TopChoice | None, _TopChoice | None]:
        ranks, choices = self._build_envelope(
            remaining, bottom_qualifies, scoop_context
        )
        index = bisect_right(ranks, middle_rank) - 1
        if index < 0:
            return None, None
        return choices[index]


def build_fantasy_response_frontier_onepass(
    incoming: Sequence[Card],
    opponent_board: Board,
    *,
    current_state: HUContinuationState,
    hero_player: int,
    next_button: int | None = None,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyResponseFrontier:
    """Compute exact no-re-Fantasy/re-Fantasy immediate optima in one traversal."""
    cards = tuple(incoming)
    if len(cards) not in (14, 15, 16, 17):
        raise ValueError("Fantasy frontier requires 14..17 incoming cards")
    _validate_physical_cards(cards, opponent_board)
    next_states = _next_states_by_qualifier(
        current_state,
        opponent_board,
        hero_player=hero_player,
        next_button=next_button,
        variant=variant,
    )
    opponent_resolved = resolve_board(opponent_board)
    n = len(cards)
    all_mask = (1 << n) - 1
    rows = _RowRankCache(cards)
    top_oracle = _BranchTopEnvelopeOracle(cards, rows, opponent_resolved)

    # branch -> (comparison key, top mask, middle mask, bottom mask, ranks)
    best: dict[bool, tuple[tuple, int, int, int, HandRank, HandRank, HandRank]] = {}

    for bottom_combo in combinations(range(n), 5):
        bottom_mask = _mask_for_indices(bottom_combo)
        bottom_ranks = rows.ranks(bottom_mask, top=False)
        bottom_rank = bottom_ranks[-1]
        bottom_qualifies = bottom_rank.category >= CAT_QUADS
        bottom_royalty = royalty(bottom_rank, ROW_BOTTOM)
        available = tuple(i for i in range(n) if not (bottom_mask & (1 << i)))

        for middle_combo in combinations(available, 5):
            middle_mask = _mask_for_indices(middle_combo)
            middle_ranks = rows.ranks(middle_mask, top=False)
            middle_index = bisect_right(middle_ranks, bottom_rank) - 1
            if middle_index < 0:
                continue
            middle_rank = middle_ranks[middle_index]
            middle_royalty = royalty(middle_rank, ROW_MIDDLE)
            remaining = all_mask ^ (bottom_mask | middle_mask)

            if opponent_resolved is None:
                fixed = 6 + bottom_royalty + middle_royalty
                scoop_context = 0
            else:
                bottom_point = _compare(bottom_rank, opponent_resolved.ranks[ROW_BOTTOM])
                middle_point = _compare(middle_rank, opponent_resolved.ranks[ROW_MIDDLE])
                scoop_context = (
                    1 if bottom_point == 1 and middle_point == 1
                    else -1 if bottom_point == -1 and middle_point == -1
                    else 0
                )
                fixed = (
                    bottom_point
                    + middle_point
                    + bottom_royalty
                    + middle_royalty
                    - opponent_resolved.royalties
                )

            choices = top_oracle.query(
                remaining,
                middle_rank,
                bottom_qualifies=bottom_qualifies,
                scoop_context=scoop_context,
            )
            for qualifies, top_choice in ((False, choices[0]), (True, choices[1])):
                if top_choice is None:
                    continue
                immediate = int(fixed + top_choice.variable_points)
                candidate_key = (
                    immediate,
                    bottom_rank,
                    middle_rank,
                    top_choice.rank,
                    -bottom_mask,
                    -middle_mask,
                    -top_choice.mask,
                )
                old = best.get(qualifies)
                if old is None or candidate_key > old[0]:
                    best[qualifies] = (
                        candidate_key,
                        top_choice.mask,
                        middle_mask,
                        bottom_mask,
                        top_choice.rank,
                        middle_rank,
                        bottom_rank,
                    )

    candidates: dict[bool, FantasyFrontierCandidate | None] = {False: None, True: None}
    for qualifies in (False, True):
        payload = best.get(qualifies)
        if payload is None:
            continue
        (_key, top_mask, middle_mask, bottom_mask, top_rank, middle_rank, bottom_rank) = payload
        selected = top_mask | middle_mask | bottom_mask
        board = Board(
            top=tuple(cards[i] for i in _indices_for_mask(top_mask, n)),
            middle=tuple(cards[i] for i in _indices_for_mask(middle_mask, n)),
            bottom=tuple(cards[i] for i in _indices_for_mask(bottom_mask, n)),
        )
        discarded = tuple(cards[i] for i in range(n) if not (selected & (1 << i)))
        resolved = resolve_board(board)
        if resolved is None:
            raise AssertionError("one-pass exact frontier reconstructed a foul")
        if resolved.ranks != (top_rank, middle_rank, bottom_rank):
            raise AssertionError("one-pass Joker ranks disagree with authoritative resolver")
        immediate = int(score_heads_up(board, opponent_board).points)
        if immediate != int(payload[0][0]):
            raise AssertionError("one-pass score disagrees with authoritative scorer")
        actual_qualifies = bool(
            resolved.ranks[ROW_TOP].category == CAT_TRIPS
            or resolved.ranks[ROW_BOTTOM].category >= CAT_QUADS
        )
        if actual_qualifies != qualifies:
            raise AssertionError("one-pass branch qualification mismatch")
        candidates[qualifies] = FantasyFrontierCandidate(
            qualifies_refantasy=qualifies,
            board=board,
            discarded=discarded,
            immediate_points=immediate,
            next_state=next_states[qualifies],
        )

    if candidates[False] is None and candidates[True] is None:
        raise AssertionError("one-pass Fantasy frontier found no reachable branch")
    result = FantasyResponseFrontier(
        hero_player=hero_player,
        incoming_count=n,
        no_refantasy=candidates[False],
        refantasy=candidates[True],
        authority=AUTHORITY,
    )
    return result
