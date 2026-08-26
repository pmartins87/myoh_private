from __future__ import annotations

"""Exact delayed Fantasy best response against a completed HU normal board.

Field evidence shows a KKPoker Fantasy player can remain unconfirmed while the
normal opponent progresses. When the opponent board is fully visible, the
Fantasy arrangement is no longer a guessed heuristic problem: for a supplied
cross-hand continuation vector we can exhaustively choose the 3/5/5 placement
that maximizes exact current score plus exact next-state value.

The search is exact for 14..17 physical cards and KKPoker row-local Joker
semantics. It does not claim that waiting until the opponent is complete is
always a legal/optimal timing rule; that timing is a separate field-rule gate.
It also does not claim the supplied continuation vector is solved.
"""

from bisect import bisect_right
from dataclasses import dataclass
from itertools import combinations
import time
from typing import Mapping, Sequence

from engine import (
    Board,
    Card,
    CAT_QUADS,
    CAT_TRIPS,
    HandRank,
    ResolvedBoard,
    ROW_BOTTOM,
    ROW_MIDDLE,
    ROW_TOP,
    _candidate_row_resolutions,
    resolve_board,
    royalty,
    score_heads_up,
)
from fantasy_transition import VARIANT_ULTIMATE, transition_from_board
from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_FANTASY,
    default_next_button,
    hand_kernel_kind,
    next_state_from_terminal_boards,
)

AUTHORITY = "EXACT_FANTASY_DELAYED_RESPONSE_GIVEN_CONTINUATION"
SCOPE = "HU_ONLY"


@dataclass(frozen=True)
class FantasyDelayedResponseResult:
    board: Board
    discarded: tuple[Card, ...]
    utility: float
    immediate_points: int
    continuation_utility: float
    next_state: HUContinuationState
    hero_royalties: int
    incoming_count: int
    mask_pairs: int
    legal_pairs: int
    row5_cache_entries: int
    row3_cache_entries: int
    top_frontiers: int
    top_envelopes: int
    elapsed_seconds: float
    authority: str = AUTHORITY


@dataclass(frozen=True)
class _TopChoice:
    variable_utility: float
    rank: HandRank
    mask: int
    qualifies_refantasy: bool


def _mask_for_indices(indices: Sequence[int]) -> int:
    mask = 0
    for index in indices:
        mask |= 1 << int(index)
    return mask


def _indices_for_mask(mask: int, count: int) -> tuple[int, ...]:
    return tuple(i for i in range(count) if mask & (1 << i))


def _compare(left: HandRank, right: HandRank) -> int:
    return 1 if left > right else -1 if left < right else 0


class _RowRankCache:
    def __init__(self, incoming: Sequence[Card]) -> None:
        self.incoming = tuple(incoming)
        self.three: dict[int, tuple[HandRank, ...]] = {}
        self.five: dict[int, tuple[HandRank, ...]] = {}

    def _cards(self, mask: int) -> tuple[Card, ...]:
        return tuple(
            self.incoming[i]
            for i in range(len(self.incoming))
            if mask & (1 << i)
        )

    def ranks(self, mask: int, *, top: bool) -> tuple[HandRank, ...]:
        cache = self.three if top else self.five
        expected = 3 if top else 5
        old = cache.get(mask)
        if old is not None:
            return old
        cards = self._cards(mask)
        if len(cards) != expected:
            raise AssertionError("row rank cache received wrong mask cardinality")
        # The engine returns strongest-first; store ascending for bisect queries.
        ranks = tuple(sorted({rank for rank, _resolved in _candidate_row_resolutions(cards)}))
        if not ranks:
            raise AssertionError("physical row produced no Joker resolution")
        cache[mask] = ranks
        return ranks


