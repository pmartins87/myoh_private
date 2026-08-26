from __future__ import annotations

"""Continuation-independent exact frontier for delayed HU Fantasy response.

For a fixed Fantasy packet and completed normal opponent board, the exact next
HU state has only two possible Hero branches: re-Fantasy or no re-Fantasy.  The
opponent transition and next button are fixed.  Therefore we can solve the best
*immediate* arrangement in each reachable branch once, then evaluate any future
50-state continuation vector with two scalar additions instead of rerunning the
14..17-card combinatorial search.

This is an exact factorization, not an approximation.  It is especially useful
for outer relative-value iteration, where V changes repeatedly while the same
terminal sample may be revisited.
"""

from dataclasses import dataclass
from math import comb
from typing import Mapping, Sequence

from engine import Board, Card
from fantasy_delayed_response import solve_delayed_fantasy_best_response
from fantasy_transition import VARIANT_ULTIMATE, transition_from_board
from hu_continuation import (
    HUContinuationState,
    all_states,
    default_next_button,
)

AUTHORITY = "EXACT_FANTASY_RESPONSE_FRONTIER"
MAX_BOARD_ROYALTIES = 22 + 50 + 25
MAX_ABS_HEADSUP_POINTS = 6 + MAX_BOARD_ROYALTIES  # 103
MAX_IMMEDIATE_SPAN = 2 * MAX_ABS_HEADSUP_POINTS   # 206
FORCE_MARGIN = 1000.0
if FORCE_MARGIN <= MAX_IMMEDIATE_SPAN:
    raise AssertionError("Fantasy qualifier force margin is not mathematically dominant")


@dataclass(frozen=True)
class FantasyFrontierCandidate:
    qualifies_refantasy: bool
    board: Board
    discarded: tuple[Card, ...]
    immediate_points: int
    next_state: HUContinuationState


@dataclass(frozen=True)
class FantasyResponseFrontier:
    hero_player: int
    incoming_count: int
    no_refantasy: FantasyFrontierCandidate | None
    refantasy: FantasyFrontierCandidate | None
    authority: str = AUTHORITY

    @property
    def candidate_count(self) -> int:
        return int(self.no_refantasy is not None) + int(self.refantasy is not None)


@dataclass(frozen=True)
class FantasyFrontierEvaluation:
    candidate: FantasyFrontierCandidate
    continuation_utility: float
    utility: float


def mask_pair_count(incoming_count: int) -> int:
    if incoming_count not in (14, 15, 16, 17):
        raise ValueError("Fantasy count must be 14..17")
    return comb(incoming_count, 5) * comb(incoming_count - 5, 5)


def _next_states_by_qualifier(
    current_state: HUContinuationState,
    opponent_board: Board,
    *,
    hero_player: int,
    next_button: int | None,
    variant: str,
) -> dict[bool, HUContinuationState]:
    if hero_player not in (0, 1):
        raise ValueError("HU hero_player must be 0 or 1")
    opponent_player = 1 - hero_player
    hero_mode = current_state.mode_for(hero_player)
    if hero_mode not in (14, 15, 16, 17):
        raise ValueError("Hero must currently be in Fantasy")
    if current_state.mode_for(opponent_player) != 0:
        raise ValueError("frontier requires exactly one Fantasy player")
    opponent_transition = transition_from_board(
        opponent_board,
        current_fantasy_cards=0,
        variant=variant,
    )
    button = (
        default_next_button(current_state.button)
        if next_button is None
        else int(next_button)
    )
    result = {}
    for qualifies in (False, True):
        modes = [0, 0]
        modes[opponent_player] = opponent_transition.next_cards
        modes[hero_player] = (
            hero_mode if qualifies and variant == VARIANT_ULTIMATE
            else 14 if qualifies
            else 0
        )
        result[qualifies] = HUContinuationState(button, modes[0], modes[1])
    return result


def _forcing_vector(
    next_states: Mapping[bool, HUContinuationState],
    *,
    hero_player: int,
    desired: bool,
) -> dict[HUContinuationState, float]:
    values = {state: 0.0 for state in all_states()}
    # Give the desired branch +M Hero utility and the other branch 0. Since the
    # immediate score span is <=206 and M=1000, any reachable desired branch
    # must beat every undesired arrangement irrespective of current points.
    persistent_value = FORCE_MARGIN if hero_player == 0 else -FORCE_MARGIN
    values[next_states[desired]] = persistent_value
    return values


def build_fantasy_response_frontier(
    incoming: Sequence[Card],
    opponent_board: Board,
    *,
    current_state: HUContinuationState,
    hero_player: int,
    next_button: int | None = None,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyResponseFrontier:
    cards = tuple(incoming)
    if len(cards) not in (14, 15, 16, 17):
        raise ValueError("Fantasy frontier requires 14..17 incoming cards")
    next_states = _next_states_by_qualifier(
        current_state,
        opponent_board,
        hero_player=hero_player,
        next_button=next_button,
        variant=variant,
    )

    candidates: dict[bool, FantasyFrontierCandidate | None] = {}
    for desired in (False, True):
        forced = solve_delayed_fantasy_best_response(
            cards,
            opponent_board,
            current_state=current_state,
            hero_player=hero_player,
            continuation_values=_forcing_vector(
                next_states, hero_player=hero_player, desired=desired
            ),
            next_button=next_button,
            variant=variant,
        )
        reached = forced.next_state == next_states[desired]
        if not reached:
            # Dominant forcing proves this branch is unreachable: if any legal
            # desired arrangement existed, its +1000 bonus would beat an
            # undesired arrangement by at least 794 points.
            candidates[desired] = None
            continue
        candidates[desired] = FantasyFrontierCandidate(
            qualifies_refantasy=desired,
            board=forced.board,
            discarded=forced.discarded,
            immediate_points=int(forced.immediate_points),
            next_state=forced.next_state,
        )

    if candidates[False] is None and candidates[True] is None:
        raise AssertionError("Fantasy frontier found no reachable terminal branch")
    return FantasyResponseFrontier(
        hero_player=hero_player,
        incoming_count=len(cards),
        no_refantasy=candidates[False],
        refantasy=candidates[True],
    )


def evaluate_fantasy_response_frontier(
    frontier: FantasyResponseFrontier,
    continuation_values: Mapping[HUContinuationState, float],
) -> FantasyFrontierEvaluation:
    options = [
        candidate
        for candidate in (frontier.no_refantasy, frontier.refantasy)
        if candidate is not None
    ]
    if not options:
        raise ValueError("Fantasy frontier has no candidates")
    scored = []
    for candidate in options:
        if candidate.next_state not in continuation_values:
            raise KeyError(f"continuation value missing for {candidate.next_state.as_key()}")
        persistent_p0 = float(continuation_values[candidate.next_state])
        hero_continuation = (
            persistent_p0 if frontier.hero_player == 0 else -persistent_p0
        )
        total = float(candidate.immediate_points) + hero_continuation
        scored.append((total, candidate.immediate_points, candidate, hero_continuation))
    # Deterministic tie-break: total utility, immediate score, no-refantasy
    # before refantasy only if mathematically tied on both values.
    total, _immediate, candidate, continuation = max(
        scored,
        key=lambda row: (
            row[0], row[1], -int(row[2].qualifies_refantasy)
        ),
    )
    return FantasyFrontierEvaluation(
        candidate=candidate,
        continuation_utility=continuation,
        utility=total,
    )
