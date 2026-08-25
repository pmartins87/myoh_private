from __future__ import annotations

"""Exact HU cross-hand Fantasy state plumbing.

This module is intentionally small and exact. It does not guess the value of a
Fantasy hand and it does not claim to solve the infinite-horizon game. Instead
it defines the complete 50-state HU meta-state surface and the exact transition
from two completed boards into the next hand.

A later one-hand equilibrium oracle can therefore optimize

    current_hand_points + continuation_value[next_state]

without hard-coding a Fantasy bonus. The continuation vector is an explicit
input until the outer average-reward/fixed-point solve is implemented.

Player exchange is also an exact zero-sum automorphism for this state surface:
swapping player identities and the button maps every state to a partner whose
player-0 value has the opposite sign. None of the 50 states is self-mapped
because the button changes, so only 25 signed canonical representatives need to
be solved while table funds are not part of the state.
"""

from dataclasses import dataclass
from itertools import product
from typing import Mapping

from engine import Board, score_heads_up
from fantasy_transition import (
    VALID_FANTASY_COUNTS,
    VARIANT_ULTIMATE,
    transition_from_board,
)

NORMAL = 0
HU_MODES: tuple[int, ...] = (NORMAL, *VALID_FANTASY_COUNTS)
STATE_COUNT = 2 * len(HU_MODES) * len(HU_MODES)
PLAYER_EXCHANGE_ORBIT_COUNT = STATE_COUNT // 2
AUTHORITY = "EXACT_HU_CONTINUATION_STATE_TRANSITION"

KERNEL_NORMAL_NORMAL = "NORMAL_NORMAL"
KERNEL_NORMAL_FANTASY = "NORMAL_FANTASY_ASYMMETRIC"
KERNEL_FANTASY_FANTASY = "FANTASY_FANTASY"


@dataclass(frozen=True, order=True)
class HUContinuationState:
    """State carried from one HU hand to the next.

    `button` is the player who owns the dealer/button in that hand (0 or 1).
    `p0_fantasy_cards` and `p1_fantasy_cards` are 0 for normal play or one of
    14/15/16/17 for the exact Fantasy deal size.
    """

    button: int
    p0_fantasy_cards: int = NORMAL
    p1_fantasy_cards: int = NORMAL

    def __post_init__(self) -> None:
        if self.button not in (0, 1):
            raise ValueError("HU button must be player 0 or player 1")
        if self.p0_fantasy_cards not in HU_MODES:
            raise ValueError("invalid player-0 Fantasy mode")
        if self.p1_fantasy_cards not in HU_MODES:
            raise ValueError("invalid player-1 Fantasy mode")

    def mode_for(self, player: int) -> int:
        if player == 0:
            return self.p0_fantasy_cards
        if player == 1:
            return self.p1_fantasy_cards
        raise ValueError("HU player must be 0 or 1")

    def as_key(self) -> str:
        return (
            f"B{self.button}:P0F{self.p0_fantasy_cards}:"
            f"P1F{self.p1_fantasy_cards}"
        )


def all_states() -> tuple[HUContinuationState, ...]:
    states = tuple(
        HUContinuationState(button, p0_mode, p1_mode)
        for button, p0_mode, p1_mode in product((0, 1), HU_MODES, HU_MODES)
    )
    if len(states) != STATE_COUNT or len(set(states)) != STATE_COUNT:
        raise AssertionError("HU continuation catalog must contain 50 states")
    return states


def hand_kernel_kind(state: HUContinuationState) -> str:
    """Classify which strategic one-hand kernel owns a meta-state."""
    f0 = state.p0_fantasy_cards > 0
    f1 = state.p1_fantasy_cards > 0
    if not f0 and not f1:
        return KERNEL_NORMAL_NORMAL
    if f0 != f1:
        return KERNEL_NORMAL_FANTASY
    return KERNEL_FANTASY_FANTASY


def identity_for_role(state: HUContinuationState, role: int) -> int:
    """Map relative one-hand role 0=nondealer, 1=dealer to persistent identity."""
    if role == 0:
        return 1 - state.button
    if role == 1:
        return state.button
    raise ValueError("HU role must be 0=nondealer or 1=dealer")


def role_for_identity(state: HUContinuationState, player: int) -> int:
    if player not in (0, 1):
        raise ValueError("HU player must be 0 or 1")
    return 1 if player == state.button else 0


def modes_in_role_order(state: HUContinuationState) -> tuple[int, int]:
    """Return (nondealer_mode, dealer_mode) for relative-role one-hand solvers."""
    return (
        state.mode_for(identity_for_role(state, 0)),
        state.mode_for(identity_for_role(state, 1)),
    )


def utility_from_nondealer_perspective_to_p0(
    state: HUContinuationState,
    nondealer_utility: float,
) -> float:
    """Convert a relative-role HU zero-sum utility to persistent player 0."""
    return (
        float(nondealer_utility)
        if identity_for_role(state, 0) == 0
        else -float(nondealer_utility)
    )


