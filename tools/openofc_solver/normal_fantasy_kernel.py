from __future__ import annotations

"""HU one-hand kernel for exactly one normal player and one Fantasy player.

Under the explicit delayed-response timing model supported by field replays, the
Fantasy player can keep the arrangement unconfirmed while the normal player
completes all five placement rounds.  The normal player therefore receives no
public card signal from the hidden Fantasy packet during the hand.  Once the
normal board is complete, the Fantasy player uses the exact M4D response
frontier.

This file defines the exact game/plumbing boundary. It does not yet claim a
solved normal-player policy.  Its terminal utility is exact conditional on the
supplied continuation vector and the delayed-response timing contract.
"""

from dataclasses import dataclass
import json
import random
from typing import Mapping, Sequence

from engine import Action, Board, Card, apply_action, full_deck, legal_actions
from fantasy_response_frontier import (
    FantasyResponseFrontier,
    build_fantasy_response_frontier,
    evaluate_fantasy_response_frontier,
)
from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_FANTASY,
    hand_kernel_kind,
)

AUTHORITY = "EXACT_NORMAL_FANTASY_HAND_MODEL_GIVEN_V_AND_DELAYED_TIMING"
ROUND_TERMINAL = 5


@dataclass(frozen=True)
class NormalFantasyDealPlan:
    fantasy_packet: tuple[Card, ...]
    normal_opening: tuple[Card, ...]
    normal_rounds: tuple[
        tuple[Card, ...],
        tuple[Card, ...],
        tuple[Card, ...],
        tuple[Card, ...],
    ]

    def normal_incoming(self, round_index: int) -> tuple[Card, ...]:
        if round_index == 0:
            return self.normal_opening
        if 1 <= round_index <= 4:
            return self.normal_rounds[round_index - 1]
        raise ValueError("normal/Fantasy round must be 0..4")

    def all_cards(self) -> tuple[Card, ...]:
        out = list(self.fantasy_packet)
        out.extend(self.normal_opening)
        for packet in self.normal_rounds:
            out.extend(packet)
        return tuple(out)


def sample_normal_fantasy_plan(
    rng: random.Random,
    fantasy_count: int,
) -> NormalFantasyDealPlan:
    if fantasy_count not in (14, 15, 16, 17):
        raise ValueError("Fantasy count must be 14..17")
    deck = list(full_deck(2))
    rng.shuffle(deck)
    cursor = 0

    def draw(count: int) -> tuple[Card, ...]:
        nonlocal cursor
        result = tuple(sorted(deck[cursor:cursor + count]))
        cursor += count
        return result

    fantasy = draw(fantasy_count)
    opening = draw(5)
    rounds = tuple(draw(3) for _ in range(4))
    plan = NormalFantasyDealPlan(fantasy, opening, rounds)  # type: ignore[arg-type]
    cards = plan.all_cards()
    if len(cards) != fantasy_count + 17 or len(set(cards)) != len(cards):
        raise AssertionError("asymmetric HU deal must contain unique physical cards")
    return plan


def players_for_meta(current_meta: HUContinuationState) -> tuple[int, int]:
    if hand_kernel_kind(current_meta) != KERNEL_NORMAL_FANTASY:
        raise ValueError("normal/Fantasy kernel requires exactly one Fantasy player")
    if current_meta.p0_fantasy_cards > 0:
        return 1, 0  # normal, fantasy
    return 0, 1


