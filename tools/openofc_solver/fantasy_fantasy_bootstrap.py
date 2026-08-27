from __future__ import annotations

"""Build sealed M4Q action-value examples from exact M4P support matrices.

The complete sampled world is used only to construct offline labels.  Every
emitted model example contains M4P own-information features for exactly one
player/candidate.  The opponent policy used for expectation is explicit and is
part of the training assumption, never silently treated as equilibrium.
"""

from dataclasses import dataclass
import math
from typing import Sequence

from fantasy_fantasy_kernel import (
    FantasyArrangement,
    FantasyFantasyWorld,
    canonical_action_key,
)
from fantasy_fantasy_payoff import FantasySupportPayoffMatrix, uniform_policy
from fantasy_fantasy_policy_features import encode_policy_action, encode_policy_state
from fantasy_fantasy_policy_model import FantasyPolicyExample

AUTHORITY = "EXACT_SUPPORT_MATRIX_BOOTSTRAP_TARGETS"
DEFAULT_SOURCE = "m4q-explicit-opponent-mixture-bootstrap"


def _normalize(weights: Sequence[float], expected: int) -> tuple[float, ...]:
    if len(weights) != expected:
        raise ValueError("opponent mixture length does not match support")
    values = tuple(float(x) for x in weights)
    if any(not math.isfinite(x) or x < 0.0 for x in values):
        raise ValueError("opponent mixture must be finite and non-negative")
    total = sum(values)
    if total <= 0.0:
        raise ValueError("opponent mixture must have positive mass")
    return tuple(x / total for x in values)


@dataclass(frozen=True)
class BootstrapTargetBatch:
    p0_examples: tuple[FantasyPolicyExample, ...]
    p1_examples: tuple[FantasyPolicyExample, ...]
    p0_opponent_policy: tuple[float, ...]
    p1_opponent_policy: tuple[float, ...]
    authority: str = AUTHORITY

    @property
    def example_count(self) -> int:
        return len(self.p0_examples) + len(self.p1_examples)


def build_bootstrap_targets(
    world: FantasyFantasyWorld,
    p0_support: Sequence[FantasyArrangement],
    p1_support: Sequence[FantasyArrangement],
    matrix: FantasySupportPayoffMatrix,
    *,
    p0_opponent_policy: Sequence[float] | None = None,
    p1_opponent_policy: Sequence[float] | None = None,
    source: str = DEFAULT_SOURCE,
) -> BootstrapTargetBatch:
    """Return exact action values under declared opponent support mixtures.

    `p0_opponent_policy` is P0's belief/mixture over P1 actions.
    `p1_opponent_policy` is P1's belief/mixture over P0 actions.
    If omitted, each is explicitly uniform over the corresponding support.
    """
    support0 = tuple(p0_support)
    support1 = tuple(p1_support)
    rows, cols = matrix.shape
    if len(support0) != rows or len(support1) != cols:
        raise ValueError("candidate supports do not match payoff matrix shape")
    if matrix.current_meta != world.current_meta:
        raise ValueError("payoff matrix meta-state does not match sampled world")
    actual_keys0 = tuple(canonical_action_key(world, 0, x) for x in support0)
    actual_keys1 = tuple(canonical_action_key(world, 1, x) for x in support1)
    if actual_keys0 != matrix.p0_action_keys or actual_keys1 != matrix.p1_action_keys:
        raise ValueError("candidate support order/identity does not match payoff matrix")

    sigma1 = _normalize(
        uniform_policy(cols) if p0_opponent_policy is None else p0_opponent_policy,
        cols,
    )
    sigma0 = _normalize(
        uniform_policy(rows) if p1_opponent_policy is None else p1_opponent_policy,
        rows,
    )

    state0 = encode_policy_state(
        world.plan.packet_for(0), current_meta=world.current_meta, player=0
    )
    state1 = encode_policy_state(
        world.plan.packet_for(1), current_meta=world.current_meta, player=1
    )
    p0_examples = []
    for i, arrangement in enumerate(support0):
        target = sum(sigma1[j] * matrix.p0_values[i][j] for j in range(cols))
        p0_examples.append(
            FantasyPolicyExample(
                state_features=state0,
                action_features=encode_policy_action(
                    world.plan.packet_for(0),
                    arrangement,
                    current_meta=world.current_meta,
                    player=0,
                ),
                target=float(target),
                source=source,
            )
        )

    p1_examples = []
    for j, arrangement in enumerate(support1):
        target = -sum(sigma0[i] * matrix.p0_values[i][j] for i in range(rows))
        p1_examples.append(
            FantasyPolicyExample(
                state_features=state1,
                action_features=encode_policy_action(
                    world.plan.packet_for(1),
                    arrangement,
                    current_meta=world.current_meta,
                    player=1,
                ),
                target=float(target),
                source=source,
            )
        )

    return BootstrapTargetBatch(
        p0_examples=tuple(p0_examples),
        p1_examples=tuple(p1_examples),
        p0_opponent_policy=sigma1,
        p1_opponent_policy=sigma0,
    )
