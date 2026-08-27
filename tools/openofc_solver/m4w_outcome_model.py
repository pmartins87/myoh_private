from __future__ import annotations

"""Own-information continuation-outcome model for sealed Fantasy/Fantasy HU.

M4V expresses every exact support action target as immediate utility plus a sparse
next-state distribution. M4W changes the learned object accordingly: instead of
learning a scalar Q tied to one continuation vector, it learns

  1. player-perspective immediate utility; and
  2. a probability distribution over the 25 next Fantasy-mode pairs.

At inference Q is reconstructed under the *current* 50-state continuation vector.
The model inputs remain exactly the M4P own-information state/action features;
opponent cards, opponent boards, complete worlds and payoff matrices are absent
from the policy API.

This is an engineering/generalization probe. It does not certify M4O support
robustness across continuation vectors or equilibrium quality.
"""

from dataclasses import dataclass
import inspect
import math
from itertools import product
from typing import Mapping, Sequence

from fantasy_fantasy_kernel import FantasyArrangement, FantasyFantasyWorld
from fantasy_fantasy_payoff import continuation_fingerprint
from fantasy_fantasy_policy_features import encode_policy_action, encode_policy_state
from fantasy_fantasy_policy_model import interaction_terms
from hu_continuation import HUContinuationState, HU_MODES
from m4v_continuation_targets import (
    ContinuationLinearTarget,
    ContinuationLinearTargetBatch,
)

AUTHORITY = "OWN_INFORMATION_CONTINUATION_OUTCOME_PROBE_NOT_EQUILIBRIUM"
OUTCOME_MODES = tuple(product(HU_MODES, HU_MODES))
OUTCOME_INDEX = {pair: index for index, pair in enumerate(OUTCOME_MODES)}
OUTCOME_COUNT = len(OUTCOME_MODES)
if OUTCOME_COUNT != 25:
    raise AssertionError("M4W requires 25 next Fantasy-mode pairs")
MASK64 = (1 << 64) - 1


def _mix64(value: int) -> int:
    x = value & MASK64
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & MASK64
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & MASK64
    x ^= x >> 31
    return x & MASK64


def _softmax(logits: Sequence[float]) -> tuple[float, ...]:
    if not logits or any(not math.isfinite(x) for x in logits):
        raise ValueError("outcome logits must be finite and non-empty")
    peak = max(logits)
    weights = [math.exp(x - peak) for x in logits]
    total = sum(weights)
    return tuple(x / total for x in weights)


def target_distribution(
    target: ContinuationLinearTarget,
    *,
    current_button: int,
) -> tuple[float, ...]:
    """Convert signed M4V coefficients into a positive 25-mode distribution."""
    if current_button not in (0, 1):
        raise ValueError("HU button must be 0 or 1")
    expected_next_button = 1 - current_button
    out = [0.0] * OUTCOME_COUNT
    sign = 1.0 if target.player == 0 else -1.0
    for state, coefficient in target.coefficients:
        if state.button != expected_next_button:
            raise ValueError("M4V next-state button violates HU alternation")
        probability = sign * float(coefficient)
        if probability < -1e-12:
            raise ValueError("M4V coefficient cannot form a probability target")
        pair = (state.p0_fantasy_cards, state.p1_fantasy_cards)
        out[OUTCOME_INDEX[pair]] += max(0.0, probability)
    total = sum(out)
    if abs(total - 1.0) > 1e-12:
        raise ValueError("M4W next-state target lost probability mass")
    return tuple(x / total for x in out)


