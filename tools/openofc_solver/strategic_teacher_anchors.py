from __future__ import annotations

"""Exact late-round anchors for the bounded strategic generalizer.

The global HU strategy is not tabularly tractable, but some late-round
information states admit a genuinely exact label that remains valid for *any*
cross-hand continuation vector.  In dealer/button R4 the opponent has already
completed a public 13-card board and Hero's three-card packet is private and
known.  `solve_r4_exact` can therefore exhaust every legal Hero action.

An R4 label is promoted from a current-hand diagnostic to a Bellman-safe teacher
only when every legal action produces the same Hero next-hand Fantasy mode.
The opponent terminal board and next button are already fixed, so the complete
next continuation state is then action-invariant.  Maximizing current points is
therefore exactly equivalent to maximizing

    current_points + V(next_state)

for *every possible* continuation vector V.  This avoids teaching the learned
model a heuristic Fantasy value or accidentally penalizing a strategically
correct point-for-Fantasy tradeoff.
"""

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence

from engine import Action
from strategic_advantage_model import (
    DeterministicReservoir,
    ReplayExample,
    SparseActionAdvantageModel,
)
from strategic_cfr import (
    HUState,
    PLAYER_DEALER,
    child_state,
    legal_action_pairs,
    sample_deal_plan,
)
from strategic_feature_encoder import (
    encode_canonical_action_key,
    encode_canonical_state_key,
)
from strategic_policy_distillation import is_holdout_key
from strategic_suit_symmetry import (
    action_key_under_suit_map,
    canonical_node_view,
)
from teacher_search import solve_r4_exact

ANCHOR_SCHEMA = "openofc-hu-exact-r4-anchor-v1"
AUTHORITY_CURRENT = "EXACT_R4_CURRENT_HAND"
AUTHORITY_INVARIANT = "EXACT_R4_ANY_CONTINUATION_WHEN_NEXT_STATE_INVARIANT"


@dataclass(frozen=True)
class ExactR4Anchor:
    key: str
    state_features: tuple[int, ...]
    action_keys: tuple[str, ...]
    action_features: tuple[tuple[int, ...], ...]
    points: tuple[int, ...]
    fantasy_cards: tuple[int, ...]
    best_points: int
    continuation_invariant: bool

    @property
    def optimal_indices(self) -> tuple[int, ...]:
        return tuple(i for i, value in enumerate(self.points) if value == self.best_points)

    @property
    def authority(self) -> str:
        return AUTHORITY_INVARIANT if self.continuation_invariant else AUTHORITY_CURRENT

    def payload(self) -> dict:
        return {
            "schema": ANCHOR_SCHEMA,
            "key": self.key,
            "actions": list(self.action_keys),
            "points": list(self.points),
            "fantasy_cards": list(self.fantasy_cards),
            "best_points": self.best_points,
            "optimal_indices": list(self.optimal_indices),
            "continuation_invariant": self.continuation_invariant,
            "authority": self.authority,
        }


def reachable_dealer_r4_state(seed: int) -> HUState:
    """Deterministically sample a legal dealer/button R4 information state.

    Earlier actions are sampled uniformly only to obtain varied reachable
    calibration states.  That reachability sampler is *not* part of the exact
    teacher claim: once the R4 information state is fixed, its terminal action
    values are exhaustively exact.
    """
    deal_rng = random.Random(int(seed))
    action_rng = random.Random(int(seed) ^ 0xA7C15D3E5B9F2041)
    state = HUState(plan=sample_deal_plan(deal_rng))
    while not (state.round_index == 4 and state.actor == PLAYER_DEALER):
        if state.terminal():
            raise AssertionError("dealer R4 target was skipped")
        pairs = legal_action_pairs(state)
        if not pairs:
            raise AssertionError("reachable pre-R4 state has no legal action")
        _key, action = pairs[action_rng.randrange(len(pairs))]
        state = child_state(state, action)
    if state.boards[0].count() != 13 or state.boards[1].count() != 11:
        raise AssertionError("dealer R4 state must see opponent=13 and self=11 cards")
    return state


def exact_r4_anchor(state: HUState) -> ExactR4Anchor:
    if state.terminal() or state.round_index != 4 or state.actor != PLAYER_DEALER:
        raise ValueError("exact R4 anchor requires dealer/button acting second on R4")
    incoming = state.plan.incoming(4, PLAYER_DEALER)
    oracle = solve_r4_exact(state.boards[1], state.boards[0], incoming)
    key, pairs, suit_map = canonical_node_view(state)
    ordered_keys = tuple(action_key for action_key, _ in pairs)
    by_key = {}
    for value in oracle.all_actions:
        action_key = action_key_under_suit_map(value.action, incoming, suit_map)
        if action_key in by_key:
            raise AssertionError("exact R4 canonical action collision")
        by_key[action_key] = value
    if set(by_key) != set(ordered_keys):
        raise AssertionError("exact R4 oracle/legal action surface mismatch")

    points = tuple(int(by_key[action_key].points) for action_key in ordered_keys)
    fantasy = tuple(int(by_key[action_key].fantasy_cards) for action_key in ordered_keys)
    if max(points) != oracle.best_points:
        raise AssertionError("exact R4 best-point mismatch")
    return ExactR4Anchor(
        key=key,
        state_features=encode_canonical_state_key(key),
        action_keys=ordered_keys,
        action_features=tuple(
            encode_canonical_action_key(action_key) for action_key in ordered_keys
        ),
        points=points,
        fantasy_cards=fantasy,
        best_points=int(oracle.best_points),
        continuation_invariant=len(set(fantasy)) == 1,
    )


