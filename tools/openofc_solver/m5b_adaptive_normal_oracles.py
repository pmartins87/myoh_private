from __future__ import annotations

"""Train-at-current-V policy-improvement probes for normal-hand kernels.

M5A fixed-policy adapters are valid policy evaluators but cannot be called a
Bellman strategic operator when V changes. M5B closes part of that semantic gap:
for every evaluate(state, V) call it trains the existing continuation-coupled
one-hand solver at that exact V, distills visited tabular information sets into
the bounded visible-information generalizer, and evaluates that freshly trained
policy on independent Monte Carlo rollouts.

The procedure is deterministic for fixed configuration/state/V and keeps common
solver/evaluation seeds across V. Finite training plus function approximation
still requires held-out deviation/exploitability certification; authority stays
PROBE_NOT_CERTIFIED.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    hand_kernel_kind,
)
from m4z_outer_bellman import OneHandOracleResult
from m5a_normal_fantasy_oracle import (
    NormalFantasyFixedPolicyOracle,
    freeze_policy_snapshot as freeze_nf_snapshot,
)
from m5a_normal_normal_oracle import (
    NormalNormalFixedPolicyOracle,
    freeze_policy_snapshot as freeze_nn_snapshot,
)
from normal_fantasy_cfr import NormalFantasyOutcomeSampling
from normal_fantasy_policy_distillation import (
    distill_normal_fantasy_solver_nodes,
)
from normal_fantasy_terminal import ExactOnePassNormalFantasyTerminalEvaluator
from strategic_advantage_model import (
    DeterministicReservoir,
    SparseActionAdvantageModel,
)
from strategic_continuation_cfr import (
    ContinuationObjective,
    SuitCanonicalContinuationMCCFR,
)
from strategic_policy_distillation import distill_solver_nodes

AUTHORITY_NN = "TRAIN_AT_CURRENT_V_NORMAL_NORMAL_PROBE_NOT_CERTIFIED"
AUTHORITY_NF = "TRAIN_AT_CURRENT_V_NORMAL_FANTASY_PROBE_NOT_CERTIFIED"
CONFIG_SCHEMA = "openofc-m5b-adaptive-normal-config-v1"
MASK64 = (1 << 64) - 1


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _state_seed(
    base_seed: int, namespace: str, state: HUContinuationState
) -> int:
    raw = f"{int(base_seed) & MASK64}|{namespace}|{state.as_key()}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


@dataclass(frozen=True)
class AdaptiveNormalConfig:
    training_iterations: int = 1000
    evaluation_samples: int = 512
    replay_capacity: int = 200000
    fit_epochs: int = 2
    model_buckets: int = 1 << 16
    learning_rate: float = 0.08
    l2: float = 1e-6
    huber_delta: float = 1.0
    epsilon: float = 0.6
    base_seed: int = 20260827

    def __post_init__(self) -> None:
        if min(
            self.training_iterations,
            self.evaluation_samples,
            self.replay_capacity,
            self.fit_epochs,
            self.model_buckets,
        ) <= 0:
            raise ValueError("M5B adaptive normal budgets must be positive")
        if self.model_buckets & (self.model_buckets - 1):
            raise ValueError("M5B model_buckets must be a power of two")
        if (
            self.learning_rate <= 0.0
            or self.l2 < 0.0
            or self.huber_delta <= 0.0
        ):
            raise ValueError("M5B adaptive model hyperparameters are invalid")
        if not 0.0 < self.epsilon <= 1.0:
            raise ValueError("M5B adaptive epsilon must be in (0,1]")

    def payload(self) -> dict[str, object]:
        return {
            "schema": CONFIG_SCHEMA,
            "training_iterations": self.training_iterations,
            "evaluation_samples": self.evaluation_samples,
            "replay_capacity": self.replay_capacity,
            "fit_epochs": self.fit_epochs,
            "model_buckets": self.model_buckets,
            "learning_rate": self.learning_rate,
            "l2": self.l2,
            "huber_delta": self.huber_delta,
            "epsilon": self.epsilon,
            "base_seed": int(self.base_seed) & MASK64,
        }

    @property
    def sha256(self) -> str:
        return _sha(self.payload())


@dataclass(frozen=True)
class AdaptiveNormalSolveReport:
    state: str
    continuation_sha256: str
    training_iterations: int
    solver_infosets: int
    distilled_nodes: int
    action_examples: int
    mean_huber_loss: float
    policy_snapshot_sha256: str
    p0_value: float
    standard_error: float
    authority: str


def _new_model(
    config: AdaptiveNormalConfig, *, seed: int
) -> SparseActionAdvantageModel:
    return SparseActionAdvantageModel(
        buckets=config.model_buckets,
        learning_rate=config.learning_rate,
        l2=config.l2,
        huber_delta=config.huber_delta,
        seed=seed,
    )


class AdaptiveNormalNormalOracle:
    authority = AUTHORITY_NN

    def __init__(
        self, config: AdaptiveNormalConfig = AdaptiveNormalConfig()
    ) -> None:
        self.config = config
        self.oracle_id = f"m5b-adaptive-normal-normal:{config.sha256}"
        self.last_report: AdaptiveNormalSolveReport | None = None

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult:
        if hand_kernel_kind(state) != KERNEL_NORMAL_NORMAL:
            raise ValueError(
                "M5B adaptive normal/normal oracle received wrong kernel"
            )
        checked, continuation_sha = continuation_fingerprint(continuation_values)
        solver_seed = _state_seed(
            self.config.base_seed, "m5b-nn-solver", state
        )
        solver = SuitCanonicalContinuationMCCFR(
            objective=ContinuationObjective(state, checked),
            epsilon=self.config.epsilon,
            seed=solver_seed,
            cfr_plus=True,
        )
        stats = solver.run(self.config.training_iterations)

        replay = DeterministicReservoir(
            capacity=self.config.replay_capacity,
            seed=_state_seed(self.config.base_seed, "m5b-nn-replay", state),
        )
        distilled = distill_solver_nodes(
            solver, replay, include_holdout=False
        )
        if not replay.items:
            raise RuntimeError(
                "M5B normal/normal training produced no distillation examples"
            )
        model = _new_model(
            self.config,
            seed=_state_seed(self.config.base_seed, "m5b-nn-model", state),
        )
        fit = model.fit(replay, epochs=self.config.fit_epochs)
        snapshot = freeze_nn_snapshot(
            model,
            training_continuation_values=checked,
            provenance=f"{self.oracle_id}|{continuation_sha}",
        )
        fixed = NormalNormalFixedPolicyOracle(
            model,
            snapshot,
            samples=self.config.evaluation_samples,
            base_seed=_state_seed(self.config.base_seed, "m5b-nn-eval", state),
        )
        value = fixed.evaluate(state, checked)
        result = OneHandOracleResult(
            state=state,
            p0_value=value.p0_value,
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=value.samples,
            standard_error=value.standard_error,
        )
        self.last_report = AdaptiveNormalSolveReport(
            state=state.as_key(),
            continuation_sha256=continuation_sha,
            training_iterations=self.config.training_iterations,
            solver_infosets=int(stats.infosets),
            distilled_nodes=int(distilled["nodes"]),
            action_examples=int(distilled["action_examples"]),
            mean_huber_loss=float(fit["mean_huber_loss"]),
            policy_snapshot_sha256=snapshot.sha256,
            p0_value=result.p0_value,
            standard_error=result.standard_error,
            authority=self.authority,
        )
        return result


class AdaptiveNormalFantasyOracle:
    authority = AUTHORITY_NF

    def __init__(
        self,
        config: AdaptiveNormalConfig = AdaptiveNormalConfig(),
        *,
        terminal_evaluator=None,
        terminal_evaluator_id: str | None = None,
    ) -> None:
        self.config = config
        self.terminal_evaluator = (
            terminal_evaluator or ExactOnePassNormalFantasyTerminalEvaluator()
        )
        terminal_id = terminal_evaluator_id or str(
            getattr(
                self.terminal_evaluator,
                "authority",
                "UNIDENTIFIED_TERMINAL_EVALUATOR",
            )
        )
        if not terminal_id.strip():
            raise ValueError("M5B terminal evaluator id must be non-empty")
        identity = {
            "config_sha256": config.sha256,
            "terminal_evaluator_id": terminal_id,
        }
        self.oracle_id = f"m5b-adaptive-normal-fantasy:{_sha(identity)}"
        self.last_report: AdaptiveNormalSolveReport | None = None

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult:
        if hand_kernel_kind(state) != KERNEL_NORMAL_FANTASY:
            raise ValueError(
                "M5B adaptive Normal/Fantasy oracle received wrong kernel"
            )
        checked, continuation_sha = continuation_fingerprint(continuation_values)
        solver = NormalFantasyOutcomeSampling(
            current_meta=state,
            continuation_values=checked,
            terminal_evaluator=self.terminal_evaluator,
            epsilon=self.config.epsilon,
            seed=_state_seed(self.config.base_seed, "m5b-nf-solver", state),
            cfr_plus=True,
        )
        stats = solver.run(self.config.training_iterations)

        replay = DeterministicReservoir(
            capacity=self.config.replay_capacity,
            seed=_state_seed(self.config.base_seed, "m5b-nf-replay", state),
        )
        distilled = distill_normal_fantasy_solver_nodes(
            solver, replay, include_holdout=False
        )
        if not replay.items:
            raise RuntimeError(
                "M5B Normal/Fantasy training produced no distillation examples"
            )
        model = _new_model(
            self.config,
            seed=_state_seed(self.config.base_seed, "m5b-nf-model", state),
        )
        fit = model.fit(replay, epochs=self.config.fit_epochs)
        snapshot = freeze_nf_snapshot(
            model,
            training_continuation_values=checked,
            provenance=f"{self.oracle_id}|{continuation_sha}",
        )
        fixed = NormalFantasyFixedPolicyOracle(
            model,
            snapshot,
            samples=self.config.evaluation_samples,
            base_seed=_state_seed(self.config.base_seed, "m5b-nf-eval", state),
            terminal_evaluator=self.terminal_evaluator,
        )
        value = fixed.evaluate(state, checked)
        result = OneHandOracleResult(
            state=state,
            p0_value=value.p0_value,
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=value.samples,
            standard_error=value.standard_error,
        )
        self.last_report = AdaptiveNormalSolveReport(
            state=state.as_key(),
            continuation_sha256=continuation_sha,
            training_iterations=self.config.training_iterations,
            solver_infosets=int(stats.infosets),
            distilled_nodes=int(distilled["nodes"]),
            action_examples=int(distilled["action_examples"]),
            mean_huber_loss=float(fit["mean_huber_loss"]),
            policy_snapshot_sha256=snapshot.sha256,
            p0_value=result.p0_value,
            standard_error=result.standard_error,
            authority=self.authority,
        )
        return result