def swap_players(state: HUContinuationState) -> HUContinuationState:
    """Exact player-label exchange automorphism."""
    return HUContinuationState(
        button=1 - state.button,
        p0_fantasy_cards=state.p1_fantasy_cards,
        p1_fantasy_cards=state.p0_fantasy_cards,
    )


def canonical_player_exchange(
    state: HUContinuationState,
) -> tuple[HUContinuationState, int]:
    """Return canonical player-exchange representative and player-0 value sign.

    If sign is +1, V(state)=V(canonical). If sign is -1,
    V(state)=-V(canonical). This reduction is exact for the declared zero-sum
    50-state model; if asymmetric table funds are later added, funds must also be
    swapped before this automorphism remains valid.
    """
    partner = swap_players(state)
    if state <= partner:
        return state, 1
    return partner, -1


def canonical_states() -> tuple[HUContinuationState, ...]:
    representatives = tuple(sorted({canonical_player_exchange(s)[0] for s in all_states()}))
    if len(representatives) != PLAYER_EXCHANGE_ORBIT_COUNT:
        raise AssertionError("HU player exchange must reduce 50 states to 25 orbits")
    return representatives


def expand_antisymmetric_values(
    canonical_values: Mapping[HUContinuationState, float],
) -> dict[HUContinuationState, float]:
    """Expand 25 canonical persistent-player values to the full 50-state map."""
    reps = canonical_states()
    missing = [state for state in reps if state not in canonical_values]
    if missing:
        raise ValueError(f"canonical continuation map is incomplete: {len(missing)} missing")
    out: dict[HUContinuationState, float] = {}
    for state in all_states():
        canonical, sign = canonical_player_exchange(state)
        out[state] = sign * float(canonical_values[canonical])
    return out


def default_next_button(current_button: int) -> int:
    """Standard HU button alternation helper.

    The strategic integration layer may pass an explicit next button when live
    evidence requires it. Keeping this helper separate prevents the terminal
    Fantasy rule itself from depending on UI/dealer-marker inference.
    """
    if current_button not in (0, 1):
        raise ValueError("HU button must be player 0 or player 1")
    return 1 - current_button


def next_state_from_terminal_boards(
    current: HUContinuationState,
    board0: Board,
    board1: Board,
    *,
    next_button: int | None = None,
    variant: str = VARIANT_ULTIMATE,
) -> HUContinuationState:
    """Apply exact Fantasy/re-Fantasy qualification for both HU players."""
    t0 = transition_from_board(
        board0,
        current_fantasy_cards=current.p0_fantasy_cards,
        variant=variant,
    )
    t1 = transition_from_board(
        board1,
        current_fantasy_cards=current.p1_fantasy_cards,
        variant=variant,
    )
    button = (
        default_next_button(current.button)
        if next_button is None
        else int(next_button)
    )
    return HUContinuationState(
        button=button,
        p0_fantasy_cards=t0.next_cards,
        p1_fantasy_cards=t1.next_cards,
    )


def continuation_adjusted_terminal_utility(
    current: HUContinuationState,
    board0: Board,
    board1: Board,
    continuation_values: Mapping[HUContinuationState, float],
    *,
    update_player: int = 0,
    next_button: int | None = None,
    variant: str = VARIANT_ULTIMATE,
) -> float:
    """Exact one-step Bellman backup for a supplied continuation vector.

    This function is exact *conditional on* the provided continuation values.
    It does not certify those values. Values are always represented from player
    0's zero-sum perspective; player 1 receives the sign-reversed utility.
    """
    if update_player not in (0, 1):
        raise ValueError("HU player must be 0 or 1")
    nxt = next_state_from_terminal_boards(
        current,
        board0,
        board1,
        next_button=next_button,
        variant=variant,
    )
    if nxt not in continuation_values:
        raise KeyError(f"continuation value missing for {nxt.as_key()}")
    immediate_p0 = float(score_heads_up(board0, board1).points)
    total_p0 = immediate_p0 + float(continuation_values[nxt])
    return total_p0 if update_player == 0 else -total_p0


def zero_continuation_values() -> dict[HUContinuationState, float]:
    """Convenience baseline equivalent to current-hand-only utility."""
    return {state: 0.0 for state in all_states()}


def normalize_relative_values(
    raw_values: Mapping[HUContinuationState, float],
    *,
    reference: HUContinuationState | None = None,
) -> tuple[float, dict[HUContinuationState, float]]:
    """Normalize one full 50-state Bellman image for relative-value iteration.

    For an average-reward stochastic game the bias vector is defined only up to
    an additive constant. This helper performs only that algebraic normalization;
    it does not produce the Bellman image itself and therefore makes no
    convergence claim.
    """
    states = all_states()
    missing = [state for state in states if state not in raw_values]
    if missing:
        raise ValueError(
            f"relative-value image is incomplete: {len(missing)} states missing"
        )
    if reference is None:
        reference = HUContinuationState(0, NORMAL, NORMAL)
    if reference not in raw_values:
        raise ValueError("reference state missing from relative-value image")
    anchor = float(raw_values[reference])
    normalized = {
        state: float(raw_values[state]) - anchor
        for state in states
    }
    return anchor, normalized