def generate_exact_r4_anchors(base_seed: int, count: int) -> tuple[ExactR4Anchor, ...]:
    if count <= 0:
        raise ValueError("anchor count must be positive")
    return tuple(
        exact_r4_anchor(reachable_dealer_r4_state(int(base_seed) + i * 104729))
        for i in range(count)
    )


def add_invariant_r4_teachers(
    anchors: Iterable[ExactR4Anchor],
    replay: DeterministicReservoir,
    *,
    include_holdout: bool = False,
    weight: float = 4.0,
) -> dict[str, int]:
    """Add only Bellman-safe exact R4 labels to replay.

    Point-only R4 states whose actions change the next Fantasy mode are never
    admitted here.  They remain diagnostics until the continuation vector is
    solved.
    """
    if not math.isfinite(weight) or weight <= 0.0:
        raise ValueError("teacher weight must be positive and finite")
    states = 0
    actions = 0
    skipped_transition = 0
    skipped_holdout = 0
    for anchor in anchors:
        if not anchor.continuation_invariant:
            skipped_transition += 1
            continue
        if not include_holdout and is_holdout_key(anchor.key):
            skipped_holdout += 1
            continue
        optimal = set(anchor.optimal_indices)
        target = 1.0 / len(optimal)
        examples = [
            ReplayExample(
                state_features=anchor.state_features,
                action_features=features,
                target=target if index in optimal else 0.0,
                weight=weight,
                source="exact_r4_continuation_invariant",
            )
            for index, features in enumerate(anchor.action_features)
        ]
        replay.extend(examples)
        states += 1
        actions += len(examples)
    return {
        "states": states,
        "action_examples": actions,
        "skipped_transition_variant": skipped_transition,
        "skipped_holdout": skipped_holdout,
    }


@dataclass(frozen=True)
class ExactR4Metrics:
    states: int
    actions: int
    optimal_top1_accuracy: float
    mean_optimal_probability_mass: float
    mean_greedy_point_regret: float
    mean_expected_point_regret: float
    mean_uniform_point_regret: float

    def payload(self) -> dict:
        return {
            "states": self.states,
            "actions": self.actions,
            "optimal_top1_accuracy": self.optimal_top1_accuracy,
            "mean_optimal_probability_mass": self.mean_optimal_probability_mass,
            "mean_greedy_point_regret": self.mean_greedy_point_regret,
            "mean_expected_point_regret": self.mean_expected_point_regret,
            "mean_uniform_point_regret": self.mean_uniform_point_regret,
        }


def evaluate_exact_r4_anchors(
    model: SparseActionAdvantageModel,
    anchors: Sequence[ExactR4Anchor],
    *,
    holdout_only: bool = True,
    require_continuation_invariant: bool = True,
) -> ExactR4Metrics:
    states = 0
    actions = 0
    hits = 0
    optimal_mass = 0.0
    greedy_regret = 0.0
    expected_regret = 0.0
    uniform_regret = 0.0
    for anchor in anchors:
        if require_continuation_invariant and not anchor.continuation_invariant:
            continue
        if holdout_only != is_holdout_key(anchor.key):
            continue
        policy = model.policy(anchor.state_features, anchor.action_features)
        if len(policy) != len(anchor.points):
            raise AssertionError("R4 model/oracle action cardinality mismatch")
        optimal = set(anchor.optimal_indices)
        greedy = max(range(len(policy)), key=lambda i: (policy[i], -i))
        hits += int(greedy in optimal)
        optimal_mass += sum(policy[i] for i in optimal)
        greedy_regret += float(anchor.best_points - anchor.points[greedy])
        expected = sum(p * value for p, value in zip(policy, anchor.points))
        expected_regret += float(anchor.best_points) - expected
        uniform = sum(anchor.points) / len(anchor.points)
        uniform_regret += float(anchor.best_points) - uniform
        states += 1
        actions += len(anchor.points)
    if states == 0:
        raise ValueError("no exact R4 anchors available for requested evaluation split")
    return ExactR4Metrics(
        states=states,
        actions=actions,
        optimal_top1_accuracy=hits / states,
        mean_optimal_probability_mass=optimal_mass / states,
        mean_greedy_point_regret=greedy_regret / states,
        mean_expected_point_regret=expected_regret / states,
        mean_uniform_point_regret=uniform_regret / states,
    )
