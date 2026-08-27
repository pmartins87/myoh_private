from __future__ import annotations

"""Continuation-aware fitted self-play for sealed Fantasy/Fantasy supports.

M4R fitted scalar Q values tied to one V. M4W changed the learned object to
continuation-independent immediate utility + next-mode distribution. M5B uses
that representation in synchronous self-play: opponent mixtures are frozen at
the current model/current V, exact M4U factors are lifted by M4V into linear
outcome targets, and M4W is trained on those continuation-independent labels.

All complete-world matrices/factors stay offline. Runtime policies receive only
own packet, own support, public meta-state and the current continuation vector.
This is a strategic-improvement probe, not an equilibrium certificate.
"""

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from fantasy_fantasy_kernel import FantasyArrangement, FantasyFantasyWorld
from fantasy_fantasy_payoff import (
    SupportDeviationDiagnostic,
    support_deviation_diagnostic,
)
from hu_continuation import HUContinuationState
from m4u_continuation_boundary import (
    FactorizedFantasySupportPayoff,
    build_factorized_support_payoff,
    materialize_factorized_payoff,
)
from m4v_continuation_targets import build_continuation_linear_targets
from m4w_outcome_model import (
    FantasyOutcomeExample,
    SparseFantasyOutcomeModel,
    build_outcome_examples,
)

AUTHORITY = "CONTINUATION_AWARE_M4W_FITTED_SELFPLAY_PROBE_NOT_EQUILIBRIUM"


@dataclass(frozen=True)
class ContinuationAwareEpisode:
    world: FantasyFantasyWorld
    p0_support: tuple[FantasyArrangement, ...]
    p1_support: tuple[FantasyArrangement, ...]
    factor: FactorizedFantasySupportPayoff

    def __post_init__(self) -> None:
        if self.factor.current_meta != self.world.current_meta:
            raise ValueError("M5B episode factor/meta mismatch")
        if self.factor.shape != (len(self.p0_support), len(self.p1_support)):
            raise ValueError("M5B episode factor/support shape mismatch")

    @classmethod
    def build(
        cls,
        world: FantasyFantasyWorld,
        p0_support: Sequence[FantasyArrangement],
        p1_support: Sequence[FantasyArrangement],
    ) -> "ContinuationAwareEpisode":
        support0 = tuple(p0_support)
        support1 = tuple(p1_support)
        return cls(
            world=world,
            p0_support=support0,
            p1_support=support1,
            factor=build_factorized_support_payoff(world, support0, support1),
        )


@dataclass(frozen=True)
class PolicyDiagnosticSnapshot:
    p0_policy: tuple[float, ...]
    p1_policy: tuple[float, ...]
    diagnostic: SupportDeviationDiagnostic


@dataclass(frozen=True)
class ContinuationAwareSelfPlayReport:
    episodes: int
    examples: int
    epochs: int
    mean_support_deviation_before: float
    mean_support_deviation_after: float
    max_support_deviation_before: float
    max_support_deviation_after: float
    mean_immediate_huber_loss: float
    mean_outcome_cross_entropy: float
    authority: str = AUTHORITY


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def snapshot_policy(
    model: SparseFantasyOutcomeModel,
    episode: ContinuationAwareEpisode,
    continuation_values: Mapping[HUContinuationState, float],
    *,
    temperature: float = 1.0,
) -> PolicyDiagnosticSnapshot:
    world = episode.world
    sigma0 = model.policy_for_private_support(
        world.plan.packet_for(0),
        episode.p0_support,
        current_meta=world.current_meta,
        player=0,
        continuation_values=continuation_values,
        temperature=temperature,
    )
    sigma1 = model.policy_for_private_support(
        world.plan.packet_for(1),
        episode.p1_support,
        current_meta=world.current_meta,
        player=1,
        continuation_values=continuation_values,
        temperature=temperature,
    )
    matrix = materialize_factorized_payoff(episode.factor, continuation_values)
    diagnostic = support_deviation_diagnostic(matrix, sigma0, sigma1)
    return PolicyDiagnosticSnapshot(
        p0_policy=tuple(sigma0),
        p1_policy=tuple(sigma1),
        diagnostic=diagnostic,
    )


def exact_outcome_targets_for_snapshot(
    episode: ContinuationAwareEpisode,
    snapshot: PolicyDiagnosticSnapshot,
) -> tuple[FantasyOutcomeExample, ...]:
    linear = build_continuation_linear_targets(
        episode.factor,
        p0_opponent_policy=snapshot.p1_policy,
        p1_opponent_policy=snapshot.p0_policy,
    )
    return build_outcome_examples(
        episode.world,
        episode.p0_support,
        episode.p1_support,
        linear,
        source="m5b-exact-current-policy-outcome-selfplay",
    )


def train_selfplay_iteration(
    model: SparseFantasyOutcomeModel,
    episodes: Sequence[ContinuationAwareEpisode],
    continuation_values: Mapping[HUContinuationState, float],
    *,
    epochs: int = 1,
    temperature: float = 1.0,
) -> ContinuationAwareSelfPlayReport:
    rows = tuple(episodes)
    if not rows:
        raise ValueError("M5B self-play requires episodes")
    if epochs <= 0 or not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("M5B self-play parameters are invalid")

    before: list[PolicyDiagnosticSnapshot] = []
    examples: list[FantasyOutcomeExample] = []
    for episode in rows:
        snapshot = snapshot_policy(
            model,
            episode,
            continuation_values,
            temperature=temperature,
        )
        before.append(snapshot)
        examples.extend(exact_outcome_targets_for_snapshot(episode, snapshot))

    fit = model.fit(examples, epochs=epochs)
    after = [
        snapshot_policy(
            model,
            episode,
            continuation_values,
            temperature=temperature,
        )
        for episode in rows
    ]
    before_dev = [
        row.diagnostic.total_support_deviation_gain for row in before
    ]
    after_dev = [
        row.diagnostic.total_support_deviation_gain for row in after
    ]
    if any(
        not math.isfinite(x) or x < -1e-9 for x in before_dev + after_dev
    ):
        raise AssertionError("M5B support deviation diagnostic became invalid")

    return ContinuationAwareSelfPlayReport(
        episodes=len(rows),
        examples=len(examples),
        epochs=epochs,
        mean_support_deviation_before=_mean(before_dev),
        mean_support_deviation_after=_mean(after_dev),
        max_support_deviation_before=max(before_dev),
        max_support_deviation_after=max(after_dev),
        mean_immediate_huber_loss=float(fit["mean_immediate_huber_loss"]),
        mean_outcome_cross_entropy=float(fit["mean_outcome_cross_entropy"]),
    )