class _TopEnvelopeOracle:
    """Exact strongest-legal-Joker top query with cached upper-bound envelopes."""

    def __init__(
        self,
        incoming: Sequence[Card],
        rows: _RowRankCache,
        opponent: ResolvedBoard | None,
        continuation_by_qualifier: Mapping[bool, float],
    ) -> None:
        self.incoming = tuple(incoming)
        self.rows = rows
        self.opponent = opponent
        self.continuation = {
            False: float(continuation_by_qualifier[False]),
            True: float(continuation_by_qualifier[True]),
        }
        # remaining mask -> sorted events (rank, masks whose effective rank becomes rank)
        self.frontiers: dict[int, tuple[tuple[HandRank, tuple[int, ...]], ...]] = {}
        # (remaining, bottom qualifier, scoop context) -> (event ranks, best choices)
        self.envelopes: dict[
            tuple[int, bool, int],
            tuple[tuple[HandRank, ...], tuple[_TopChoice, ...]],
        ] = {}

    def _frontier(
        self, remaining: int
    ) -> tuple[tuple[HandRank, tuple[int, ...]], ...]:
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

    def _top_variable(
        self,
        rank: HandRank,
        *,
        bottom_qualifies: bool,
        scoop_context: int,
    ) -> tuple[float, bool]:
        qualifies = bottom_qualifies or rank.category == CAT_TRIPS
        value = float(royalty(rank, ROW_TOP)) + self.continuation[qualifies]
        if self.opponent is not None:
            top_point = _compare(rank, self.opponent.ranks[ROW_TOP])
            value += float(top_point)
            if scoop_context == 1 and top_point == 1:
                value += 3.0
            elif scoop_context == -1 and top_point == -1:
                value -= 3.0
        return value, qualifies

    @staticmethod
    def _better(candidate: _TopChoice, old: _TopChoice | None) -> bool:
        if old is None:
            return True
        if candidate.variable_utility != old.variable_utility:
            return candidate.variable_utility > old.variable_utility
        if candidate.rank != old.rank:
            return candidate.rank > old.rank
        return candidate.mask < old.mask

    def _build_envelope(
        self,
        remaining: int,
        bottom_qualifies: bool,
        scoop_context: int,
    ) -> tuple[tuple[HandRank, ...], tuple[_TopChoice, ...]]:
        key = (remaining, bool(bottom_qualifies), int(scoop_context))
        old = self.envelopes.get(key)
        if old is not None:
            return old

        # As the middle upper bound rises, each physical top mask is forced to
        # its strongest Joker interpretation not exceeding that bound. Updating
        # the current effective rank at every event exactly matches resolve_board.
        current: dict[int, HandRank] = {}
        event_ranks: list[HandRank] = []
        best_choices: list[_TopChoice] = []
        for event_rank, masks in self._frontier(remaining):
            for top_mask in masks:
                current[top_mask] = event_rank
            best: _TopChoice | None = None
            for top_mask, effective_rank in current.items():
                variable, qualifies = self._top_variable(
                    effective_rank,
                    bottom_qualifies=bottom_qualifies,
                    scoop_context=scoop_context,
                )
                candidate = _TopChoice(
                    variable_utility=variable,
                    rank=effective_rank,
                    mask=top_mask,
                    qualifies_refantasy=qualifies,
                )
                if self._better(candidate, best):
                    best = candidate
            if best is None:
                raise AssertionError("top envelope event produced no candidate")
            event_ranks.append(event_rank)
            best_choices.append(best)

        built = (tuple(event_ranks), tuple(best_choices))
        self.envelopes[key] = built
        return built

    def query(
        self,
        remaining: int,
        middle_rank: HandRank,
        *,
        bottom_qualifies: bool,
        scoop_context: int,
    ) -> _TopChoice | None:
        ranks, choices = self._build_envelope(
            remaining, bottom_qualifies, scoop_context
        )
        index = bisect_right(ranks, middle_rank) - 1
        if index < 0:
            return None
        return choices[index]


def _validate_physical_cards(incoming: Sequence[Card], opponent: Board) -> None:
    if len(set(incoming)) != len(incoming):
        raise ValueError("Fantasy incoming contains duplicate physical cards")
    opp_cards = tuple(card for row in opponent.rows() for card in row)
    if len(opp_cards) != 13 or not opponent.complete():
        raise ValueError("delayed Fantasy response requires complete opponent board")
    if len(set(opp_cards)) != 13:
        raise ValueError("opponent board contains duplicate physical cards")
    overlap = set(incoming) & set(opp_cards)
    if overlap:
        raise ValueError(
            "Fantasy incoming overlaps public opponent board: "
            + ",".join(sorted(str(card) for card in overlap))
        )