@dataclass(frozen=True)
class NormalFantasyState:
    current_meta: HUContinuationState
    plan: NormalFantasyDealPlan
    round_index: int = 0
    normal_board: Board = Board()
    normal_discards: tuple[Card, ...] = ()

    def __post_init__(self) -> None:
        normal_player, fantasy_player = players_for_meta(self.current_meta)
        expected = self.current_meta.mode_for(fantasy_player)
        if len(self.plan.fantasy_packet) != expected:
            raise ValueError("deal Fantasy packet count does not match meta-state")
        if self.current_meta.mode_for(normal_player) != 0:
            raise AssertionError("normal-player mode mismatch")
        cards = self.plan.all_cards()
        if len(set(cards)) != len(cards):
            raise ValueError("normal/Fantasy plan contains duplicate physical card")
        if self.round_index not in range(ROUND_TERMINAL + 1):
            raise ValueError("normal/Fantasy round outside 0..5")

    @property
    def normal_player(self) -> int:
        return players_for_meta(self.current_meta)[0]

    @property
    def fantasy_player(self) -> int:
        return players_for_meta(self.current_meta)[1]

    def terminal(self) -> bool:
        return self.round_index == ROUND_TERMINAL

    def incoming(self) -> tuple[Card, ...]:
        if self.terminal():
            raise ValueError("terminal asymmetric state has no incoming packet")
        return self.plan.normal_incoming(self.round_index)


def legal_normal_actions(state: NormalFantasyState) -> list[Action]:
    if state.terminal():
        return []
    return legal_actions(state.normal_board, state.incoming(), state.round_index)


def child_normal_state(state: NormalFantasyState, action: Action) -> NormalFantasyState:
    if state.terminal():
        raise ValueError("cannot act in terminal normal/Fantasy state")
    incoming = state.incoming()
    board = apply_action(state.normal_board, incoming, action)
    discards = state.normal_discards
    if action.discard_index is not None:
        discards = discards + (incoming[action.discard_index],)
    result = NormalFantasyState(
        current_meta=state.current_meta,
        plan=state.plan,
        round_index=state.round_index + 1,
        normal_board=board,
        normal_discards=discards,
    )
    if result.terminal():
        if not result.normal_board.complete() or len(result.normal_discards) != 4:
            raise AssertionError("terminal normal player must have 13 placed + 4 discarded")
    return result


def information_state_key(state: NormalFantasyState) -> str:
    """Exact normal-player information key under delayed hidden Fantasy play.

    The opponent Fantasy packet is intentionally absent.  Since the Fantasy
    player emits no public placements before normal completion in this timing
    model, the normal player has no opponent-action history to condition on.
    Own board + own remembered discards contains all previously observed normal
    cards, so no strategic memory is discarded.
    """
    if state.terminal():
        raise ValueError("terminal asymmetric state has no decision information key")
    payload = {
        "v": 1,
        "kernel": "normal-vs-hidden-fantasy-delayed",
        "normal_player": state.normal_player,
        "fantasy_player": state.fantasy_player,
        "button": state.current_meta.button,
        "fantasy_count": len(state.plan.fantasy_packet),
        "round": state.round_index,
        "normal_board": tuple(
            tuple(sorted(str(card) for card in row))
            for row in state.normal_board.rows()
        ),
        "own_discards": tuple(sorted(str(card) for card in state.normal_discards)),
        "incoming": tuple(sorted(str(card) for card in state.incoming())),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def exact_terminal_frontier(state: NormalFantasyState) -> FantasyResponseFrontier:
    if not state.terminal():
        raise ValueError("terminal frontier requires completed normal/Fantasy state")
    return build_fantasy_response_frontier(
        state.plan.fantasy_packet,
        state.normal_board,
        current_state=state.current_meta,
        hero_player=state.fantasy_player,
    )


def exact_terminal_utility_for_normal(
    state: NormalFantasyState,
    continuation_values: Mapping[HUContinuationState, float],
    *,
    frontier: FantasyResponseFrontier | None = None,
) -> float:
    """Return exact utility from the normal player's perspective.

    The M4D frontier is scored from the Fantasy player's perspective. HU scoring
    plus continuation is zero-sum, so the normal player's value is its negation.
    """
    if not state.terminal():
        raise ValueError("terminal utility requires completed normal/Fantasy state")
    if frontier is None:
        frontier = exact_terminal_frontier(state)
    if frontier.hero_player != state.fantasy_player:
        raise ValueError("frontier belongs to wrong Fantasy player")
    evaluated = evaluate_fantasy_response_frontier(frontier, continuation_values)
    return -float(evaluated.utility)
