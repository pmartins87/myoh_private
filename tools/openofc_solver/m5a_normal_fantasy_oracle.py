from __future__ import annotations

"""M5A fixed-policy value adapter for delayed Normal/Fantasy HU states.

This module deliberately evaluates a *frozen* visible-information normal-player
policy under an arbitrary current continuation vector. Fantasy terminal play is
resolved by the injected terminal evaluator (exact M4H by default). It is a
state-value/policy-evaluation adapter, not a Bellman-optimality certificate.

Common random numbers are used across continuation vectors: the chance/action
stream is derived from the policy snapshot and state, never from V. This makes
outer continuation comparisons materially less noisy while preserving exact
SHA binding of every returned value to the V actually scored.
"""

from dataclasses import dataclass
import hashlib
import inspect
import json
import math
import random
from typing import Mapping, Protocol, Sequence

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_FANTASY,
    hand_kernel_kind,
)
from m4z_outer_bellman import OneHandOracleResult
from normal_fantasy_kernel import (
    NormalFantasyState,
    child_normal_state,
    players_for_meta,
    sample_normal_fantasy_plan,
)
from normal_fantasy_policy_features import (
    encode_normal_fantasy_action_key,
    encode_normal_fantasy_state_key,
)
from normal_fantasy_symmetry import canonical_node_view
from normal_fantasy_terminal import (
    ExactOnePassNormalFantasyTerminalEvaluator,
    TerminalEvaluation,
)
from strategic_advantage_model import SparseActionAdvantageModel

SNAPSHOT_SCHEMA = "openofc-m5a-normal-fantasy-policy-snapshot-v1"
AUTHORITY = "FIXED_VISIBLE_POLICY_NORMAL_FANTASY_VALUE_NOT_BELLMAN_OPTIMAL"
MASK64 = (1 << 64) - 1


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def model_fingerprint(model: SparseActionAdvantageModel) -> str:
    return _sha(model.payload())


@dataclass(frozen=True)
class NormalFantasyPolicySnapshot:
    model_sha256: str
    training_continuation_sha256: str
    provenance: str
    sha256: str
    schema: str = SNAPSHOT_SCHEMA
    authority: str = AUTHORITY

    def __post_init__(self) -> None:
        if not _is_sha256(self.model_sha256) or not _is_sha256(
            self.training_continuation_sha256
        ):
            raise ValueError("M5A policy snapshot has invalid source SHA fields")
        if not str(self.provenance).strip():
            raise ValueError("M5A policy snapshot provenance must be non-empty")
        if self.schema != SNAPSHOT_SCHEMA or self.authority != AUTHORITY:
            raise ValueError("M5A policy snapshot schema/authority mismatch")
        expected = _sha(self.unsigned_payload())
        if self.sha256 != expected:
            raise ValueError("M5A policy snapshot SHA-256 mismatch")

    def unsigned_payload(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "authority": self.authority,
            "model_sha256": self.model_sha256,
            "training_continuation_sha256": self.training_continuation_sha256,
            "provenance": self.provenance,
        }


def freeze_policy_snapshot(
    model: SparseActionAdvantageModel,
    *,
    training_continuation_values: Mapping[HUContinuationState, float],
    provenance: str,
) -> NormalFantasyPolicySnapshot:
    if not str(provenance).strip():
        raise ValueError("M5A policy provenance must be non-empty")
    _checked, continuation_sha = continuation_fingerprint(
        training_continuation_values
    )
    model_sha = model_fingerprint(model)
    payload = {
        "schema": SNAPSHOT_SCHEMA,
        "authority": AUTHORITY,
        "model_sha256": model_sha,
        "training_continuation_sha256": continuation_sha,
        "provenance": str(provenance),
    }
    return NormalFantasyPolicySnapshot(
        model_sha256=model_sha,
        training_continuation_sha256=continuation_sha,
        provenance=str(provenance),
        sha256=_sha(payload),
    )


