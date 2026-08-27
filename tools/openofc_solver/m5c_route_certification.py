from __future__ import annotations

"""M5C fail-closed held-out certification for M4Z one-hand routes.

M5A/M5B make the three HU kernel classes evaluable and improvable at a supplied
continuation vector.  Existence, training loss, or in-sample policy imitation do
not make a route strategically trustworthy.  M5C is the promotion firewall:
only independent held-out evidence, explicit externally supplied thresholds and
SHA-bound provenance can produce a READY_CERTIFIED route.

No strategic threshold is hard-coded here.  Missing metrics fail closed.
Synthetic/test evidence can exercise the logic but can never be registered into
a REAL M4Z Bellman registry.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    hand_kernel_kind,
)
from m4z_outer_bellman import (
    OneHandOracle,
    OracleRegistry,
    ROUTE_READY_CERTIFIED,
)

THRESHOLD_SCHEMA = "openofc-m5c-strategic-thresholds-v1"
EVIDENCE_SCHEMA = "openofc-m5c-heldout-route-evidence-v1"
CERT_SCHEMA = "openofc-m5c-route-certificate-v1"
AUTHORITY = "HELDOUT_STRATEGIC_ROUTE_CERTIFICATION_FIREWALL"
STATUS_READY = "READY_CERTIFIED"
STATUS_BLOCKED = "BLOCKED"
STATUS_TEST_ONLY = "READY_TEST_ONLY"
EVIDENCE_HELDOUT = "HELD_OUT"
EVIDENCE_TEST = "SYNTHETIC_TEST_ONLY"
SUPPORTED_KERNELS = (
    KERNEL_NORMAL_NORMAL,
    KERNEL_NORMAL_FANTASY,
    KERNEL_FANTASY_FANTASY,
)


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: Mapping[str, object]) -> str:
    raw = dict(payload)
    raw.pop("sha256", None)
    return hashlib.sha256(_canonical_bytes(raw)).hexdigest()


def _require_sha(value: str, label: str) -> str:
    text = str(value).lower()
    if len(text) != 64:
        raise ValueError(f"{label} must be a SHA-256")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be a SHA-256") from exc
    return text


def _finite_nonnegative(value: float, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{label} must be finite and non-negative")
    return number


@dataclass(frozen=True)
class KernelThresholds:
    """Explicit acceptance budget for one kernel class.

    support_gap and model_q_error are mandatory only for Fantasy/Fantasy.
    policy imitation metrics are intentionally absent: they are useful
    diagnostics but not strategic promotion criteria.
    """

    min_heldout_seeds: int
    min_heldout_samples: int
    max_value_standard_error: float
    max_unilateral_deviation: float
    max_support_gap: float | None = None
    max_model_q_error: float | None = None

    def __post_init__(self) -> None:
        if self.min_heldout_seeds <= 0 or self.min_heldout_samples <= 0:
            raise ValueError("held-out seed/sample thresholds must be positive")
        _finite_nonnegative(
            self.max_value_standard_error, "max_value_standard_error"
        )
        _finite_nonnegative(
            self.max_unilateral_deviation, "max_unilateral_deviation"
        )
        if self.max_support_gap is not None:
            _finite_nonnegative(self.max_support_gap, "max_support_gap")
        if self.max_model_q_error is not None:
            _finite_nonnegative(self.max_model_q_error, "max_model_q_error")

    def payload(self) -> dict[str, object]:
        return {
            "min_heldout_seeds": int(self.min_heldout_seeds),
            "min_heldout_samples": int(self.min_heldout_samples),
            "max_value_standard_error": float(self.max_value_standard_error),
            "max_unilateral_deviation": float(self.max_unilateral_deviation),
            "max_support_gap": (
                None if self.max_support_gap is None else float(self.max_support_gap)
            ),
            "max_model_q_error": (
                None if self.max_model_q_error is None else float(self.max_model_q_error)
            ),
        }


@dataclass(frozen=True)
class StrategicThresholdManifest:
    normal_normal: KernelThresholds
    normal_fantasy: KernelThresholds
    fantasy_fantasy: KernelThresholds
    provenance: str
    sha256: str
    schema: str = THRESHOLD_SCHEMA

    def __post_init__(self) -> None:
        if not str(self.provenance).strip():
            raise ValueError("threshold provenance must be non-empty")
        if self.schema != THRESHOLD_SCHEMA:
            raise ValueError("unsupported M5C threshold schema")
        if self.fantasy_fantasy.max_support_gap is None:
            raise ValueError("Fantasy/Fantasy thresholds require max_support_gap")
        if self.fantasy_fantasy.max_model_q_error is None:
            raise ValueError("Fantasy/Fantasy thresholds require max_model_q_error")
        if self.sha256 != _sha(self.unsigned_payload()):
            raise ValueError("M5C threshold manifest SHA mismatch")

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "provenance": self.provenance,
            "kernels": {
                KERNEL_NORMAL_NORMAL: self.normal_normal.payload(),
                KERNEL_NORMAL_FANTASY: self.normal_fantasy.payload(),
                KERNEL_FANTASY_FANTASY: self.fantasy_fantasy.payload(),
            },
        }

    def for_kernel(self, kernel: str) -> KernelThresholds:
        if kernel == KERNEL_NORMAL_NORMAL:
            return self.normal_normal
        if kernel == KERNEL_NORMAL_FANTASY:
            return self.normal_fantasy
        if kernel == KERNEL_FANTASY_FANTASY:
            return self.fantasy_fantasy
        raise ValueError("unsupported M5C kernel")


def freeze_threshold_manifest(
    *,
    normal_normal: KernelThresholds,
    normal_fantasy: KernelThresholds,
    fantasy_fantasy: KernelThresholds,
    provenance: str,
) -> StrategicThresholdManifest:
    payload: dict[str, object] = {
        "schema": THRESHOLD_SCHEMA,
        "provenance": str(provenance),
        "kernels": {
            KERNEL_NORMAL_NORMAL: normal_normal.payload(),
            KERNEL_NORMAL_FANTASY: normal_fantasy.payload(),
            KERNEL_FANTASY_FANTASY: fantasy_fantasy.payload(),
        },
    }
    return StrategicThresholdManifest(
        normal_normal=normal_normal,
        normal_fantasy=normal_fantasy,
        fantasy_fantasy=fantasy_fantasy,
        provenance=str(provenance),
        sha256=_sha(payload),
    )


@dataclass(frozen=True)
class HeldoutRouteEvidence:
    state: HUContinuationState
    kernel_kind: str
    oracle_id: str
    implementation_sha256: str
    continuation_evidence_sha256: str
    heldout_seed_ids: tuple[str, ...]
    heldout_samples: int
    value_standard_error: float
    max_unilateral_deviation: float
    support_gap: float | None
    model_q_error: float | None
    evidence_kind: str
    provenance: str
    sha256: str
    schema: str = EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVIDENCE_SCHEMA:
            raise ValueError("unsupported M5C evidence schema")
        if self.state not in set(all_states()):
            raise ValueError("M5C evidence state is outside HU catalog")
        if self.kernel_kind != hand_kernel_kind(self.state):
            raise ValueError("M5C evidence kernel/state mismatch")
        if self.kernel_kind not in SUPPORTED_KERNELS:
            raise ValueError("unsupported M5C evidence kernel")
        if not self.oracle_id or not str(self.provenance).strip():
            raise ValueError("M5C evidence requires oracle_id and provenance")
        _require_sha(self.implementation_sha256, "implementation_sha256")
        _require_sha(
            self.continuation_evidence_sha256, "continuation_evidence_sha256"
        )
        if self.evidence_kind not in (EVIDENCE_HELDOUT, EVIDENCE_TEST):
            raise ValueError("unsupported M5C evidence kind")
        if self.heldout_samples <= 0:
            raise ValueError("M5C evidence requires positive held-out samples")
        if not self.heldout_seed_ids or len(set(self.heldout_seed_ids)) != len(
            self.heldout_seed_ids
        ):
            raise ValueError("M5C held-out seed ids must be unique and non-empty")
        _finite_nonnegative(self.value_standard_error, "value_standard_error")
        _finite_nonnegative(
            self.max_unilateral_deviation, "max_unilateral_deviation"
        )
        if self.support_gap is not None:
            _finite_nonnegative(self.support_gap, "support_gap")
        if self.model_q_error is not None:
            _finite_nonnegative(self.model_q_error, "model_q_error")
        if self.kernel_kind == KERNEL_FANTASY_FANTASY:
            if self.support_gap is None or self.model_q_error is None:
                raise ValueError(
                    "Fantasy/Fantasy held-out evidence requires support_gap and model_q_error"
                )
        if self.sha256 != _sha(self.unsigned_payload()):
            raise ValueError("M5C evidence SHA mismatch")

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "state": self.state.as_key(),
            "kernel_kind": self.kernel_kind,
            "oracle_id": self.oracle_id,
            "implementation_sha256": self.implementation_sha256,
            "continuation_evidence_sha256": self.continuation_evidence_sha256,
            "heldout_seed_ids": list(self.heldout_seed_ids),
            "heldout_samples": int(self.heldout_samples),
            "value_standard_error": float(self.value_standard_error),
            "max_unilateral_deviation": float(self.max_unilateral_deviation),
            "support_gap": (
                None if self.support_gap is None else float(self.support_gap)
            ),
            "model_q_error": (
                None if self.model_q_error is None else float(self.model_q_error)
            ),
            "evidence_kind": self.evidence_kind,
            "provenance": self.provenance,
        }


def freeze_route_evidence(
    *,
    state: HUContinuationState,
    oracle_id: str,
    implementation_sha256: str,
    continuation_evidence_sha256: str,
    heldout_seed_ids: Sequence[str],
    heldout_samples: int,
    value_standard_error: float,
    max_unilateral_deviation: float,
    support_gap: float | None = None,
    model_q_error: float | None = None,
    evidence_kind: str = EVIDENCE_HELDOUT,
    provenance: str,
) -> HeldoutRouteEvidence:
    kernel = hand_kernel_kind(state)
    payload: dict[str, object] = {
        "schema": EVIDENCE_SCHEMA,
        "state": state.as_key(),
        "kernel_kind": kernel,
        "oracle_id": str(oracle_id),
        "implementation_sha256": str(implementation_sha256).lower(),
        "continuation_evidence_sha256": str(continuation_evidence_sha256).lower(),
        "heldout_seed_ids": [str(x) for x in heldout_seed_ids],
        "heldout_samples": int(heldout_samples),
        "value_standard_error": float(value_standard_error),
        "max_unilateral_deviation": float(max_unilateral_deviation),
        "support_gap": None if support_gap is None else float(support_gap),
        "model_q_error": None if model_q_error is None else float(model_q_error),
        "evidence_kind": str(evidence_kind),
        "provenance": str(provenance),
    }
    return HeldoutRouteEvidence(
        state=state,
        kernel_kind=kernel,
        oracle_id=str(oracle_id),
        implementation_sha256=str(implementation_sha256).lower(),
        continuation_evidence_sha256=str(continuation_evidence_sha256).lower(),
        heldout_seed_ids=tuple(str(x) for x in heldout_seed_ids),
        heldout_samples=int(heldout_samples),
        value_standard_error=float(value_standard_error),
        max_unilateral_deviation=float(max_unilateral_deviation),
        support_gap=None if support_gap is None else float(support_gap),
        model_q_error=None if model_q_error is None else float(model_q_error),
        evidence_kind=str(evidence_kind),
        provenance=str(provenance),
        sha256=_sha(payload),
    )


@dataclass(frozen=True)
class RouteCertificate:
    state: HUContinuationState
    kernel_kind: str
    oracle_id: str
    implementation_sha256: str
    evidence_sha256: str
    threshold_sha256: str
    status: str
    failures: tuple[str, ...]
    sha256: str
    schema: str = CERT_SCHEMA
    authority: str = AUTHORITY

    @property
    def ready_for_real_bellman(self) -> bool:
        return self.status == STATUS_READY and not self.failures


def certify_route(
    evidence: HeldoutRouteEvidence,
    thresholds: StrategicThresholdManifest,
) -> RouteCertificate:
    budget = thresholds.for_kernel(evidence.kernel_kind)
    failures: list[str] = []
    if evidence.evidence_kind != EVIDENCE_HELDOUT:
        failures.append("EVIDENCE_NOT_INDEPENDENT_HELDOUT")
    if len(evidence.heldout_seed_ids) < budget.min_heldout_seeds:
        failures.append("INSUFFICIENT_HELDOUT_SEEDS")
    if evidence.heldout_samples < budget.min_heldout_samples:
        failures.append("INSUFFICIENT_HELDOUT_SAMPLES")
    if evidence.value_standard_error > budget.max_value_standard_error:
        failures.append("VALUE_STANDARD_ERROR_EXCEEDS_THRESHOLD")
    if evidence.max_unilateral_deviation > budget.max_unilateral_deviation:
        failures.append("UNILATERAL_DEVIATION_EXCEEDS_THRESHOLD")
    if evidence.kernel_kind == KERNEL_FANTASY_FANTASY:
        if evidence.support_gap is None:
            failures.append("SUPPORT_GAP_MISSING")
        elif evidence.support_gap > float(budget.max_support_gap):
            failures.append("SUPPORT_GAP_EXCEEDS_THRESHOLD")
        if evidence.model_q_error is None:
            failures.append("MODEL_Q_ERROR_MISSING")
        elif evidence.model_q_error > float(budget.max_model_q_error):
            failures.append("MODEL_Q_ERROR_EXCEEDS_THRESHOLD")

    if evidence.evidence_kind == EVIDENCE_TEST and not failures:
        status = STATUS_TEST_ONLY
    else:
        status = STATUS_READY if not failures else STATUS_BLOCKED
    payload: dict[str, object] = {
        "schema": CERT_SCHEMA,
        "authority": AUTHORITY,
        "state": evidence.state.as_key(),
        "kernel_kind": evidence.kernel_kind,
        "oracle_id": evidence.oracle_id,
        "implementation_sha256": evidence.implementation_sha256,
        "evidence_sha256": evidence.sha256,
        "threshold_sha256": thresholds.sha256,
        "status": status,
        "failures": sorted(failures),
    }
    return RouteCertificate(
        state=evidence.state,
        kernel_kind=evidence.kernel_kind,
        oracle_id=evidence.oracle_id,
        implementation_sha256=evidence.implementation_sha256,
        evidence_sha256=evidence.sha256,
        threshold_sha256=thresholds.sha256,
        status=status,
        failures=tuple(sorted(failures)),
        sha256=_sha(payload),
    )


def register_certified_route(
    registry: OracleRegistry,
    oracle: OneHandOracle,
    certificate: RouteCertificate,
) -> None:
    """Promote exactly one route; test-only or blocked certificates are refused."""

    if not certificate.ready_for_real_bellman:
        raise RuntimeError("M5C certificate is not eligible for REAL Bellman routing")
    oracle_id = str(getattr(oracle, "oracle_id", ""))
    if oracle_id != certificate.oracle_id:
        raise ValueError("M5C certificate/oracle identity mismatch")
    if certificate.kernel_kind != hand_kernel_kind(certificate.state):
        raise ValueError("M5C certificate kernel/state mismatch")
    registry.register(
        certificate.state,
        oracle,
        status=ROUTE_READY_CERTIFIED,
        authority=certificate.authority,
        implementation_sha256=certificate.implementation_sha256,
    )


def certification_summary(
    certificates: Sequence[RouteCertificate],
) -> dict[str, object]:
    rows = tuple(certificates)
    by_status: dict[str, int] = {}
    by_kernel: dict[str, dict[str, int]] = {}
    for cert in rows:
        by_status[cert.status] = by_status.get(cert.status, 0) + 1
        kernel_row = by_kernel.setdefault(cert.kernel_kind, {})
        kernel_row[cert.status] = kernel_row.get(cert.status, 0) + 1
    return {
        "schema": CERT_SCHEMA,
        "authority": AUTHORITY,
        "certificates": len(rows),
        "ready_for_real_bellman": sum(c.ready_for_real_bellman for c in rows),
        "by_status": dict(sorted(by_status.items())),
        "by_kernel": {
            key: dict(sorted(value.items())) for key, value in sorted(by_kernel.items())
        },
        "complete_50_state_surface": (
            len(rows) == len(all_states())
            and {c.state for c in rows} == set(all_states())
        ),
    }