def q_from_outcome(
    immediate: float,
    distribution: Sequence[float],
    *,
    current_meta: HUContinuationState,
    player: int,
    continuation_values: Mapping[HUContinuationState, float],
) -> float:
    """Reconstruct player-perspective Q from an outcome prediction and current V."""
    if player not in (0, 1):
        raise ValueError("HU player must be 0 or 1")
    if len(distribution) != OUTCOME_COUNT:
        raise ValueError("M4W outcome distribution has wrong dimension")
    probs = tuple(float(x) for x in distribution)
    if any(not math.isfinite(x) or x < 0.0 for x in probs):
        raise ValueError("M4W outcome probabilities must be finite/non-negative")
    total = sum(probs)
    if total <= 0.0:
        raise ValueError("M4W outcome distribution has zero mass")
    probs = tuple(x / total for x in probs)
    checked, _sha = continuation_fingerprint(continuation_values)
    next_button = 1 - current_meta.button
    expected_p0_continuation = 0.0
    for probability, (p0_mode, p1_mode) in zip(probs, OUTCOME_MODES):
        state = HUContinuationState(next_button, p0_mode, p1_mode)
        expected_p0_continuation += probability * float(checked[state])
    sign = 1.0 if player == 0 else -1.0
    return float(immediate + sign * expected_p0_continuation)


@dataclass(frozen=True)
class FantasyOutcomeExample:
    state_features: tuple[int, ...]
    action_features: tuple[int, ...]
    player: int
    current_button: int
    immediate_target: float
    next_mode_distribution: tuple[float, ...]
    weight: float = 1.0
    source: str = "m4v-exact-continuation-linear-target"

    def __post_init__(self) -> None:
        if self.player not in (0, 1) or self.current_button not in (0, 1):
            raise ValueError("invalid HU player/button in M4W example")
        if not math.isfinite(self.immediate_target):
            raise ValueError("M4W immediate target must be finite")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError("M4W example weight must be positive and finite")
        if len(self.next_mode_distribution) != OUTCOME_COUNT:
            raise ValueError("M4W outcome target has wrong dimension")
        if any(
            not math.isfinite(x) or x < 0.0
            for x in self.next_mode_distribution
        ):
            raise ValueError("M4W outcome target must be finite/non-negative")
        if abs(sum(self.next_mode_distribution) - 1.0) > 1e-12:
            raise ValueError("M4W outcome target must sum to one")

    def exact_q(
        self, continuation_values: Mapping[HUContinuationState, float]
    ) -> float:
        meta = _meta_from_state_features_contract(self)
        return q_from_outcome(
            self.immediate_target,
            self.next_mode_distribution,
            current_meta=meta,
            player=self.player,
            continuation_values=continuation_values,
        )


def _meta_from_state_features_contract(example: FantasyOutcomeExample) -> HUContinuationState:
    """Meta helper for exact-label tests; count values are not decoded from features.

    M4W examples carry button/player separately but Q reconstruction also needs the
    current Fantasy counts only for type validity. The next-state map depends on
    next button and predicted mode pair, not current counts, so F14/F14 is a safe
    structural placeholder here. Runtime calls always pass the real current_meta.
    """
    return HUContinuationState(example.current_button, 14, 14)


def build_outcome_examples(
    world: FantasyFantasyWorld,
    p0_support: Sequence[FantasyArrangement],
    p1_support: Sequence[FantasyArrangement],
    targets: ContinuationLinearTargetBatch,
    *,
    source: str = "m4w-exact-m4v-outcome",
) -> tuple[FantasyOutcomeExample, ...]:
    support0 = tuple(p0_support)
    support1 = tuple(p1_support)
    if len(support0) != len(targets.p0_targets) or len(support1) != len(targets.p1_targets):
        raise ValueError("M4W support/target cardinality mismatch")
    out: list[FantasyOutcomeExample] = []
    for player, support, rows in (
        (0, support0, targets.p0_targets),
        (1, support1, targets.p1_targets),
    ):
        packet = world.plan.packet_for(player)
        state_features = encode_policy_state(
            packet, current_meta=world.current_meta, player=player
        )
        for index, (arrangement, target) in enumerate(zip(support, rows)):
            if target.player != player or target.action_index != index:
                raise ValueError("M4W M4V target ordering mismatch")
            out.append(
                FantasyOutcomeExample(
                    state_features=state_features,
                    action_features=encode_policy_action(
                        packet,
                        arrangement,
                        current_meta=world.current_meta,
                        player=player,
                    ),
                    player=player,
                    current_button=world.current_meta.button,
                    immediate_target=float(target.immediate),
                    next_mode_distribution=target_distribution(
                        target, current_button=world.current_meta.button
                    ),
                    source=source,
                )
            )
    return tuple(out)