def policy_for_visible_node(
    model: SparseActionAdvantageModel,
    canonical_key: str,
    canonical_action_keys: Sequence[str],
) -> tuple[float, ...]:
    """Inference firewall: canonical visible key + public legal action keys only."""
    actions = tuple(canonical_action_keys)
    if not actions:
        raise ValueError("Normal/Fantasy policy requires legal actions")
    state_features = encode_normal_fantasy_state_key(canonical_key)
    action_features = [
        encode_normal_fantasy_action_key(key) for key in actions
    ]
    probabilities = tuple(
        float(x) for x in model.policy(state_features, action_features)
    )
    if len(probabilities) != len(actions):
        raise AssertionError("Normal/Fantasy model returned wrong policy cardinality")
    if any(not math.isfinite(x) or x < 0.0 for x in probabilities):
        raise ValueError("Normal/Fantasy model returned invalid probability")
    total = sum(probabilities)
    if total <= 0.0:
        raise ValueError("Normal/Fantasy model returned zero policy mass")
    return tuple(x / total for x in probabilities)


def policy_api_has_hidden_opponent_argument() -> bool:
    names = inspect.signature(policy_for_visible_node).parameters
    forbidden = ("opponent", "world", "hidden", "fantasy_packet", "plan")
    return any(any(token in name for token in forbidden) for name in names)


class TerminalEvaluator(Protocol):
    def evaluate(
        self,
        state: NormalFantasyState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> TerminalEvaluation: ...


def _sample_index(probabilities: Sequence[float], rng: random.Random) -> int:
    target = rng.random()
    cumulative = 0.0
    for index, probability in enumerate(probabilities):
        cumulative += float(probability)
        if target < cumulative:
            return index
    return len(probabilities) - 1


def _mean_standard_error(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("M5A state-value estimate requires samples")
    mean = sum(values) / len(values)
    if len(values) == 1:
        return float(mean), 0.0
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return float(mean), float(math.sqrt(max(0.0, variance) / len(values)))


class NormalFantasyFixedPolicyOracle:
    """M4Z-compatible Monte Carlo value adapter for one frozen normal policy."""

    authority = AUTHORITY

    def __init__(
        self,
        model: SparseActionAdvantageModel,
        snapshot: NormalFantasyPolicySnapshot,
        *,
        samples: int = 128,
        base_seed: int = 20260827,
        terminal_evaluator: TerminalEvaluator | None = None,
    ) -> None:
        if samples <= 0:
            raise ValueError("M5A oracle samples must be positive")
        if model_fingerprint(model) != snapshot.model_sha256:
            raise ValueError("M5A policy snapshot/model SHA mismatch")
        if not _is_sha256(snapshot.training_continuation_sha256) or not _is_sha256(
            snapshot.sha256
        ):
            raise ValueError("M5A policy snapshot has invalid SHA fields")
        self.model = model
        self.snapshot = snapshot
        self.samples = int(samples)
        self.base_seed = int(base_seed) & MASK64
        self.terminal_evaluator = (
            terminal_evaluator or ExactOnePassNormalFantasyTerminalEvaluator()
        )
        self.oracle_id = f"m5a-normal-fantasy-fixed-policy:{snapshot.sha256}"

    def _rng_for_state(self, state: HUContinuationState) -> random.Random:
        # V is intentionally absent: common random numbers across Bellman iterates.
        payload = f"{self.base_seed}|{self.oracle_id}|{state.as_key()}".encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        return random.Random(seed)

    def _rollout_one(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
        rng: random.Random,
    ) -> float:
        normal_player, fantasy_player = players_for_meta(state)
        fantasy_count = state.mode_for(fantasy_player)
        plan = sample_normal_fantasy_plan(rng, fantasy_count)
        node = NormalFantasyState(current_meta=state, plan=plan)
        while not node.terminal():
            key, pairs, _suit_map = canonical_node_view(node)
            action_keys = tuple(action_key for action_key, _action in pairs)
            probabilities = policy_for_visible_node(
                self.model, key, action_keys
            )
            selected = _sample_index(probabilities, rng)
            node = child_normal_state(node, pairs[selected][1])
        terminal = self.terminal_evaluator.evaluate(node, continuation_values)
        normal_value = float(terminal.utility_for_normal)
        return normal_value if normal_player == 0 else -normal_value

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult:
        if hand_kernel_kind(state) != KERNEL_NORMAL_FANTASY:
            raise ValueError("M5A Normal/Fantasy oracle received wrong kernel state")
        checked, continuation_sha = continuation_fingerprint(continuation_values)
        rng = self._rng_for_state(state)
        p0_samples = [
            self._rollout_one(state, checked, rng) for _ in range(self.samples)
        ]
        mean, standard_error = _mean_standard_error(p0_samples)
        return OneHandOracleResult(
            state=state,
            p0_value=mean,
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=self.samples,
            standard_error=standard_error,
        )