def solve_delayed_fantasy_best_response(
    incoming: Sequence[Card],
    opponent_board: Board,
    *,
    current_state: HUContinuationState,
    hero_player: int,
    continuation_values: Mapping[HUContinuationState, float],
    next_button: int | None = None,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyDelayedResponseResult:
    """Exhaustively solve one 14..17-card Fantasy arrangement after opponent completion."""
    start = time.perf_counter()
    cards = tuple(incoming)
    if hero_player not in (0, 1):
        raise ValueError("HU hero_player must be 0 or 1")
    if hand_kernel_kind(current_state) != KERNEL_NORMAL_FANTASY:
        raise ValueError("delayed response solver requires exactly one HU Fantasy player")
    hero_mode = current_state.mode_for(hero_player)
    opponent_player = 1 - hero_player
    if hero_mode not in (14, 15, 16, 17) or len(cards) != hero_mode:
        raise ValueError("incoming count must equal Hero's 14..17 Fantasy mode")
    if current_state.mode_for(opponent_player) != 0:
        raise ValueError("delayed response opponent must be in a normal hand")
    _validate_physical_cards(cards, opponent_board)

    opponent_resolved = resolve_board(opponent_board)
    opponent_transition = transition_from_board(
        opponent_board,
        current_fantasy_cards=0,
        variant=variant,
    )
    resolved_next_button = (
        default_next_button(current_state.button)
        if next_button is None
        else int(next_button)
    )

    def state_for_qualifier(qualifies: bool) -> HUContinuationState:
        modes = [0, 0]
        # Ultimate keeps the current Fantasy size on re-Fantasy; Progressive
        # returns 14. Invalid variants are already rejected by transition_from_board.
        modes[hero_player] = (
            hero_mode if qualifies and variant == VARIANT_ULTIMATE
            else 14 if qualifies
            else 0
        )
        modes[opponent_player] = opponent_transition.next_cards
        return HUContinuationState(
            resolved_next_button,
            modes[0],
            modes[1],
        )

    continuation_by_qualifier: dict[bool, float] = {}
    next_by_qualifier: dict[bool, HUContinuationState] = {}
    for qualifies in (False, True):
        nxt = state_for_qualifier(qualifies)
        if nxt not in continuation_values:
            raise KeyError(f"continuation value missing for {nxt.as_key()}")
        persistent_p0_value = float(continuation_values[nxt])
        continuation_by_qualifier[qualifies] = (
            persistent_p0_value if hero_player == 0 else -persistent_p0_value
        )
        next_by_qualifier[qualifies] = nxt

    n = len(cards)
    all_mask = (1 << n) - 1
    rows = _RowRankCache(cards)
    top_oracle = _TopEnvelopeOracle(
        cards,
        rows,
        opponent_resolved,
        continuation_by_qualifier,
    )

    mask_pairs = 0
    legal_pairs = 0
    best_key: tuple | None = None
    best_payload: tuple[int, int, int, HandRank, HandRank, HandRank, bool, float] | None = None

    for bottom_combo in combinations(range(n), 5):
        bottom_mask = _mask_for_indices(bottom_combo)
        bottom_ranks = rows.ranks(bottom_mask, top=False)
        bottom_rank = bottom_ranks[-1]  # strongest physical-row interpretation
        bottom_qualifies = bottom_rank.category >= CAT_QUADS
        bottom_royalty = royalty(bottom_rank, ROW_BOTTOM)
        available = tuple(i for i in range(n) if not (bottom_mask & (1 << i)))

        for middle_combo in combinations(available, 5):
            middle_mask = _mask_for_indices(middle_combo)
            mask_pairs += 1
            middle_ranks = rows.ranks(middle_mask, top=False)
            middle_index = bisect_right(middle_ranks, bottom_rank) - 1
            if middle_index < 0:
                continue
            middle_rank = middle_ranks[middle_index]
            middle_royalty = royalty(middle_rank, ROW_MIDDLE)
            remaining = all_mask ^ (bottom_mask | middle_mask)

            if opponent_resolved is None:
                fixed = 6.0 + float(bottom_royalty + middle_royalty)
                scoop_context = 0
            else:
                bottom_point = _compare(
                    bottom_rank, opponent_resolved.ranks[ROW_BOTTOM]
                )
                middle_point = _compare(
                    middle_rank, opponent_resolved.ranks[ROW_MIDDLE]
                )
                scoop_context = (
                    1 if bottom_point == 1 and middle_point == 1
                    else -1 if bottom_point == -1 and middle_point == -1
                    else 0
                )
                fixed = float(
                    bottom_point
                    + middle_point
                    + bottom_royalty
                    + middle_royalty
                    - opponent_resolved.royalties
                )

            top_choice = top_oracle.query(
                remaining,
                middle_rank,
                bottom_qualifies=bottom_qualifies,
                scoop_context=scoop_context,
            )
            if top_choice is None:
                continue
            legal_pairs += 1
            utility = fixed + top_choice.variable_utility
            candidate_key = (
                utility,
                bottom_rank,
                middle_rank,
                top_choice.rank,
                -bottom_mask,
                -middle_mask,
                -top_choice.mask,
            )
            if best_key is None or candidate_key > best_key:
                best_key = candidate_key
                best_payload = (
                    top_choice.mask,
                    middle_mask,
                    bottom_mask,
                    top_choice.rank,
                    middle_rank,
                    bottom_rank,
                    top_choice.qualifies_refantasy,
                    utility,
                )

    if best_payload is None:
        raise RuntimeError("no legal 3/5/5 Fantasy board exists for incoming cards")

    (
        top_mask,
        middle_mask,
        bottom_mask,
        top_rank,
        middle_rank,
        bottom_rank,
        qualifies,
        optimized_utility,
    ) = best_payload
    selected_mask = top_mask | middle_mask | bottom_mask
    board = Board(
        top=tuple(cards[i] for i in _indices_for_mask(top_mask, n)),
        middle=tuple(cards[i] for i in _indices_for_mask(middle_mask, n)),
        bottom=tuple(cards[i] for i in _indices_for_mask(bottom_mask, n)),
    )
    discarded = tuple(
        cards[i] for i in range(n) if not (selected_mask & (1 << i))
    )
    if len(discarded) != n - 13:
        raise AssertionError("exact Fantasy response selected wrong discard count")

    resolved = resolve_board(board)
    if resolved is None:
        raise AssertionError("optimized Fantasy response reconstructed as a foul")
    if resolved.ranks != (top_rank, middle_rank, bottom_rank):
        raise AssertionError(
            "top-envelope Joker interpretation disagrees with authoritative resolver"
        )

    immediate = score_heads_up(board, opponent_board).points
    if hero_player == 0:
        persistent_board0, persistent_board1 = board, opponent_board
    else:
        persistent_board0, persistent_board1 = opponent_board, board
    exact_next = next_state_from_terminal_boards(
        current_state,
        persistent_board0,
        persistent_board1,
        next_button=resolved_next_button,
        variant=variant,
    )
    if exact_next != next_by_qualifier[qualifies]:
        raise AssertionError("optimized qualifier disagrees with exact transition module")
    continuation_utility = (
        float(continuation_values[exact_next])
        if hero_player == 0
        else -float(continuation_values[exact_next])
    )
    exact_utility = float(immediate) + continuation_utility
    if abs(exact_utility - optimized_utility) > 1e-9:
        raise AssertionError(
            "optimized Fantasy utility disagrees with independent terminal scorer"
        )

    return FantasyDelayedResponseResult(
        board=board,
        discarded=discarded,
        utility=exact_utility,
        immediate_points=immediate,
        continuation_utility=continuation_utility,
        next_state=exact_next,
        hero_royalties=resolved.royalties,
        incoming_count=n,
        mask_pairs=mask_pairs,
        legal_pairs=legal_pairs,
        row5_cache_entries=len(rows.five),
        row3_cache_entries=len(rows.three),
        top_frontiers=len(top_oracle.frontiers),
        top_envelopes=len(top_oracle.envelopes),
        elapsed_seconds=time.perf_counter() - start,
    )