class SparseFantasyOutcomeModel:
    """Sparse immediate + categorical-next-state model over M4P own-info features."""

    def __init__(
        self,
        *,
        buckets: int = 1 << 14,
        learning_rate: float = 0.05,
        l2: float = 1e-6,
        huber_delta: float = 1.0,
        seed: int = 20260830,
    ) -> None:
        if buckets <= 0 or buckets & (buckets - 1):
            raise ValueError("M4W buckets must be a positive power of two")
        if learning_rate <= 0.0 or l2 < 0.0 or huber_delta <= 0.0:
            raise ValueError("invalid M4W hyperparameter")
        self.buckets = int(buckets)
        self.learning_rate = float(learning_rate)
        self.l2 = float(l2)
        self.huber_delta = float(huber_delta)
        self.seed = int(seed) & MASK64
        self.immediate_weights: dict[int, float] = {}
        self.immediate_grad_sq: dict[int, float] = {}
        self.outcome_weights: list[dict[int, float]] = [dict() for _ in range(OUTCOME_COUNT)]
        self.outcome_grad_sq: list[dict[int, float]] = [dict() for _ in range(OUTCOME_COUNT)]
        self.epochs_trained = 0
        self.updates = 0

    def _terms(self, state_features: Sequence[int], action_features: Sequence[int]):
        return interaction_terms(
            state_features, action_features, buckets=self.buckets
        )

    @staticmethod
    def _dot(weights: Mapping[int, float], terms: Sequence[tuple[int, float]]) -> float:
        return sum(float(weights.get(index, 0.0)) * value for index, value in terms)

    def predict_features(
        self,
        state_features: Sequence[int],
        action_features: Sequence[int],
    ) -> tuple[float, tuple[float, ...]]:
        terms = self._terms(state_features, action_features)
        immediate = self._dot(self.immediate_weights, terms)
        logits = tuple(self._dot(head, terms) for head in self.outcome_weights)
        return float(immediate), _softmax(logits)

    def predict_q_features(
        self,
        state_features: Sequence[int],
        action_features: Sequence[int],
        *,
        current_meta: HUContinuationState,
        player: int,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> float:
        immediate, distribution = self.predict_features(state_features, action_features)
        return q_from_outcome(
            immediate,
            distribution,
            current_meta=current_meta,
            player=player,
            continuation_values=continuation_values,
        )

    def policy_for_private_support(
        self,
        own_packet,
        support: Sequence[FantasyArrangement],
        *,
        current_meta: HUContinuationState,
        player: int,
        continuation_values: Mapping[HUContinuationState, float],
        temperature: float = 1.0,
    ) -> tuple[float, ...]:
        """Continuation-aware policy with no hidden-opponent/full-world input."""
        if not support or not math.isfinite(temperature) or temperature <= 0.0:
            raise ValueError("M4W policy requires support and positive temperature")
        state_features = encode_policy_state(
            tuple(own_packet), current_meta=current_meta, player=player
        )
        q_values = []
        for arrangement in support:
            action_features = encode_policy_action(
                tuple(own_packet),
                arrangement,
                current_meta=current_meta,
                player=player,
            )
            q_values.append(
                self.predict_q_features(
                    state_features,
                    action_features,
                    current_meta=current_meta,
                    player=player,
                    continuation_values=continuation_values,
                )
                / temperature
            )
        peak = max(q_values)
        weights = [math.exp(value - peak) for value in q_values]
        total = sum(weights)
        return tuple(value / total for value in weights)

    def update(self, example: FantasyOutcomeExample) -> tuple[float, float]:
        terms = self._terms(example.state_features, example.action_features)
        immediate_prediction = self._dot(self.immediate_weights, terms)
        error = immediate_prediction - example.immediate_target
        if abs(error) <= self.huber_delta:
            immediate_loss = 0.5 * error * error
            immediate_common = error
        else:
            immediate_loss = self.huber_delta * (abs(error) - 0.5 * self.huber_delta)
            immediate_common = self.huber_delta if error > 0.0 else -self.huber_delta
        immediate_common *= example.weight
        for index, value in terms:
            old = self.immediate_weights.get(index, 0.0)
            gradient = immediate_common * value + self.l2 * old
            accum = self.immediate_grad_sq.get(index, 0.0) + gradient * gradient
            self.immediate_grad_sq[index] = accum
            self.immediate_weights[index] = old - self.learning_rate * gradient / math.sqrt(accum + 1e-12)

        logits = tuple(self._dot(head, terms) for head in self.outcome_weights)
        probabilities = _softmax(logits)
        cross_entropy = -sum(
            target * math.log(max(1e-15, probability))
            for target, probability in zip(example.next_mode_distribution, probabilities)
            if target > 0.0
        )
        for head_index, (probability, target) in enumerate(
            zip(probabilities, example.next_mode_distribution)
        ):
            common = (probability - target) * example.weight
            weights = self.outcome_weights[head_index]
            grad_sq = self.outcome_grad_sq[head_index]
            for index, value in terms:
                old = weights.get(index, 0.0)
                gradient = common * value + self.l2 * old
                accum = grad_sq.get(index, 0.0) + gradient * gradient
                grad_sq[index] = accum
                weights[index] = old - self.learning_rate * gradient / math.sqrt(accum + 1e-12)

        self.updates += 1
        return float(immediate_loss * example.weight), float(cross_entropy * example.weight)

    def fit(
        self,
        examples: Sequence[FantasyOutcomeExample],
        *,
        epochs: int = 1,
    ) -> dict[str, float]:
        rows = tuple(examples)
        if not rows or epochs <= 0:
            raise ValueError("M4W fit requires examples and positive epochs")
        immediate_loss = outcome_loss = 0.0
        updates = 0
        for _ in range(epochs):
            epoch = self.epochs_trained
            order = list(range(len(rows)))
            order.sort(key=lambda i: _mix64(self.seed ^ (epoch << 32) ^ i))
            for index in order:
                a, b = self.update(rows[index])
                immediate_loss += a
                outcome_loss += b
                updates += 1
            self.epochs_trained += 1
        return {
            "mean_immediate_huber_loss": immediate_loss / updates,
            "mean_outcome_cross_entropy": outcome_loss / updates,
            "examples": float(updates),
            "epochs_trained": float(self.epochs_trained),
            "updates": float(self.updates),
        }

    def payload(self) -> dict:
        return {
            "authority": AUTHORITY,
            "buckets": self.buckets,
            "learning_rate": self.learning_rate,
            "l2": self.l2,
            "huber_delta": self.huber_delta,
            "seed": self.seed,
            "epochs_trained": self.epochs_trained,
            "updates": self.updates,
            "immediate_weights": sorted(self.immediate_weights.items()),
            "immediate_grad_sq": sorted(self.immediate_grad_sq.items()),
            "outcome_weights": [sorted(head.items()) for head in self.outcome_weights],
            "outcome_grad_sq": [sorted(head.items()) for head in self.outcome_grad_sq],
        }


def policy_api_has_hidden_opponent_argument() -> bool:
    names = inspect.signature(SparseFantasyOutcomeModel.policy_for_private_support).parameters
    forbidden = ("opponent", "world", "matrix", "hidden")
    return any(any(token in name for token in forbidden) for name in names)
