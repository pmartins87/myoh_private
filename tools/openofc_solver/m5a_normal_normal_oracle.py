from __future__ import annotations

"""M5A fixed-policy value adapter for the two Normal/Normal HU states.

The policy surface is the existing exact suit24 visible information key plus its
public legal actions. A frozen distilled policy is evaluated under arbitrary
current continuation values with common random numbers. This is policy
evaluation, not a claim that the policy is the Bellman best response at every V.
"""

from dataclasses import dataclass
import hashlib
import inspect
import json
import math
import random
from typing import Mapping, Sequence

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_NORMAL,
    continuation_adjusted_terminal_utility,
    hand_kernel_kind,
    identity_for_role,
)
from m4z_outer_bellman import OneHandOracleResult
from strategic_advantage_model import SparseActionAdvantageModel
from strategic_cfr import HUState, child_state, sample_deal_plan
from strategic_feature_encoder import (
    encode_canonical_action_key,
    encode_canonical_state_key,
)
from strategic_suit_symmetry import canonical_node_view

SNAPSHOT_SCHEMA = "openofc-m5a-normal-normal-policy-snapshot-v1"
AUTHORITY = "FIXED_VISIBLE_POLICY_NORMAL_NORMAL_VALUE_NOT_BELLMAN_OPTIMAL"
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
class NormalNormalPolicySnapshot:
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
            raise ValueError("M5A normal/normal snapshot has invalid source SHA")
        if not str(self.provenance).strip():
            raise ValueError("M5A normal/normal provenance must be non-empty")
        if self.schema != SNAPSHOT_SCHEMA or self.authority != AUTHORITY:
            raise ValueError("M5A normal/normal snapshot schema/authority mismatch")
        if self.sha256 != _sha(self.unsigned_payload()):
            raise ValueError("M5A normal/normal snapshot SHA mismatch")

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
) -> NormalNormalPolicySnapshot:
    if not str(provenance).strip():
        raise ValueError("M5A normal/normal provenance must be non-empty")
    _checked, continuation_sha = continuation_fingerprint(
        training_continuation_values
    )
    payload = {
        "schema": SNAPSHOT_SCHEMA,
        "authority": AUTHORITY,
        "model_sha256": model_fingerprint(model),
        "training_continuation_sha256": continuation_sha,
        "provenance": str(provenance),
    }
    return NormalNormalPolicySnapshot(
        model_sha256=str(payload["model_sha256"]),
        training_continuation_sha256=continuation_sha,
        provenance=str(provenance),
        sha256=_sha(payload),
    )


def policy_for_visible_node(
    model: SparseActionAdvantageModel,
    canonical_key: str,
    canonical_action_keys: Sequence[str],
) -> tuple[float, ...]:
    actions = tuple(canonical_action_keys)
    if not actions:
        raise ValueError("normal/normal policy requires legal actions")
    state_features = encode_canonical_state_key(canonical_key)
    action_features = [encode_canonical_action_key(key) for key in actions]
    probabilities = tuple(
        float(x) for x in model.policy(state_features, action_features)
    )
    if len(probabilities) != len(actions):
        raise AssertionError("normal/normal model returned wrong policy cardinality")
    if any(not math.isfinite(x) or x < 0.0 for x in probabilities):
        raise ValueError("normal/normal model returned invalid probability")
    total = sum(probabilities)
    if total <= 0.0:
        raise ValueError("normal/normal model returned zero policy mass")
    return tuple(x / total for x in probabilities)


def policy_api_has_hidden_opponent_argument() -> bool:
    names = inspect.signature(policy_for_visible_node).parameters
    forbidden = ("opponent_packet", "world", "hidden", "plan", "deal")
    return any(any(token in name for token in forbidden) for name in names)


def _sample_index(probabilities: Sequence[float], rng: random.Random) -> int:
    target = rng.random()
    cumulative = 0.0
    for index, probability in enumerate(probabilities):
        cumulative += float(probability)
        if target < cumulative:
            return index
    return len(probabilities) - 1


def _mean_standard_error(values: Sequence[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    if len(values) == 1:
        return float(mean), 0.0
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return float(mean), float(math.sqrt(max(0.0, variance) / len(values)))


class NormalNormalFixedPolicyOracle:
    authority = AUTHORITY

    def __init__(
        self,
        model: SparseActionAdvantageModel,
        snapshot: NormalNormalPolicySnapshot,
        *,
        samples: int = 512,
        base_seed: int = 20260827,
    ) -> None:
        if samples <= 0:
            raise ValueError("M5A normal/normal samples must be positive")
        if model_fingerprint(model) != snapshot.model_sha256:
            raise ValueError("M5A normal/normal model/snapshot SHA mismatch")
        self.model = model
        self.snapshot = snapshot
        self.samples = int(samples)
        self.base_seed = int(base_seed) & MASK64
        self.oracle_id = f"m5a-normal-normal-fixed-policy:{snapshot.sha256}"

    def _rng_for_state(self, state: HUContinuationState) -> random.Random:
        payload = f"{self.base_seed}|{self.oracle_id}|{state.as_key()}".encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        return random.Random(seed)

    def _rollout_one(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
        rng: random.Random,
    ) -> float:
        node = HUState(plan=sample_deal_plan(rng))
        while not node.terminal():
            key, pairs, _suit_map = canonical_node_view(node)
            action_keys = tuple(action_key for action_key, _action in pairs)
            probabilities = policy_for_visible_node(self.model, key, action_keys)
            selected = _sample_index(probabilities, rng)
            node = child_state(node, pairs[selected][1])

        persistent_boards = [None, None]
        for role in (0, 1):
            persistent = identity_for_role(state, role)
            persistent_boards[persistent] = node.boards[role]
        if persistent_boards[0] is None or persistent_boards[1] is None:
            raise AssertionError("normal/normal persistent board remap failed")
        return float(
            continuation_adjusted_terminal_utility(
                state,
                persistent_boards[0],
                persistent_boards[1],
                continuation_values,
                update_player=0,
            )
        )

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult:
        if hand_kernel_kind(state) != KERNEL_NORMAL_NORMAL:
            raise ValueError("M5A normal/normal oracle received wrong kernel state")
        checked, continuation_sha = continuation_fingerprint(continuation_values)
        rng = self._rng_for_state(state)
        values = [
            self._rollout_one(state, checked, rng) for _ in range(self.samples)
        ]
        mean, standard_error = _mean_standard_error(values)
        return OneHandOracleResult(
            state=state,
            p0_value=mean,
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=self.samples,
            standard_error=standard_error,
        )
