from __future__ import annotations

"""Exact poker teacher for a Fantasy packet against a completed opponent board.

For normal-vs-Fantasy this is identical to M4H.  For Fantasy-vs-Fantasy the
completed opponent board is counterfactual teacher information only: sealed
M4M policies never receive it.  The expensive one-pass search is reused because
branchwise immediate optima depend on cards and score, not on the opponent's
incoming Fantasy mode.  Only the attached next meta-state must be remapped.
"""

from dataclasses import replace
from typing import Sequence

from engine import Board, Card
from fantasy_response_frontier import FantasyResponseFrontier
from fantasy_response_frontier_onepass import build_fantasy_response_frontier_onepass
from fantasy_transition import VARIANT_ULTIMATE, transition_from_board
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    default_next_button,
    hand_kernel_kind,
)

AUTHORITY = "EXACT_FANTASY_COUNTERFACTUAL_FRONTIER_ONEPASS"
POLICY_FIREWALL = "COMPLETED_OPPONENT_BOARD_IS_TEACHER_ONLY_FOR_SEALED_FANTASY_FANTASY"


def _proxy_asymmetric_state(
    current_state: HUContinuationState,
    hero_player: int,
) -> HUContinuationState:
    modes = [0, 0]
    modes[hero_player] = current_state.mode_for(hero_player)
    return HUContinuationState(current_state.button, modes[0], modes[1])


def _actual_next_state(
    current_state: HUContinuationState,
    opponent_board: Board,
    *,
    hero_player: int,
    qualifies_refantasy: bool,
    next_button: int | None,
    variant: str,
) -> HUContinuationState:
    opponent = 1 - hero_player
    hero_mode = current_state.mode_for(hero_player)
    opponent_mode = current_state.mode_for(opponent)
    opponent_transition = transition_from_board(
        opponent_board,
        current_fantasy_cards=opponent_mode,
        variant=variant,
    )
    modes = [0, 0]
    modes[opponent] = opponent_transition.next_cards
    modes[hero_player] = (
        hero_mode if qualifies_refantasy and variant == VARIANT_ULTIMATE
        else 14 if qualifies_refantasy
        else 0
    )
    button = default_next_button(current_state.button) if next_button is None else int(next_button)
    return HUContinuationState(button, modes[0], modes[1])


def build_fantasy_counterfactual_frontier(
    incoming: Sequence[Card],
    opponent_board: Board,
    *,
    current_state: HUContinuationState,
    hero_player: int,
    next_button: int | None = None,
    variant: str = VARIANT_ULTIMATE,
) -> FantasyResponseFrontier:
    if hero_player not in (0, 1):
        raise ValueError("HU hero_player must be 0 or 1")
    kind = hand_kernel_kind(current_state)
    if kind not in (KERNEL_NORMAL_FANTASY, KERNEL_FANTASY_FANTASY):
        raise ValueError("counterfactual frontier requires Hero in Fantasy")
    hero_mode = current_state.mode_for(hero_player)
    if hero_mode not in (14, 15, 16, 17) or len(tuple(incoming)) != hero_mode:
        raise ValueError("incoming count must equal Hero Fantasy mode")

    if kind == KERNEL_NORMAL_FANTASY:
        frontier = build_fantasy_response_frontier_onepass(
            incoming,
            opponent_board,
            current_state=current_state,
            hero_player=hero_player,
            next_button=next_button,
            variant=variant,
        )
    else:
        # M4H's search uses next-state metadata only after branchwise immediate
        # optima are found.  A proxy normal opponent therefore preserves every
        # selected board/score while letting us reuse the certified search.
        frontier = build_fantasy_response_frontier_onepass(
            incoming,
            opponent_board,
            current_state=_proxy_asymmetric_state(current_state, hero_player),
            hero_player=hero_player,
            next_button=next_button,
            variant=variant,
        )

    def remap(candidate):
        if candidate is None:
            return None
        return replace(
            candidate,
            next_state=_actual_next_state(
                current_state,
                opponent_board,
                hero_player=hero_player,
                qualifies_refantasy=candidate.qualifies_refantasy,
                next_button=next_button,
                variant=variant,
            ),
        )

    return FantasyResponseFrontier(
        hero_player=hero_player,
        incoming_count=frontier.incoming_count,
        no_refantasy=remap(frontier.no_refantasy),
        refantasy=remap(frontier.refantasy),
        authority=AUTHORITY,
    )
