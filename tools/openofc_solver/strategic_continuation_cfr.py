from __future__ import annotations

"""Continuation-coupled HU normal/normal MCCFR.

This is the first strategic kernel whose normal-hand decisions can be trained
against an explicit solved/iterated cross-hand continuation vector instead of
current-hand points only.  It preserves the complete action set and the exact
24-way suit reduction from strategic_suit_symmetry.

Authority is deliberately STRATEGIC_APPROX until the continuation vector itself
is solved and a best-response/exploitability certificate passes.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_NORMAL,
    all_states,
    continuation_adjusted_terminal_utility,
    hand_kernel_kind,
    identity_for_role,
)
from strategic_cfr import HUState, child_state
from strategic_suit_symmetry import (
    SuitCanonicalOutcomeSamplingMCCFR,
    _sample_index,
    canonical_node_view,
)

AUTHORITY = "STRATEGIC_APPROX_HU_NORMAL_NORMAL_WITH_CONTINUATION"
SOLVER_KIND = "suit24-continuation-exact"
OBJECTIVE_SCHEMA = "openofc-hu-continuation-objective-v1"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _state_from_key(key: str) -> HUContinuationState:
    try:
        button_part, p0_part, p1_part = key.split(":")
        if not button_part.startswith("B") or not p0_part.startswith("P0F") \
                or not p1_part.startswith("P1F"):
            raise ValueError
        return HUContinuationState(
            int(button_part[1:]), int(p0_part[3:]), int(p1_part[3:])
        )
    except Exception as exc:
        raise ValueError(f"invalid HU continuation state key: {key!r}") from exc


def validate_continuation_values(
    values: Mapping[HUContinuationState, float],
) -> dict[HUContinuationState, float]:
    required = set(all_states())
    supplied = set(values)
    if supplied != required:
        missing = sorted(state.as_key() for state in required - supplied)
        extra = sorted(state.as_key() for state in supplied - required)
        raise ValueError(
            f"continuation vector must contain all 50 states; "
            f"missing={missing[:3]} extra={extra[:3]}"
        )
    result: dict[HUContinuationState, float] = {}
    for state in required:
        value = float(values[state])
        if not math.isfinite(value):
            raise ValueError(f"non-finite continuation value for {state.as_key()}")
        result[state] = value
    return result


@dataclass(frozen=True)
class ContinuationObjective:
    current_state: HUContinuationState
    values: Mapping[HUContinuationState, float]

    def __post_init__(self) -> None:
        if hand_kernel_kind(self.current_state) != KERNEL_NORMAL_NORMAL:
            raise ValueError("normal/normal MCCFR requires both players outside Fantasy")
        object.__setattr__(self, "values", validate_continuation_values(self.values))

    def payload(self) -> dict:
        values = {
            state.as_key(): float(self.values[state])
            for state in sorted(all_states())
        }
        base = {
            "schema": OBJECTIVE_SCHEMA,
            "current_state": self.current_state.as_key(),
            "values": values,
        }
        base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
        return base

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ContinuationObjective":
        if payload.get("schema") != OBJECTIVE_SCHEMA:
            raise ValueError("unsupported continuation objective schema")
        raw = dict(payload)
        expected = str(raw.pop("sha256", ""))
        actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
        if expected != actual:
            raise ValueError("continuation objective SHA-256 mismatch")
        raw_values = raw.get("values")
        if not isinstance(raw_values, dict):
            raise ValueError("continuation objective values are missing")
        values = {
            _state_from_key(str(key)): float(value)
            for key, value in raw_values.items()
        }
        return cls(
            current_state=_state_from_key(str(raw["current_state"])),
            values=values,
        )

    @property
    def fingerprint(self) -> str:
        return str(self.payload()["sha256"])


class SuitCanonicalContinuationMCCFR(SuitCanonicalOutcomeSamplingMCCFR):
    """Full-action suit-canonical normal/normal MCCFR with Bellman continuation."""

    solver_kind = SOLVER_KIND

    def __init__(
        self,
        *,
        objective: ContinuationObjective,
        epsilon: float = 0.6,
        seed: int = 20260825,
        cfr_plus: bool = True,
    ) -> None:
        super().__init__(epsilon=epsilon, seed=seed, cfr_plus=cfr_plus)
        self.objective = objective

    def terminal_value(self, state: HUState, update_role: int) -> float:
        if not state.terminal():
            raise ValueError("continuation terminal utility requires terminal HU state")
        if update_role not in (0, 1):
            raise ValueError("HU role must be 0 or 1")

        # strategic_cfr uses relative role 0=nondealer, 1=dealer.  The outer
        # continuation state uses persistent player identities, so remap both
        # terminal boards and the requested utility perspective exactly.
        persistent_boards = [None, None]
        for role in (0, 1):
            persistent = identity_for_role(self.objective.current_state, role)
            persistent_boards[persistent] = state.boards[role]
        if persistent_boards[0] is None or persistent_boards[1] is None:
            raise AssertionError("relative-role to persistent-player mapping failed")
        persistent_update = identity_for_role(
            self.objective.current_state, update_role
        )
        return continuation_adjusted_terminal_utility(
            self.objective.current_state,
            persistent_boards[0],
            persistent_boards[1],
            self.objective.values,
            update_player=persistent_update,
        )

    def _episode(
        self,
        state: HUState,
        update_player: int,
        *,
        my_reach: float,
        opp_reach: float,
        sample_reach: float,
    ) -> float:
        if state.terminal():
            return self.terminal_value(state, update_player)

        current = state.actor
        key, pairs, _suit_map = canonical_node_view(state)
        action_keys = [action_key for action_key, _ in pairs]
        actions = [action for _, action in pairs]
        node = self._node(key, action_keys)
        policy = node.current_policy()

        if current == update_player:
            uniform = 1.0 / len(policy)
            sample_policy = [
                self.epsilon * uniform + (1.0 - self.epsilon) * p
                for p in policy
            ]
        else:
            sample_policy = list(policy)

        sampled = _sample_index(sample_policy, self.rng)
        if current == update_player:
            new_my_reach = my_reach * policy[sampled]
            new_opp_reach = opp_reach
        else:
            new_my_reach = my_reach
            new_opp_reach = opp_reach * policy[sampled]
        new_sample_reach = sample_reach * sample_policy[sampled]
        child_value = self._episode(
            child_state(state, actions[sampled]),
            update_player,
            my_reach=new_my_reach,
            opp_reach=new_opp_reach,
            sample_reach=new_sample_reach,
        )

        child_values = [0.0] * len(policy)
        child_values[sampled] = child_value / sample_policy[sampled]
        value_estimate = sum(
            policy[i] * child_values[i] for i in range(len(policy))
        )

        if current == update_player:
            if sample_reach <= 0.0:
                raise AssertionError("sample reach became non-positive")
            scale = opp_reach / sample_reach
            cf_value = value_estimate * scale
            for i in range(len(policy)):
                delta = child_values[i] * scale - cf_value
                updated = node.cumulative_regrets[i] + delta
                node.cumulative_regrets[i] = (
                    max(0.0, updated) if self.cfr_plus else updated
                )
            for i in range(len(policy)):
                node.cumulative_policy[i] += (
                    my_reach * policy[i] / sample_reach
                )
            node.visits += 1

        return value_estimate

    def checkpoint_payload(self) -> dict:
        payload = super().checkpoint_payload()
        payload["continuation_objective"] = self.objective.payload()
        payload["solver_kind"] = self.solver_kind
        payload["authority"] = AUTHORITY
        return payload
