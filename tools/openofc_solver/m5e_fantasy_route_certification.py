from __future__ import annotations

"""Fail-closed held-out certification for Fantasy/Fantasy one-hand routes.

M4X protects action-support coverage across a declared continuation region, M4W
provides a sealed continuation-aware outcome model, M5A exposes a state-value
adapter, and M5B adds fitted self-play.  M5E is the routing firewall that keeps
those pieces out of a REAL M4Z Bellman image until independent held-out evidence
passes explicit externally supplied budgets at the exact continuation SHA.

The certificate is intentionally per-V.  M5D is responsible for rebuilding the
50-state certified registry after every Bellman update rather than widening a
stale certificate.
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
    all_states,
    hand_kernel_kind,
)
from m4x_robust_support import ContinuationFamily, continuation_region_membership
from m4z_outer_bellman import (
    OneHandOracleResult,
    OracleRegistry,
    ROUTE_READY_CERTIFIED,
)

EVIDENCE_SCHEMA = "openofc-m5e-fantasy-route-evidence-v1"
CERT_SCHEMA = "openofc-m5e-fantasy-route-certification-v1"
AUTHORITY = "CONTINUATION_SHA_BOUND_HELDOUT_FANTASY_ROUTE_FIREWALL"
ROUTE_CERTIFIED = "CERTIFIED_FANTASY_ROUTE_ALLOWED"
ROUTE_BLOCKED = "UNCERTIFIED_FANTASY_ROUTE_BLOCKED"
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


def _require_fantasy_state(state: HUContinuationState) -> None:
    if hand_kernel_kind(state) != KERNEL_FANTASY_FANTASY:
        raise ValueError("M5E evidence only applies to Fantasy/Fantasy states")


def freeze_route_evidence(
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
    family: ContinuationFamily,
    *,
    oracle_id: str,
    model_sha256: str,
    implementation_sha256: str,
    support_gap: float,
    support_deviation_gain: float,
    model_q_mae: float,
    model_q_max_error: float,
    standard_error: float,
    heldout_worlds: int,
    heldout_seeds: int,
    max_support_gap: float,
    max_support_deviation_gain: float,
    max_model_q_mae: float,
    max_model_q_error: float,
    max_standard_error: float,
    reference_authority: str,
    provenance: str,
) -> dict[str, object]:
    """Freeze one exact-V held-out Fantasy/Fantasy route decision."""
    _require_fantasy_state(state)
    checked, continuation_sha = continuation_fingerprint(continuation_values)
    membership = continuation_region_membership(family, checked)
    if not membership.inside:
        raise ValueError("M5E continuation vector is outside the M4X support region")
    if not str(oracle_id).strip():
        raise ValueError("M5E evidence requires oracle_id")
    for field in (model_sha256, implementation_sha256, family.sha256):
        if not _is_sha256(field):
            raise ValueError("M5E evidence requires valid model/implementation/family SHA")
    if not _is_sha256(family.source_sha256):
        raise ValueError("M5E continuation family source SHA is invalid")
    if int(heldout_worlds) <= 0 or int(heldout_seeds) <= 0:
        raise ValueError("M5E held-out worlds/seeds must be positive")
    if not str(reference_authority).strip() or not str(provenance).strip():
        raise ValueError("M5E evidence requires reference authority/provenance")

    metrics = {
        "support_gap": float(support_gap),
        "support_deviation_gain": float(support_deviation_gain),
        "model_q_mae": float(model_q_mae),
        "model_q_max_error": float(model_q_max_error),
        "standard_error": float(standard_error),
    }
    thresholds = {
        "max_support_gap": float(max_support_gap),
        "max_support_deviation_gain": float(max_support_deviation_gain),
        "max_model_q_mae": float(max_model_q_mae),
        "max_model_q_error": float(max_model_q_error),
        "max_standard_error": float(max_standard_error),
    }
    if not all(math.isfinite(value) and value >= 0.0 for value in metrics.values()):
        raise ValueError("M5E strategic metrics must be finite/non-negative")
    if not all(math.isfinite(value) and value >= 0.0 for value in thresholds.values()):
        raise ValueError("M5E acceptance thresholds must be finite/non-negative")

    passed = (
        metrics["support_gap"] <= thresholds["max_support_gap"] + EPS
        and metrics["support_deviation_gain"]
        <= thresholds["max_support_deviation_gain"] + EPS
        and metrics["model_q_mae"] <= thresholds["max_model_q_mae"] + EPS
        and metrics["model_q_max_error"] <= thresholds["max_model_q_error"] + EPS
        and metrics["standard_error"] <= thresholds["max_standard_error"] + EPS
    )
    payload: dict[str, object] = {
        "schema": EVIDENCE_SCHEMA,
        "authority": AUTHORITY,
        "state": state.as_key(),
        "kernel_kind": KERNEL_FANTASY_FANTASY,
        "continuation_sha256": continuation_sha,
        "family_sha256": family.sha256,
        "family_source_sha256": family.source_sha256,
        "region_nearest_anchor": membership.nearest_anchor,
        "region_distance_linf": membership.distance_linf,
        "region_radius_linf": membership.radius_linf,
        "oracle_id": str(oracle_id),
        "model_sha256": str(model_sha256).lower(),
        "implementation_sha256": str(implementation_sha256).lower(),
        "metrics": metrics,
        "thresholds": thresholds,
        "heldout_worlds": int(heldout_worlds),
        "heldout_seeds": int(heldout_seeds),
        "reference_authority": str(reference_authority).strip(),
        "provenance": str(provenance).strip(),
        "passed": bool(passed),
        "promotion_blocked": True,
    }
    payload["sha256"] = _sha(payload)
    return payload


def validate_route_evidence(evidence: Mapping[str, object]) -> None:
    if evidence.get("schema") != EVIDENCE_SCHEMA or evidence.get("authority") != AUTHORITY:
        raise ValueError("unsupported M5E evidence schema/authority")
    if evidence.get("sha256") != _sha(evidence):
        raise ValueError("M5E evidence SHA-256 mismatch")
    if evidence.get("promotion_blocked") is not True:
        raise ValueError("M5E evidence cannot promote the full policy")
    if evidence.get("kernel_kind") != KERNEL_FANTASY_FANTASY:
        raise ValueError("M5E evidence kernel mismatch")
    for field in (
        "continuation_sha256",
        "family_sha256",
        "family_source_sha256",
        "model_sha256",
        "implementation_sha256",
    ):
        if not _is_sha256(evidence.get(field)):
            raise ValueError(f"M5E evidence has invalid {field}")
    metrics = evidence.get("metrics")
    thresholds = evidence.get("thresholds")
    if not isinstance(metrics, Mapping) or not isinstance(thresholds, Mapping):
        raise ValueError("M5E evidence metrics/thresholds are missing")
    metric_names = (
        "support_gap",
        "support_deviation_gain",
        "model_q_mae",
        "model_q_max_error",
        "standard_error",
    )
    threshold_names = (
        "max_support_gap",
        "max_support_deviation_gain",
        "max_model_q_mae",
        "max_model_q_error",
        "max_standard_error",
    )
    metric_values = [float(metrics.get(name, math.nan)) for name in metric_names]
    threshold_values = [float(thresholds.get(name, math.nan)) for name in threshold_names]
    if not all(math.isfinite(value) and value >= 0.0 for value in metric_values):
        raise ValueError("M5E evidence contains invalid metric")
    if not all(math.isfinite(value) and value >= 0.0 for value in threshold_values):
        raise ValueError("M5E evidence contains invalid threshold")
    expected_pass = all(
        metric <= threshold + EPS
        for metric, threshold in zip(metric_values, threshold_values)
    )
    if bool(evidence.get("passed")) != expected_pass:
        raise ValueError("M5E evidence pass/fail flag is inconsistent")
    if int(evidence.get("heldout_worlds", 0)) <= 0 or int(evidence.get("heldout_seeds", 0)) <= 0:
        raise ValueError("M5E evidence held-out cardinality is invalid")
    if not str(evidence.get("oracle_id", "")).strip():
        raise ValueError("M5E evidence oracle id is missing")
    if not str(evidence.get("reference_authority", "")).strip() or not str(
        evidence.get("provenance", "")
    ).strip():
        raise ValueError("M5E evidence reference provenance is missing")


def freeze_certification(
    evidence_records: Sequence[Mapping[str, object]],
    continuation_values: Mapping[HUContinuationState, float],
    family: ContinuationFamily,
    *,
    source_report_sha256: str,
    provenance: str,
) -> dict[str, object]:
    checked, continuation_sha = continuation_fingerprint(continuation_values)
    membership = continuation_region_membership(family, checked)
    if not membership.inside:
        raise ValueError("M5E certification continuation is outside M4X region")
    if not _is_sha256(source_report_sha256):
        raise ValueError("M5E certification requires source report SHA-256")
    if not str(provenance).strip():
        raise ValueError("M5E certification requires provenance")
    if not evidence_records:
        raise ValueError("M5E certification requires route evidence")

    seen: set[str] = set()
    evidence_shas: list[str] = []
    routes: list[dict[str, object]] = []
    for evidence in evidence_records:
        validate_route_evidence(evidence)
        if evidence.get("passed") is not True:
            raise ValueError("M5E refuses to certify failed held-out evidence")
        if str(evidence["continuation_sha256"]) != continuation_sha:
            raise ValueError("M5E evidence is stale for this continuation vector")
        if str(evidence["family_sha256"]) != family.sha256:
            raise ValueError("M5E evidence belongs to a different M4X family")
        state_key = str(evidence["state"])
        if state_key in seen:
            raise ValueError("M5E certification contains duplicate state evidence")
        seen.add(state_key)
        evidence_shas.append(str(evidence["sha256"]))
        routes.append(
            {
                "state": state_key,
                "kernel_kind": KERNEL_FANTASY_FANTASY,
                "oracle_id": str(evidence["oracle_id"]),
                "model_sha256": str(evidence["model_sha256"]),
                "implementation_sha256": str(evidence["implementation_sha256"]),
                "evidence_sha256": str(evidence["sha256"]),
            }
        )
    routes.sort(key=lambda row: str(row["state"]))
    payload: dict[str, object] = {
        "schema": CERT_SCHEMA,
        "authority": AUTHORITY,
        "continuation_sha256": continuation_sha,
        "family_sha256": family.sha256,
        "family_source_sha256": family.source_sha256,
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
        raise ValueError("unsupported M5E certification schema/authority")
    if manifest.get("sha256") != _sha(manifest):
        raise ValueError("M5E certification SHA-256 mismatch")
    if manifest.get("promotion_blocked") is not True:
        raise ValueError("M5E certification cannot promote the full policy")
    for field in (
        "continuation_sha256",
        "family_sha256",
        "family_source_sha256",
        "source_report_sha256",
    ):
        if not _is_sha256(manifest.get(field)):
            raise ValueError(f"M5E certification has invalid {field}")
    routes = manifest.get("certified_routes")
    if not isinstance(routes, Sequence) or isinstance(routes, (str, bytes)):
        raise ValueError("M5E certification route catalog is invalid")
    if int(manifest.get("certified_route_count", -1)) != len(routes):
        raise ValueError("M5E certified route count mismatch")
    seen: set[str] = set()
    for route in routes:
        if not isinstance(route, Mapping):
            raise ValueError("M5E certified route entry is invalid")
        state_key = str(route.get("state", ""))
        if not state_key or state_key in seen:
            raise ValueError("M5E certified route catalog has duplicate/empty state")
        seen.add(state_key)
        if route.get("kernel_kind") != KERNEL_FANTASY_FANTASY:
            raise ValueError("M5E certified route has invalid kernel")
        if not str(route.get("oracle_id", "")).strip():
            raise ValueError("M5E certified route missing oracle id")
        for field in ("model_sha256", "implementation_sha256", "evidence_sha256"):
            if not _is_sha256(route.get(field)):
                raise ValueError(f"M5E certified route has invalid {field}")


def _route_for(
    manifest: Mapping[str, object], state: HUContinuationState
) -> Mapping[str, object] | None:
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
    if hand_kernel_kind(state) != KERNEL_FANTASY_FANTASY:
        return ROUTE_BLOCKED
    _checked, continuation_sha = continuation_fingerprint(continuation_values)
    if continuation_sha != str(manifest["continuation_sha256"]):
        return ROUTE_BLOCKED
    route = _route_for(manifest, state)
    if route is None:
        return ROUTE_BLOCKED
    return ROUTE_CERTIFIED


def require_certified(
    manifest: Mapping[str, object],
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
) -> Mapping[str, object]:
    if certification_route(manifest, state, continuation_values) != ROUTE_CERTIFIED:
        raise RuntimeError(
            "Fantasy/Fantasy approximation is not certified for this state/continuation vector"
        )
    route = _route_for(manifest, state)
    assert route is not None
    return route


def _delegate_model_sha(delegate: object) -> str:
    snapshot = getattr(delegate, "snapshot", None)
    return str(getattr(snapshot, "model_sha256", getattr(delegate, "model_sha256", "")))


def _delegate_family_sha(delegate: object) -> str:
    family = getattr(delegate, "family", None)
    return str(getattr(family, "sha256", getattr(delegate, "family_sha256", "")))


@dataclass
class CertifiedFantasyFantasyOracle:
    delegate: object
    state: HUContinuationState
    manifest: Mapping[str, object]

    def __post_init__(self) -> None:
        validate_certification(self.manifest)
        _require_fantasy_state(self.state)
        route = _route_for(self.manifest, self.state)
        if route is None:
            raise ValueError("M5E wrapper state is not present in certification")
        if str(getattr(self.delegate, "oracle_id", "")) != str(route["oracle_id"]):
            raise ValueError("M5E delegate oracle_id does not match certified evidence")
        if _delegate_model_sha(self.delegate) != str(route["model_sha256"]):
            raise ValueError("M5E delegate model SHA does not match certified evidence")
        if _delegate_family_sha(self.delegate) != str(self.manifest["family_sha256"]):
            raise ValueError("M5E delegate family SHA does not match certification")
        self.oracle_id = (
            f"m5e:{self.state.as_key()}:{str(self.manifest['sha256'])[:16]}:"
            f"{str(route['oracle_id'])}"
        )

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult:
        if state != self.state:
            raise ValueError("M5E certified oracle called for wrong state")
        route = require_certified(self.manifest, state, continuation_values)
        result = self.delegate.evaluate(state, continuation_values)  # type: ignore[attr-defined]
        _checked, continuation_sha = continuation_fingerprint(continuation_values)
        if result.state != state:
            raise AssertionError("M5E delegate returned wrong state")
        if result.continuation_sha256 != continuation_sha:
            raise AssertionError("M5E delegate returned stale continuation SHA")
        if result.oracle_id != str(route["oracle_id"]):
            raise AssertionError("M5E delegate oracle_id drifted after certification")
        return OneHandOracleResult(
            state=state,
            p0_value=float(result.p0_value),
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=int(result.samples),
            standard_error=float(result.standard_error),
        )


def register_certified_fantasy_routes(
    registry: OracleRegistry,
    manifest: Mapping[str, object],
    *,
    fantasy_oracle: object,
) -> int:
    """Overlay only M5E-certified Fantasy/Fantasy routes on an M4Z registry."""
    validate_certification(manifest)
    state_by_key = {state.as_key(): state for state in all_states()}
    count = 0
    for route in manifest["certified_routes"]:  # type: ignore[index]
        state = state_by_key.get(str(route["state"]))
        if state is None:
            raise ValueError("M5E certification references state outside HU catalog")
        _require_fantasy_state(state)
        wrapped = CertifiedFantasyFantasyOracle(fantasy_oracle, state, manifest)
        registry.register(
            state,
            wrapped,
            status=ROUTE_READY_CERTIFIED,
            authority=AUTHORITY,
            implementation_sha256=str(route["implementation_sha256"]),
        )
        count += 1
    return count
