from __future__ import annotations

"""Exact dealer/button R4 Bellman teacher for an explicit continuation vector.

Unlike the M4C3 continuation-invariant anchors, this oracle can label *every*
fully observed dealer R4 information state, including point-for-Fantasy trades.
Its authority is exact conditional on the supplied 50-state continuation vector.
It therefore becomes a production-quality teacher once the outer HU continuation
solve freezes V; until then it is a seam test and calibration oracle rather than
a claim that V itself is correct.
"""

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from engine import apply_action
from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_NORMAL,
    hand_kernel_kind,
    identity_for_role,
    next_state_from_terminal_boards,
)
from strategic_advantage_model import DeterministicReservoir, ReplayExample
from strategic_cfr import HUState, PLAYER_DEALER
from strategic_feature_encoder import encode_canonical_action_key, encode_canonical_state_key
from strategic_policy_distillation import is_holdout_key
from strategic_suit_symmetry import action_key_under_suit_map, canonical_node_view
from teacher_search import solve_r4_exact

AUTHORITY = "EXACT_DEALER_R4_GIVEN_CONTINUATION_VECTOR"


@dataclass(frozen=True)
class ContinuationR4Action:
    action_key: str
    immediate_points: int
    continuation_utility: float
    total_utility: float
    next_state: HUContinuationState
    fantasy_cards: int


@dataclass(frozen=True)
class ContinuationR4Result:
    key: str
    state_features: tuple[int, ...]
    action_features: tuple[tuple[int, ...], ...]
    actions: tuple[ContinuationR4Action, ...]
    best_utility: float
    optimal_indices: tuple[int, ...]
    hero_player: int
    authority: str = AUTHORITY


def solve_dealer_r4_given_continuation(
    state: HUState,
    *,
    current_meta: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
) -> ContinuationR4Result:
    if state.terminal() or state.round_index != 4 or state.actor != PLAYER_DEALER:
        raise ValueError("continuation R4 teacher requires dealer/button acting second on R4")
    if hand_kernel_kind(current_meta) != KERNEL_NORMAL_NORMAL:
        raise ValueError("continuation R4 teacher requires a normal/normal HU meta-state")
    if len(continuation_values) != 50:
        raise ValueError("continuation R4 teacher requires all 50 HU continuation values")
    if any(not math.isfinite(float(value)) for value in continuation_values.values()):
        raise ValueError("continuation vector contains non-finite value")

    hero_player = identity_for_role(current_meta, PLAYER_DEALER)
    if hero_player != current_meta.button:
        raise AssertionError("dealer relative role must map to current button identity")
    incoming = state.plan.incoming(4, PLAYER_DEALER)
    oracle = solve_r4_exact(state.boards[PLAYER_DEALER], state.boards[0], incoming)
    key, pairs, suit_map = canonical_node_view(state)
    ordered_keys = tuple(action_key for action_key, _ in pairs)

    by_key = {}
    for value in oracle.all_actions:
        action_key = action_key_under_suit_map(value.action, incoming, suit_map)
        dealer_final = apply_action(state.boards[PLAYER_DEALER], incoming, value.action)
        if hero_player == 0:
            persistent0, persistent1 = dealer_final, state.boards[0]
        else:
            persistent0, persistent1 = state.boards[0], dealer_final
        nxt = next_state_from_terminal_boards(
            current_meta, persistent0, persistent1
        )
        if nxt not in continuation_values:
            raise KeyError(f"continuation value missing for {nxt.as_key()}")
        persistent_p0 = float(continuation_values[nxt])
        hero_continuation = persistent_p0 if hero_player == 0 else -persistent_p0
        total = float(value.points) + hero_continuation
        by_key[action_key] = ContinuationR4Action(
            action_key=action_key,
            immediate_points=int(value.points),
            continuation_utility=hero_continuation,
            total_utility=total,
            next_state=nxt,
            fantasy_cards=int(value.fantasy_cards),
        )

    if set(by_key) != set(ordered_keys):
        raise AssertionError("continuation R4 action surface mismatch")
    actions = tuple(by_key[action_key] for action_key in ordered_keys)
    best = max(action.total_utility for action in actions)
    optimal = tuple(
        index for index, action in enumerate(actions)
        if abs(action.total_utility - best) <= 1e-12
    )
    return ContinuationR4Result(
        key=key,
        state_features=encode_canonical_state_key(key),
        action_features=tuple(
            encode_canonical_action_key(action_key) for action_key in ordered_keys
        ),
        actions=actions,
        best_utility=best,
        optimal_indices=optimal,
        hero_player=hero_player,
    )


def add_continuation_r4_teacher(
    result: ContinuationR4Result,
    replay: DeterministicReservoir,
    *,
    include_holdout: bool = False,
    weight: float = 4.0,
) -> dict[str, int]:
    if not math.isfinite(weight) or weight <= 0.0:
        raise ValueError("teacher weight must be positive and finite")
    if not include_holdout and is_holdout_key(result.key):
        return {"states": 0, "action_examples": 0, "skipped_holdout": 1}
    optimal = set(result.optimal_indices)
    target = 1.0 / len(optimal)
    replay.extend(
        ReplayExample(
            state_features=result.state_features,
            action_features=features,
            target=target if index in optimal else 0.0,
            weight=weight,
            source="exact_dealer_r4_given_continuation",
        )
        for index, features in enumerate(result.action_features)
    )
    return {
        "states": 1,
        "action_examples": len(result.action_features),
        "skipped_holdout": 0,
    }
