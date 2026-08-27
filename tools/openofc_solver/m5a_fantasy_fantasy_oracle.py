from __future__ import annotations

"""M5A continuation-aware fixed-model value adapter for Fantasy/Fantasy HU.

M4W predicts continuation-independent immediate utility and next-mode outcomes;
M4X supplies a robust union support over a declared continuation region. This
adapter combines them into an M4Z-compatible one-hand value oracle while keeping
both sealed players' inference surfaces private.

The adapter fails closed when the current continuation vector leaves the frozen
M4X family region. It is still a fitted-policy evaluator, not an equilibrium or
Bellman-optimality certificate.
"""

from dataclasses import dataclass
import hashlib
import json
import math
import random
from typing import Mapping, Sequence

from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    sample_fantasy_fantasy_plan,
    terminal_utility,
)
from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    hand_kernel_kind,
)
from m4w_outcome_model import SparseFantasyOutcomeModel
from m4x_robust_support import (
    ContinuationFamily,
    continuation_region_membership,
    generate_robust_union_support,
)
from m4z_outer_bellman import OneHandOracleResult

SNAPSHOT_SCHEMA = "openofc-m5a-fantasy-fantasy-policy-snapshot-v1"
AUTHORITY = "M4W_M4X_SEALED_FIXED_MODEL_VALUE_NOT_EQUILIBRIUM"
MASK64 = (1 << 64) - 1


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def model_fingerprint(model: SparseFantasyOutcomeModel) -> str:
    return _sha(model.payload())


@dataclass(frozen=True)
class FantasyFantasyPolicySnapshot:
    model_sha256: str
    family_sha256: str
    synthetic_worlds_per_anchor: int
    max_candidates_per_anchor: int
    proposal_base_seed: int
    temperature: float
    provenance: str
    sha256: str
    schema: str = SNAPSHOT_SCHEMA
    authority: str = AUTHORITY

    def __post_init__(self) -> None:
        if len(self.model_sha256) != 64 or len(self.family_sha256) != 64:
            raise ValueError("M5A Fantasy/Fantasy snapshot SHA fields are invalid")
        try:
            int(self.model_sha256, 16)
            int(self.family_sha256, 16)
        except ValueError as exc:
            raise ValueError(
                "M5A Fantasy/Fantasy snapshot SHA fields are invalid"
            ) from exc
        if (
            self.synthetic_worlds_per_anchor <= 0
            or self.max_candidates_per_anchor <= 0
        ):
            raise ValueError("M5A Fantasy/Fantasy support budgets must be positive")
        if not math.isfinite(self.temperature) or self.temperature <= 0.0:
            raise ValueError("M5A Fantasy/Fantasy temperature must be positive")
        if not str(self.provenance).strip():
            raise ValueError("M5A Fantasy/Fantasy provenance must be non-empty")
        if self.schema != SNAPSHOT_SCHEMA or self.authority != AUTHORITY:
            raise ValueError("M5A Fantasy/Fantasy snapshot schema/authority mismatch")
        if self.sha256 != _sha(self.unsigned_payload()):
            raise ValueError("M5A Fantasy/Fantasy snapshot SHA mismatch")

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority": self.authority,
            "model_sha256": self.model_sha256,
            "family_sha256": self.family_sha256,
            "synthetic_worlds_per_anchor": self.synthetic_worlds_per_anchor,
            "max_candidates_per_anchor": self.max_candidates_per_anchor,
            "proposal_base_seed": self.proposal_base_seed,
            "temperature": self.temperature,
            "provenance": self.provenance,
        }


def freeze_policy_snapshot(
    model: SparseFantasyOutcomeModel,
    family: ContinuationFamily,
    *,
    synthetic_worlds_per_anchor: int = 8,
    max_candidates_per_anchor: int = 32,
    proposal_base_seed: int = 20260827,
    temperature: float = 1.0,
    provenance: str,
) -> FantasyFantasyPolicySnapshot:
    payload: dict[str, object] = {
        "schema": SNAPSHOT_SCHEMA,
        "authority": AUTHORITY,
        "model_sha256": model_fingerprint(model),
        "family_sha256": family.sha256,
        "synthetic_worlds_per_anchor": int(synthetic_worlds_per_anchor),
        "max_candidates_per_anchor": int(max_candidates_per_anchor),
        "proposal_base_seed": int(proposal_base_seed),
        "temperature": float(temperature),
        "provenance": str(provenance),
    }
    return FantasyFantasyPolicySnapshot(
        model_sha256=str(payload["model_sha256"]),
        family_sha256=str(payload["family_sha256"]),
        synthetic_worlds_per_anchor=int(synthetic_worlds_per_anchor),
        max_candidates_per_anchor=int(max_candidates_per_anchor),
        proposal_base_seed=int(proposal_base_seed),
        temperature=float(temperature),
        provenance=str(provenance),
        sha256=_sha(payload),
    )


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


class FantasyFantasyFixedModelOracle:
    authority = AUTHORITY

    def __init__(
        self,
        model: SparseFantasyOutcomeModel,
        family: ContinuationFamily,
        snapshot: FantasyFantasyPolicySnapshot,
        *,
        samples: int = 32,
        base_seed: int = 20260827,
    ) -> None:
        if samples <= 0:
            raise ValueError("M5A Fantasy/Fantasy samples must be positive")
        if model_fingerprint(model) != snapshot.model_sha256:
            raise ValueError("M5A Fantasy/Fantasy model/snapshot SHA mismatch")
        if family.sha256 != snapshot.family_sha256:
            raise ValueError("M5A Fantasy/Fantasy family/snapshot SHA mismatch")
        self.model = model
        self.family = family
        self.snapshot = snapshot
        self.samples = int(samples)
        self.base_seed = int(base_seed) & MASK64
        self.oracle_id = f"m5a-fantasy-fantasy-fixed-model:{snapshot.sha256}"

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
        world = FantasyFantasyWorld(
            current_meta=state,
            plan=sample_fantasy_fantasy_plan(rng, state),
        )
        arrangements = []
        for player in (0, 1):
            packet = world.plan.packet_for(player)
            support = generate_robust_union_support(
                packet,
                current_meta=state,
                player=player,
                family=self.family,
                synthetic_worlds_per_anchor=(
                    self.snapshot.synthetic_worlds_per_anchor
                ),
                max_candidates_per_anchor=(
                    self.snapshot.max_candidates_per_anchor
                ),
                base_seed=self.snapshot.proposal_base_seed,
            )
            probabilities = self.model.policy_for_private_support(
                packet,
                support.candidates,
                current_meta=state,
                player=player,
                continuation_values=continuation_values,
                temperature=self.snapshot.temperature,
            )
            selected = _sample_index(probabilities, rng)
            arrangements.append(support.candidates[selected])
        return float(
            terminal_utility(
                world,
                arrangements[0],
                arrangements[1],
                continuation_values,
                update_player=0,
            )
        )

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult:
        if hand_kernel_kind(state) != KERNEL_FANTASY_FANTASY:
            raise ValueError("M5A Fantasy/Fantasy oracle received wrong kernel state")
        checked, continuation_sha = continuation_fingerprint(continuation_values)
        membership = continuation_region_membership(self.family, checked)
        if not membership.inside:
            raise RuntimeError(
                "M5A Fantasy/Fantasy continuation escaped M4X certified support region"
            )
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
