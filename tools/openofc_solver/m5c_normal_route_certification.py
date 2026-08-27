from __future__ import annotations

"""M5C fail-closed certification boundary for adaptive Normal-hand oracles.

M5B can retrain Normal/Normal and Normal/Fantasy policies at the current outer
continuation vector, but a train-at-current-V probe is not automatically safe to
feed into the real 50-state Bellman operator.  M5C makes held-out evidence and
its exact continuation SHA an executable routing requirement.

This module deliberately certifies routes, not the full OpenOFC policy.  Missing,
stale, failed or tampered evidence leaves the corresponding M4Z route blocked.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    hand_kernel_kind,
)
from m4z_outer_bellman import (
    OneHandOracleResult,
    OracleRegistry,
    ROUTE_READY_CERTIFIED,
)

EVIDENCE_SCHEMA = "openofc-m5c-normal-route-evidence-v1"
CERT_SCHEMA = "openofc-m5c-normal-route-certification-v1"
AUTHORITY = "CONTINUATION_SHA_BOUND_HELDOUT_NORMAL_ROUTE_FIREWALL"
ROUTE_CERTIFIED = "CERTIFIED_NORMAL_ROUTE_ALLOWED"
ROUTE_BLOCKED = "UNCERTIFIED_NORMAL_ROUTE_BLOCKED"
EPS = 1e-12


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: Mapping[str, object]) -> str:
    raw = dict(payload)
    raw.pop("sha256", None)
    return hashlib.sha256(_canonical_bytes(raw)).hexdigest()


def _is_sha256(value: object) -> bool:
    text = str(value)
    if len(text) != 64:
        return False
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def _normal_state(state: HUContinuationState) -> bool:
    return hand_kernel_kind(state) in (KERNEL_NORMAL_NORMAL, KERNEL_NORMAL_FANTASY)


def freeze_route_evidence(
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
    *,
    oracle_id: str,
    oracle_config_sha256: str,
    implementation_sha256: str,
    model_value: float,
    reference_value: float,
    standard_error: float,
    samples: int,
    max_abs_value_error: float,
    max_standard_error: float,
    reference_authority: str,
    provenance: str,
) -> dict[str, object]:
    """Freeze one independently budgeted held-out route check.

    Thresholds are caller supplied.  M5C never learns a threshold from the same
    smoke/evaluation sample that it is judging.
    """
    if not _normal_state(state):
        raise ValueError("M5C evidence only applies to Normal-hand kernels")
    _checked, continuation_sha = continuation_fingerprint(continuation_values)
    if not str(oracle_id).strip():
        raise ValueError("M5C evidence requires oracle_id")
    if not _is_sha256(oracle_config_sha256) or not _is_sha256(implementation_sha256):
        raise ValueError("M5C evidence requires SHA-256 config/implementation ids")
    numeric = (
        float(model_value),
        float(reference_value),
        float(standard_error),
        float(max_abs_value_error),
        float(max_standard_error),
    )
    if not all(math.isfinite(value) for value in numeric):
        raise ValueError("M5C evidence contains non-finite numeric value")
    if standard_error < 0.0 or max_abs_value_error < 0.0 or max_standard_error < 0.0:
        raise ValueError("M5C uncertainty/error budgets must be non-negative")
    if int(samples) <= 0:
        raise ValueError("M5C held-out sample count must be positive")
    if not str(reference_authority).strip() or not str(provenance).strip():
        raise ValueError("M5C evidence requires reference authority/provenance")

    abs_error = abs(float(model_value) - float(reference_value))
    passed = (
        abs_error <= float(max_abs_value_error) + EPS
        and float(standard_error) <= float(max_standard_error) + EPS
    )
    payload: dict[str, object] = {
        "schema": EVIDENCE_SCHEMA,
        "authority": AUTHORITY,
        "state": state.as_key(),
        "kernel_kind": hand_kernel_kind(state),
        "continuation_sha256": continuation_sha,
        "oracle_id": str(oracle_id),
        "oracle_config_sha256": str(oracle_config_sha256).lower(),
        "implementation_sha256": str(implementation_sha256).lower(),
        "model_value": float(model_value),
        "reference_value": float(reference_value),
        "abs_value_error": abs_error,
        "standard_error": float(standard_error),
        "samples": int(samples),
        "thresholds": {
            "max_abs_value_error": float(max_abs_value_error),
            "max_standard_error": float(max_standard_error),
        },
        "reference_authority": str(reference_authority).strip(),
        "provenance": str(provenance).strip(),
        "passed": bool(passed),
        "promotion_blocked": True,
    }
    payload["sha256"] = _sha(payload)
    return payload


def validate_route_evidence(evidence: Mapping[str, object]) -> None:
    if evidence.get("schema") != EVIDENCE_SCHEMA or evidence.get("authority") != AUTHORITY:
        raise ValueError("unsupported M5C evidence schema/authority")
    if evidence.get("sha256") != _sha(evidence):
        raise ValueError("M5C evidence SHA-256 mismatch")
    if evidence.get("promotion_blocked") is not True:
        raise ValueError("M5C route evidence cannot promote the full policy")
    if evidence.get("kernel_kind") not in (KERNEL_NORMAL_NORMAL, KERNEL_NORMAL_FANTASY):
        raise ValueError("M5C evidence contains non-Normal kernel")
    if not _is_sha256(evidence.get("continuation_sha256")):
        raise ValueError("M5C evidence continuation SHA is invalid")
    if not _is_sha256(evidence.get("oracle_config_sha256")) or not _is_sha256(
        evidence.get("implementation_sha256")
    ):
        raise ValueError("M5C evidence config/implementation SHA is invalid")
    thresholds = evidence.get("thresholds")
    if not isinstance(thresholds, Mapping):
        raise ValueError("M5C evidence missing explicit thresholds")
    max_error = float(thresholds.get("max_abs_value_error", -1.0))
    max_se = float(thresholds.get("max_standard_error", -1.0))
    if max_error < 0.0 or max_se < 0.0:
        raise ValueError("M5C evidence thresholds are invalid")
    abs_error = abs(float(evidence["model_value"]) - float(evidence["reference_value"]))
    if abs(abs_error - float(evidence.get("abs_value_error", math.nan))) > EPS:
        raise ValueError("M5C evidence stored error is inconsistent")
    expected_pass = abs_error <= max_error + EPS and float(evidence["standard_error"]) <= max_se + EPS
    if bool(evidence.get("passed")) != expected_pass:
        raise ValueError("M5C evidence pass/fail flag is inconsistent")
    if int(evidence.get("samples", 0)) <= 0:
        raise ValueError("M5C evidence sample count is invalid")


def freeze_certification(
    evidence_records: Sequence[Mapping[str, object]],
    continuation_values: Mapping[HUContinuationState, float],
    *,
    source_report_sha256: str,
    provenance: str,
) -> dict[str, object]:
    """Certify only explicitly evidenced passing Normal routes for one exact V."""
    _checked, continuation_sha = continuation_fingerprint(continuation_values)
    if not _is_sha256(source_report_sha256):
        raise ValueError("M5C certification requires source report SHA-256")
    if not str(provenance).strip():
        raise ValueError("M5C certification requires provenance")
    if not evidence_records:
        raise ValueError("M5C certification requires route evidence")

    routes: list[dict[str, object]] = []
    seen: set[str] = set()
    evidence_shas: list[str] = []
    for evidence in evidence_records:
        validate_route_evidence(evidence)
        if str(evidence["continuation_sha256"]) != continuation_sha:
            raise ValueError("M5C evidence is stale for this continuation vector")
        if evidence.get("passed") is not True:
            raise ValueError("M5C refuses to certify failed held-out evidence")
        state_key = str(evidence["state"])
        if state_key in seen:
            raise ValueError("M5C certification contains duplicate state evidence")
        seen.add(state_key)
        evidence_shas.append(str(evidence["sha256"]))
        routes.append(
            {
                "state": state_key,
                "kernel_kind": str(evidence["kernel_kind"]),
                "oracle_id": str(evidence["oracle_id"]),
                "oracle_config_sha256": str(evidence["oracle_config_sha256"]),
                "implementation_sha256": str(evidence["implementation_sha256"]),
                "evidence_sha256": str(evidence["sha256"]),
            }
        )

    routes.sort(key=lambda row: str(row["state"]))
    payload: dict[str, object] = {
        "schema": CERT_SCHEMA,
        "authority": AUTHORITY,
        "continuation_sha256": continuation_sha,
        "source_report_sha256": str(source_report_sha256).lower(),
        "evidence_sha256": sorted(evidence_shas),
        "certified_routes": routes,
        "certified_route_count": len(routes),
        "provenance": str(provenance).strip(),
        "promotion_blocked": True,
    }
    payload["sha256"] = _sha(payload)
    return payload


def validate_certification(manifest: Mapping[str, object]) -> None:
    if manifest.get("schema") != CERT_SCHEMA or manifest.get("authority") != AUTHORITY:
        raise ValueError("unsupported M5C certification schema/authority")
    if manifest.get("sha256") != _sha(manifest):
        raise ValueError("M5C certification SHA-256 mismatch")
    if manifest.get("promotion_blocked") is not True:
        raise ValueError("M5C certification cannot promote the full policy")
    if not _is_sha256(manifest.get("continuation_sha256")) or not _is_sha256(
        manifest.get("source_report_sha256")
    ):
        raise ValueError("M5C certification provenance SHA is invalid")
    routes = manifest.get("certified_routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("M5C certification has no certified routes")
    if int(manifest.get("certified_route_count", -1)) != len(routes):
        raise ValueError("M5C certified route count mismatch")
    keys: set[str] = set()
    for route in routes:
        if not isinstance(route, Mapping):
            raise ValueError("M5C certified route entry is invalid")
        state_key = str(route.get("state", ""))
        if not state_key or state_key in keys:
            raise ValueError("M5C certified route catalog has duplicate/empty state")
        keys.add(state_key)
        if route.get("kernel_kind") not in (KERNEL_NORMAL_NORMAL, KERNEL_NORMAL_FANTASY):
            raise ValueError("M5C certified route has invalid kernel")
        if not str(route.get("oracle_id", "")).strip():
            raise ValueError("M5C certified route missing oracle id")
        for field in ("oracle_config_sha256", "implementation_sha256", "evidence_sha256"):
            if not _is_sha256(route.get(field)):
                raise ValueError(f"M5C certified route has invalid {field}")


def _route_for(manifest: Mapping[str, object], state: HUContinuationState) -> Mapping[str, object] | None:
    for route in manifest["certified_routes"]:  # type: ignore[index]
        if str(route["state"]) == state.as_key():
            return route
    return None


def certification_route(
    manifest: Mapping[str, object],
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
) -> str:
    validate_certification(manifest)
    if not _normal_state(state):
        return ROUTE_BLOCKED
    _checked, continuation_sha = continuation_fingerprint(continuation_values)
    if continuation_sha != str(manifest["continuation_sha256"]):
        return ROUTE_BLOCKED
    route = _route_for(manifest, state)
    if route is None or str(route["kernel_kind"]) != hand_kernel_kind(state):
        return ROUTE_BLOCKED
    return ROUTE_CERTIFIED


def require_certified(
    manifest: Mapping[str, object],
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
) -> Mapping[str, object]:
    if certification_route(manifest, state, continuation_values) != ROUTE_CERTIFIED:
        raise RuntimeError(
            "adaptive Normal approximation is not certified for this state/continuation vector"
        )
    route = _route_for(manifest, state)
    assert route is not None
    return route


@dataclass
class CertifiedAdaptiveNormalOracle:
    """M4Z-facing wrapper that refuses stale or mismatched adaptive delegates."""

    delegate: object
    state: HUContinuationState
    manifest: Mapping[str, object]

    def __post_init__(self) -> None:
        validate_certification(self.manifest)
        route = _route_for(self.manifest, self.state)
        if route is None:
            raise ValueError("M5C wrapper state is not present in certification")
        delegate_id = str(getattr(self.delegate, "oracle_id", ""))
        if delegate_id != str(route["oracle_id"]):
            raise ValueError("M5C delegate oracle_id does not match certified evidence")
        self.oracle_id = (
            f"m5c:{self.state.as_key()}:{str(self.manifest['sha256'])[:16]}:{delegate_id}"
        )

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult:
        if state != self.state:
            raise ValueError("M5C certified oracle called for wrong state")
        route = require_certified(self.manifest, state, continuation_values)
        result = self.delegate.evaluate(state, continuation_values)  # type: ignore[attr-defined]
        _checked, continuation_sha = continuation_fingerprint(continuation_values)
        if result.state != state:
            raise AssertionError("M5C delegate returned wrong state")
        if result.continuation_sha256 != continuation_sha:
            raise AssertionError("M5C delegate returned stale continuation SHA")
        if result.oracle_id != str(route["oracle_id"]):
            raise AssertionError("M5C delegate oracle_id drifted after certification")
        return OneHandOracleResult(
            state=state,
            p0_value=float(result.p0_value),
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=int(result.samples),
            standard_error=float(result.standard_error),
        )


def register_certified_normal_routes(
    registry: OracleRegistry,
    manifest: Mapping[str, object],
    *,
    normal_normal_oracle: object,
    normal_fantasy_oracle: object,
) -> int:
    """Overlay certified Normal routes on an existing (normally blocked) M4Z registry."""
    validate_certification(manifest)
    state_by_key = {state.as_key(): state for state in all_states()}
    count = 0
    for route in manifest["certified_routes"]:  # type: ignore[index]
        state_key = str(route["state"])
        state = state_by_key.get(state_key)
        if state is None:
            raise ValueError("M5C certification references state outside HU catalog")
        kind = hand_kernel_kind(state)
        if kind == KERNEL_NORMAL_NORMAL:
            delegate = normal_normal_oracle
        elif kind == KERNEL_NORMAL_FANTASY:
            delegate = normal_fantasy_oracle
        elif kind == KERNEL_FANTASY_FANTASY:
            raise AssertionError("Fantasy/Fantasy route leaked into M5C")
        else:
            raise AssertionError("unknown HU kernel kind")
        wrapped = CertifiedAdaptiveNormalOracle(delegate, state, manifest)
        registry.register(
            state,
            wrapped,
            status=ROUTE_READY_CERTIFIED,
            authority=AUTHORITY,
            implementation_sha256=str(route["implementation_sha256"]),
        )
        count += 1
    return count
