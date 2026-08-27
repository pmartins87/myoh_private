from __future__ import annotations

"""Exact zero-sum payoff matrices on bounded Fantasy/Fantasy action supports.

M4O supplies candidate arrangements from each player's own information only.
M4P is the offline strategic evaluator: after a complete chance world is sampled,
it may combine both private supports to score every candidate pair exactly as
current points + V(next state).  This full-world matrix must never be a runtime
policy input.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from fantasy_fantasy_kernel import (
    FantasyArrangement,
    FantasyFantasyWorld,
    canonical_action_key,
    terminal_utility,
    validate_arrangement,
)
from hu_continuation import HUContinuationState
from strategic_continuation_cfr import validate_continuation_values

AUTHORITY = "EXACT_BOUNDED_FANTASY_FANTASY_SUPPORT_PAYOFF_MATRIX"
POLICY_FIREWALL = "FULL_WORLD_MATRIX_IS_OFFLINE_TRAINING_AND_EVALUATION_ONLY"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def continuation_fingerprint(
    values: Mapping[HUContinuationState, float],
) -> tuple[dict[HUContinuationState, float], str]:
    checked = validate_continuation_values(values)
    payload = {state.as_key(): float(checked[state]) for state in sorted(checked)}
    return checked, hashlib.sha256(_canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class FantasySupportPayoffMatrix:
    current_meta: HUContinuationState
    p0_action_keys: tuple[str, ...]
    p1_action_keys: tuple[str, ...]
    p0_values: tuple[tuple[float, ...], ...]
    continuation_fingerprint: str
    authority: str = AUTHORITY

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.p0_action_keys), len(self.p1_action_keys)

    def __post_init__(self) -> None:
        rows, cols = self.shape
        if rows <= 0 or cols <= 0:
            raise ValueError("support payoff matrix must be non-empty")
        if len(self.p0_values) != rows or any(len(row) != cols for row in self.p0_values):
            raise ValueError("support payoff matrix shape mismatch")
        if len(set(self.p0_action_keys)) != rows or len(set(self.p1_action_keys)) != cols:
            raise ValueError("support payoff matrix contains duplicate canonical actions")
        if any(not math.isfinite(value) for row in self.p0_values for value in row):
            raise ValueError("support payoff matrix contains non-finite utility")


@dataclass(frozen=True)
class SupportDeviationDiagnostic:
    profile_p0_value: float
    p0_best_response_value: float
    p1_best_response_value: float
    p0_deviation_gain: float
    p1_deviation_gain: float
    total_support_deviation_gain: float


def build_exact_support_payoff_matrix(
    world: FantasyFantasyWorld,
    p0_support: Sequence[FantasyArrangement],
    p1_support: Sequence[FantasyArrangement],
    continuation_values: Mapping[HUContinuationState, float],
) -> FantasySupportPayoffMatrix:
    candidates0 = tuple(p0_support)
    candidates1 = tuple(p1_support)
    if not candidates0 or not candidates1:
        raise ValueError("both Fantasy supports must be non-empty")
    packet0 = world.plan.packet_for(0)
    packet1 = world.plan.packet_for(1)
    for arrangement in candidates0:
        validate_arrangement(packet0, arrangement)
    for arrangement in candidates1:
        validate_arrangement(packet1, arrangement)

    checked, continuation_sha = continuation_fingerprint(continuation_values)
    keys0 = tuple(canonical_action_key(world, 0, arrangement) for arrangement in candidates0)
    keys1 = tuple(canonical_action_key(world, 1, arrangement) for arrangement in candidates1)
    if len(set(keys0)) != len(keys0) or len(set(keys1)) != len(keys1):
        raise ValueError("support contains duplicate suit-canonical arrangements")

    values = []
    for arrangement0 in candidates0:
        row = []
        for arrangement1 in candidates1:
            value = terminal_utility(
                world,
                arrangement0,
                arrangement1,
                checked,
                update_player=0,
            )
            # Independent sign check catches perspective/continuation mistakes.
            reverse = terminal_utility(
                world,
                arrangement0,
                arrangement1,
                checked,
                update_player=1,
            )
            if abs(float(value) + float(reverse)) > 1e-9:
                raise AssertionError("Fantasy support payoff lost zero-sum parity")
            row.append(float(value))
        values.append(tuple(row))

    return FantasySupportPayoffMatrix(
        current_meta=world.current_meta,
        p0_action_keys=keys0,
        p1_action_keys=keys1,
        p0_values=tuple(values),
        continuation_fingerprint=continuation_sha,
    )


def _normalized_policy(weights: Sequence[float], expected: int) -> tuple[float, ...]:
    if len(weights) != expected:
        raise ValueError("policy length does not match support")
    values = tuple(float(x) for x in weights)
    if any(not math.isfinite(x) or x < 0.0 for x in values):
        raise ValueError("policy weights must be finite and non-negative")
    total = sum(values)
    if total <= 0.0:
        raise ValueError("policy must have positive total weight")
    return tuple(x / total for x in values)


def uniform_policy(size: int) -> tuple[float, ...]:
    if size <= 0:
        raise ValueError("uniform policy size must be positive")
    p = 1.0 / float(size)
    return tuple(p for _ in range(size))


def expected_p0_value(
    matrix: FantasySupportPayoffMatrix,
    p0_policy: Sequence[float],
    p1_policy: Sequence[float],
) -> float:
    rows, cols = matrix.shape
    sigma0 = _normalized_policy(p0_policy, rows)
    sigma1 = _normalized_policy(p1_policy, cols)
    return sum(
        sigma0[i] * sigma1[j] * matrix.p0_values[i][j]
        for i in range(rows)
        for j in range(cols)
    )


def support_deviation_diagnostic(
    matrix: FantasySupportPayoffMatrix,
    p0_policy: Sequence[float],
    p1_policy: Sequence[float],
) -> SupportDeviationDiagnostic:
    """Exact unilateral-deviation gains restricted to the supplied supports.

    This is not full-game exploitability: actions omitted by M4O are outside this
    matrix and remain covered separately by M4O's exact-teacher support gap.
    """
    rows, cols = matrix.shape
    sigma0 = _normalized_policy(p0_policy, rows)
    sigma1 = _normalized_policy(p1_policy, cols)
    profile = expected_p0_value(matrix, sigma0, sigma1)
    p0_br = max(
        sum(sigma1[j] * matrix.p0_values[i][j] for j in range(cols))
        for i in range(rows)
    )
    # Player 1 maximizes -P0 utility.
    p1_br = max(
        -sum(sigma0[i] * matrix.p0_values[i][j] for i in range(rows))
        for j in range(cols)
    )
    p0_gain = max(0.0, p0_br - profile)
    p1_gain = max(0.0, p1_br + profile)
    return SupportDeviationDiagnostic(
        profile_p0_value=float(profile),
        p0_best_response_value=float(p0_br),
        p1_best_response_value=float(p1_br),
        p0_deviation_gain=float(p0_gain),
        p1_deviation_gain=float(p1_gain),
        total_support_deviation_gain=float(p0_gain + p1_gain),
    )
