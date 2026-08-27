from __future__ import annotations

"""Exact continuation-linear action targets for fixed sealed Fantasy supports.

M4U factors each support payoff cell into immediate points plus exact next-state
identity. M4V lifts that factorization through a frozen opponent support mixture.
Each candidate action becomes a linear functional of the full continuation
vector:

    Q_a(V) = immediate_a + sum_s coefficient[a,s] * V(s)

For player 0 the coefficients form a probability distribution (+1 total mass).
For player 1 they are the sign-reversed next-state distribution (-1 total mass),
because all continuation values are stored from persistent player-0 perspective.

This is exact for a fixed action support and fixed opponent support policy. It
does not certify that M4O support remains adequate when V changes, and it does
not claim the opponent policy itself is invariant to V.
"""

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import HUContinuationState
from m4u_continuation_boundary import FactorizedFantasySupportPayoff

AUTHORITY = "EXACT_CONTINUATION_LINEAR_TARGETS_FIXED_SUPPORT_AND_OPPONENT_MIXTURE"


def _normalize(weights: Sequence[float], expected: int) -> tuple[float, ...]:
    if len(weights) != expected:
        raise ValueError("opponent mixture length does not match support")
    values = tuple(float(x) for x in weights)
    if any(not math.isfinite(x) or x < 0.0 for x in values):
        raise ValueError("opponent mixture must be finite and non-negative")
    total = sum(values)
    if total <= 0.0:
        raise ValueError("opponent mixture must have positive total mass")
    return tuple(x / total for x in values)


@dataclass(frozen=True)
class ContinuationLinearTarget:
    player: int
    action_index: int
    immediate: float
    coefficients: tuple[tuple[HUContinuationState, float], ...]
    authority: str = AUTHORITY

    def __post_init__(self) -> None:
        if self.player not in (0, 1):
            raise ValueError("HU player must be 0 or 1")
        if self.action_index < 0 or not math.isfinite(self.immediate):
            raise ValueError("invalid continuation-linear target")
        if not self.coefficients:
            raise ValueError("continuation-linear target needs next-state mass")
        seen: set[HUContinuationState] = set()
        total = 0.0
        for state, coefficient in self.coefficients:
            if state in seen:
                raise ValueError("duplicate next state in linear target")
            seen.add(state)
            if not math.isfinite(coefficient):
                raise ValueError("non-finite continuation coefficient")
            total += coefficient
        expected = 1.0 if self.player == 0 else -1.0
        if abs(total - expected) > 1e-12:
            raise ValueError("continuation coefficients lost zero-sum mass")

    def value(
        self,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> float:
        checked, _sha = continuation_fingerprint(continuation_values)
        return float(
            self.immediate
            + sum(
                coefficient * float(checked[state])
                for state, coefficient in self.coefficients
            )
        )


@dataclass(frozen=True)
class ContinuationLinearTargetBatch:
    p0_targets: tuple[ContinuationLinearTarget, ...]
    p1_targets: tuple[ContinuationLinearTarget, ...]
    p0_opponent_policy: tuple[float, ...]
    p1_opponent_policy: tuple[float, ...]
    authority: str = AUTHORITY

    @property
    def target_count(self) -> int:
        return len(self.p0_targets) + len(self.p1_targets)


def _coalesce(
    rows: Sequence[tuple[HUContinuationState, float]],
) -> tuple[tuple[HUContinuationState, float], ...]:
    out: dict[HUContinuationState, float] = {}
    for state, mass in rows:
        out[state] = out.get(state, 0.0) + float(mass)
    return tuple(
        (state, value)
        for state, value in sorted(out.items())
        if abs(value) > 0.0
    )


def build_continuation_linear_targets(
    factor: FactorizedFantasySupportPayoff,
    *,
    p0_opponent_policy: Sequence[float],
    p1_opponent_policy: Sequence[float],
) -> ContinuationLinearTargetBatch:
    """Factor exact per-action Q targets through frozen opponent mixtures.

    `p0_opponent_policy` is the mixture over P1 support actions used for P0 Qs.
    `p1_opponent_policy` is the mixture over P0 support actions used for P1 Qs.
    """
    rows, cols = factor.shape
    sigma1 = _normalize(p0_opponent_policy, cols)
    sigma0 = _normalize(p1_opponent_policy, rows)

    p0_targets: list[ContinuationLinearTarget] = []
    for i in range(rows):
        immediate = sum(
            sigma1[j] * factor.immediate_p0[i][j]
            for j in range(cols)
        )
        coefficients = _coalesce(
            tuple(
                (factor.next_states[i][j], sigma1[j])
                for j in range(cols)
            )
        )
        p0_targets.append(
            ContinuationLinearTarget(
                player=0,
                action_index=i,
                immediate=float(immediate),
                coefficients=coefficients,
            )
        )

    p1_targets: list[ContinuationLinearTarget] = []
    for j in range(cols):
        immediate = -sum(
            sigma0[i] * factor.immediate_p0[i][j]
            for i in range(rows)
        )
        coefficients = _coalesce(
            tuple(
                (factor.next_states[i][j], -sigma0[i])
                for i in range(rows)
            )
        )
        p1_targets.append(
            ContinuationLinearTarget(
                player=1,
                action_index=j,
                immediate=float(immediate),
                coefficients=coefficients,
            )
        )

    return ContinuationLinearTargetBatch(
        p0_targets=tuple(p0_targets),
        p1_targets=tuple(p1_targets),
        p0_opponent_policy=sigma1,
        p1_opponent_policy=sigma0,
    )


def materialize_target_values(
    batch: ContinuationLinearTargetBatch,
    continuation_values: Mapping[HUContinuationState, float],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    return (
        tuple(target.value(continuation_values) for target in batch.p0_targets),
        tuple(target.value(continuation_values) for target in batch.p1_targets),
    )
