from __future__ import annotations

"""M4U continuation-safe certification boundary for sealed Fantasy/Fantasy HU.

M4S/M4T evidence is conditional on the exact continuation vector used to build
proposal supports, payoff matrices and fitted action-value targets.  This module
makes that dependency executable: a sealed Fantasy/Fantasy approximation may be
used by the outer Bellman loop only when both the state and the continuation
fingerprint match a SHA-bound certification manifest.

The module also exposes an exact support-payoff factorization into

    immediate_points + V(next_state)

so an already fixed action-support matrix can be rematerialized under another
continuation vector without rescoring poker hands.  This transport primitive does
NOT certify that the support or learned policy remains adequate after V changes.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from engine import score_heads_up
from fantasy_fantasy_kernel import (
    FantasyArrangement,
    FantasyFantasyWorld,
    canonical_action_key,
    validate_arrangement,
)
from fantasy_fantasy_payoff import (
    FantasySupportPayoffMatrix,
    continuation_fingerprint,
)
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    hand_kernel_kind,
    next_state_from_terminal_boards,
)
from plan_m4t_adaptive_scale import (
    PLAN_SCHEMA,
    coverage_tiers,
    sha as m4t_sha,
    signature as m4t_signature,
    validate_report,
)

CERT_SCHEMA = "openofc-m4u-continuation-certification-v1"
FACTOR_SCHEMA = "openofc-m4u-factorized-support-payoff-v1"
AUTHORITY = "CONTINUATION_SHA_BOUND_APPROXIMATION_FIREWALL"
ROUTE_CERTIFIED = "CERTIFIED_APPROXIMATION_ALLOWED"
ROUTE_BLOCKED = "UNCERTIFIED_APPROXIMATION_BLOCKED"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: Mapping[str, object]) -> str:
    raw = dict(payload)
    raw.pop("sha256", None)
    return hashlib.sha256(_canonical_bytes(raw)).hexdigest()


def m4t_state_key(state: HUContinuationState) -> str:
    if hand_kernel_kind(state) != KERNEL_FANTASY_FANTASY:
        raise ValueError("M4U certification only applies to Fantasy/Fantasy states")
    return (
        f"b{state.button}:p0f{state.p0_fantasy_cards}:"
        f"p1f{state.p1_fantasy_cards}"
    )


def _complete_passed_tier_states(plan: Mapping[str, object]) -> tuple[str, ...]:
    decisions = plan.get("state_decisions")
    if not isinstance(decisions, Mapping):
        raise ValueError("M4T plan missing state_decisions")
    out: list[str] = []
    for tier in coverage_tiers():
        if not all(
            isinstance(decisions.get(state), Mapping)
            and decisions[state].get("status") == "STATE_BUDGETS_PASS"  # type: ignore[index]
            for state in tier
        ):
            break
        out.extend(tier)
    return tuple(out)


def validate_m4t_plan(plan: Mapping[str, object]) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unsupported M4T plan schema")
    if plan.get("sha256") != m4t_sha(plan):
        raise ValueError("M4T plan SHA-256 mismatch")
    if plan.get("promotion_blocked") is not True:
        raise ValueError("M4T plan unexpectedly claims promotion authority")
    targets = plan.get("error_targets")
    if not isinstance(targets, Mapping) or any(
        targets.get(name) is None
        for name in (
            "mean_support_gap",
            "max_deviation",
            "mean_q_mae",
            "max_q_error",
        )
    ):
        raise ValueError("M4U requires explicit frozen numeric M4T targets")


def freeze_certification(
    plan: Mapping[str, object],
    source_report: Mapping[str, object],
    *,
    provenance: str,
) -> dict[str, object]:
    """Freeze the currently complete, passing M4T tiers with exact provenance."""
    validate_m4t_plan(plan)
    validate_report(source_report)
    if not provenance.strip():
        raise ValueError("certification provenance must be non-empty")
    if str(plan.get("experiment_signature")) != m4t_signature(source_report):
        raise ValueError("M4T plan/source report experiment mismatch")
    report_sha = str(source_report["sha256"])
    inputs = tuple(str(x) for x in plan.get("input_report_sha256", ()))
    if report_sha not in inputs:
        raise ValueError("source M4S report is not an input to this M4T plan")
    certified = _complete_passed_tier_states(plan)
    if not certified:
        raise ValueError("no complete M4T coverage tier is certified")

    payload: dict[str, object] = {
        "schema": CERT_SCHEMA,
        "authority": AUTHORITY,
        "promotion_blocked": True,
        "m4t_plan_sha256": str(plan["sha256"]),
        "m4s_source_report_sha256": report_sha,
        "experiment_signature": str(plan["experiment_signature"]),
        "generator_fingerprint": str(source_report["generator_fingerprint"]),
        "continuation_fingerprint": str(source_report["continuation_fingerprint"]),
        "error_targets": dict(plan["error_targets"]),  # type: ignore[arg-type]
        "certified_states": list(certified),
        "provenance": provenance.strip(),
    }
    payload["sha256"] = _sha(payload)
    return payload


def validate_certification(manifest: Mapping[str, object]) -> None:
    if manifest.get("schema") != CERT_SCHEMA or manifest.get("authority") != AUTHORITY:
        raise ValueError("unsupported M4U certification schema/authority")
    if manifest.get("sha256") != _sha(manifest):
        raise ValueError("M4U certification SHA-256 mismatch")
    if manifest.get("promotion_blocked") is not True:
        raise ValueError("M4U certification cannot promote policy by itself")
    states = manifest.get("certified_states")
    if not isinstance(states, list) or not states or len(states) != len(set(states)):
        raise ValueError("M4U certification state catalog is invalid")
    if not str(manifest.get("continuation_fingerprint", "")):
        raise ValueError("M4U certification missing continuation fingerprint")


def certification_route(
    manifest: Mapping[str, object],
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
) -> str:
    """Return a fail-closed routing decision for the outer continuation solve."""
    validate_certification(manifest)
    if hand_kernel_kind(state) != KERNEL_FANTASY_FANTASY:
        return ROUTE_BLOCKED
    _checked, continuation_sha = continuation_fingerprint(continuation_values)
    if continuation_sha != manifest["continuation_fingerprint"]:
        return ROUTE_BLOCKED
    return (
        ROUTE_CERTIFIED
        if m4t_state_key(state) in set(manifest["certified_states"])  # type: ignore[arg-type]
        else ROUTE_BLOCKED
    )


def require_certified(
    manifest: Mapping[str, object],
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
) -> None:
    route = certification_route(manifest, state, continuation_values)
    if route != ROUTE_CERTIFIED:
        raise RuntimeError(
            "sealed Fantasy/Fantasy approximation is not certified for this "
            "state/continuation vector"
        )


@dataclass(frozen=True)
class FactorizedFantasySupportPayoff:
    """Exact payoff support independent of any particular continuation vector."""

    current_meta: HUContinuationState
    p0_action_keys: tuple[str, ...]
    p1_action_keys: tuple[str, ...]
    immediate_p0: tuple[tuple[float, ...], ...]
    next_states: tuple[tuple[HUContinuationState, ...], ...]
    authority: str = "EXACT_M4U_IMMEDIATE_PLUS_NEXT_STATE_FACTORIZATION"

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.p0_action_keys), len(self.p1_action_keys)

    def __post_init__(self) -> None:
        rows, cols = self.shape
        if rows <= 0 or cols <= 0:
            raise ValueError("factorized payoff must be non-empty")
        if len(self.immediate_p0) != rows or any(
            len(row) != cols for row in self.immediate_p0
        ):
            raise ValueError("factorized immediate matrix shape mismatch")
        if len(self.next_states) != rows or any(
            len(row) != cols for row in self.next_states
        ):
            raise ValueError("factorized next-state matrix shape mismatch")
        if any(
            not math.isfinite(value)
            for row in self.immediate_p0
            for value in row
        ):
            raise ValueError("factorized payoff contains non-finite immediate value")


def build_factorized_support_payoff(
    world: FantasyFantasyWorld,
    p0_support: Sequence[FantasyArrangement],
    p1_support: Sequence[FantasyArrangement],
) -> FactorizedFantasySupportPayoff:
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

    keys0 = tuple(
        canonical_action_key(world, 0, arrangement) for arrangement in candidates0
    )
    keys1 = tuple(
        canonical_action_key(world, 1, arrangement) for arrangement in candidates1
    )
    if len(set(keys0)) != len(keys0) or len(set(keys1)) != len(keys1):
        raise ValueError("support contains duplicate suit-canonical arrangements")

    immediate: list[tuple[float, ...]] = []
    next_rows: list[tuple[HUContinuationState, ...]] = []
    for arrangement0 in candidates0:
        score_row: list[float] = []
        state_row: list[HUContinuationState] = []
        for arrangement1 in candidates1:
            score_row.append(
                float(score_heads_up(arrangement0.board, arrangement1.board).points)
            )
            state_row.append(
                next_state_from_terminal_boards(
                    world.current_meta, arrangement0.board, arrangement1.board
                )
            )
        immediate.append(tuple(score_row))
        next_rows.append(tuple(state_row))

    return FactorizedFantasySupportPayoff(
        current_meta=world.current_meta,
        p0_action_keys=keys0,
        p1_action_keys=keys1,
        immediate_p0=tuple(immediate),
        next_states=tuple(next_rows),
    )


def materialize_factorized_payoff(
    factor: FactorizedFantasySupportPayoff,
    continuation_values: Mapping[HUContinuationState, float],
) -> FantasySupportPayoffMatrix:
    checked, continuation_sha = continuation_fingerprint(continuation_values)
    rows, cols = factor.shape
    values = tuple(
        tuple(
            factor.immediate_p0[i][j] + float(checked[factor.next_states[i][j]])
            for j in range(cols)
        )
        for i in range(rows)
    )
    return FantasySupportPayoffMatrix(
        current_meta=factor.current_meta,
        p0_action_keys=factor.p0_action_keys,
        p1_action_keys=factor.p1_action_keys,
        p0_values=values,
        continuation_fingerprint=continuation_sha,
    )
