from __future__ import annotations

"""M4Z fail-closed 50-state oracle registry and outer relative-value driver.

The outer HU problem has exactly 50 continuation states. Component solvers are
useful only after every state can be routed to a one-hand value oracle that is
explicitly bound to the current continuation vector. M4Z provides that
orchestration boundary.

No zero-continuation fallback exists. A real Bellman image is refused unless all
50 routes are READY_CERTIFIED. Synthetic fixture routes are accepted only when
the entire run is explicitly tagged SYNTHETIC_TEST_FIXTURE.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Protocol

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    hand_kernel_kind,
    normalize_relative_values,
)
from m4y_bellman_trace import (
    BellmanTrace,
    EVIDENCE_FIXTURE,
    EVIDENCE_REAL,
    freeze_bellman_trace,
)

MANIFEST_SCHEMA = "openofc-m4z-oracle-registry-v1"
IMAGE_SCHEMA = "openofc-m4z-bellman-image-v1"
RVI_SCHEMA = "openofc-m4z-relative-value-run-v1"
AUTHORITY = "FAIL_CLOSED_50_STATE_BELLMAN_ORCHESTRATOR"
ROUTE_BLOCKED = "BLOCKED"
ROUTE_READY_CERTIFIED = "READY_CERTIFIED"
ROUTE_READY_FIXTURE = "READY_FIXTURE"
READY_STATUSES = (ROUTE_READY_CERTIFIED, ROUTE_READY_FIXTURE)
EPS = 1e-12


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: Mapping[str, object]) -> str:
    raw = dict(payload)
    raw.pop("sha256", None)
    return hashlib.sha256(_canonical_bytes(raw)).hexdigest()


def _is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class OneHandOracleResult:
    state: HUContinuationState
    p0_value: float
    continuation_sha256: str
    oracle_id: str
    samples: int = 0
    standard_error: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.p0_value)):
            raise ValueError("one-hand oracle returned non-finite value")
        if not _is_sha256(self.continuation_sha256):
            raise ValueError("one-hand oracle returned invalid continuation SHA")
        if not self.oracle_id:
            raise ValueError("one-hand oracle result requires oracle_id")
        if int(self.samples) < 0:
            raise ValueError("one-hand oracle samples cannot be negative")
        if not math.isfinite(float(self.standard_error)) or float(self.standard_error) < 0.0:
            raise ValueError("one-hand oracle standard error must be finite/non-negative")


class OneHandOracle(Protocol):
    oracle_id: str

    def evaluate(
        self,
        state: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OneHandOracleResult: ...


@dataclass(frozen=True)
class OracleRoute:
    state: HUContinuationState
    kernel_kind: str
    status: str
    oracle_id: str
    authority: str
    implementation_sha256: str
    reason: str


@dataclass(frozen=True)
class OracleRegistryManifest:
    routes: tuple[OracleRoute, ...]
    sha256: str
    schema: str = MANIFEST_SCHEMA
    authority: str = AUTHORITY

    @property
    def ready_certified(self) -> int:
        return sum(route.status == ROUTE_READY_CERTIFIED for route in self.routes)

    @property
    def ready_fixture(self) -> int:
        return sum(route.status == ROUTE_READY_FIXTURE for route in self.routes)

    @property
    def blocked(self) -> int:
        return sum(route.status == ROUTE_BLOCKED for route in self.routes)

    def kernel_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for route in self.routes:
            out[route.kernel_kind] = out.get(route.kernel_kind, 0) + 1
        return out


class OracleRegistry:
    """Mutable construction object; Bellman calls always freeze a manifest first."""

    def __init__(self) -> None:
        self._routes: dict[HUContinuationState, OracleRoute] = {}
        self._oracles: dict[HUContinuationState, OneHandOracle] = {}

    def block(
        self,
        state: HUContinuationState,
        *,
        reason: str,
        authority: str = "NO_CERTIFIED_ONE_HAND_ORACLE",
    ) -> None:
        if state not in set(all_states()):
            raise ValueError("route state is outside HU catalog")
        if not str(reason).strip():
            raise ValueError("blocked route requires a reason")
        self._routes[state] = OracleRoute(
            state=state,
            kernel_kind=hand_kernel_kind(state),
            status=ROUTE_BLOCKED,
            oracle_id="",
            authority=str(authority),
            implementation_sha256="0" * 64,
            reason=str(reason),
        )
        self._oracles.pop(state, None)

    def register(
        self,
        state: HUContinuationState,
        oracle: OneHandOracle,
        *,
        status: str,
        authority: str,
        implementation_sha256: str,
    ) -> None:
        if state not in set(all_states()):
            raise ValueError("route state is outside HU catalog")
        if status not in (ROUTE_READY_CERTIFIED, ROUTE_READY_FIXTURE):
            raise ValueError("ready route must be certified or fixture")
        if not str(authority).strip():
            raise ValueError("ready route requires authority")
        if not _is_sha256(str(implementation_sha256)):
            raise ValueError("ready route requires implementation SHA-256")
        oracle_id = str(getattr(oracle, "oracle_id", ""))
        if not oracle_id:
            raise ValueError("one-hand oracle object requires oracle_id")
        self._routes[state] = OracleRoute(
            state=state,
            kernel_kind=hand_kernel_kind(state),
            status=status,
            oracle_id=oracle_id,
            authority=str(authority),
            implementation_sha256=str(implementation_sha256).lower(),
            reason="",
        )
        self._oracles[state] = oracle

    def freeze_manifest(self) -> OracleRegistryManifest:
        states = all_states()
        missing = [state for state in states if state not in self._routes]
        if missing:
            raise ValueError(f"oracle registry is incomplete: {len(missing)} states missing")
        routes = tuple(self._routes[state] for state in sorted(states))
        payload: dict[str, object] = {
            "schema": MANIFEST_SCHEMA,
            "authority": AUTHORITY,
            "routes": [
                {
                    "state": route.state.as_key(),
                    "kernel_kind": route.kernel_kind,
                    "status": route.status,
                    "oracle_id": route.oracle_id,
                    "route_authority": route.authority,
                    "implementation_sha256": route.implementation_sha256,
                    "reason": route.reason,
                }
                for route in routes
            ],
        }
        return OracleRegistryManifest(routes=routes, sha256=_sha(payload))

    def assert_ready_for(self, evidence_kind: str) -> OracleRegistryManifest:
        manifest = self.freeze_manifest()
        if evidence_kind == EVIDENCE_REAL:
            bad = [
                route for route in manifest.routes
                if route.status != ROUTE_READY_CERTIFIED
            ]
            if bad:
                raise RuntimeError(
                    f"real Bellman image blocked: {len(bad)} routes are not READY_CERTIFIED"
                )
        elif evidence_kind == EVIDENCE_FIXTURE:
            bad = [
                route for route in manifest.routes
                if route.status not in READY_STATUSES
            ]
            if bad:
                raise RuntimeError(
                    f"fixture Bellman image blocked: {len(bad)} routes are not ready"
                )
        else:
            raise ValueError("unsupported Bellman evidence kind")
        return manifest

    def oracle_for(self, state: HUContinuationState) -> OneHandOracle:
        route = self._routes.get(state)
        if route is None or route.status not in READY_STATUSES:
            raise RuntimeError(f"state route is blocked: {state.as_key()}")
        oracle = self._oracles.get(state)
        if oracle is None:
            raise AssertionError("ready route has no oracle object")
        return oracle


def default_blocked_registry() -> OracleRegistry:
    """Truthful current integration baseline: all states present, none fabricated."""
    registry = OracleRegistry()
    for state in all_states():
        kind = hand_kernel_kind(state)
        if kind == KERNEL_NORMAL_NORMAL:
            reason = "NORMAL_NORMAL_STATE_VALUE_ADAPTER_NOT_CERTIFIED"
        elif kind == KERNEL_NORMAL_FANTASY:
            reason = "NORMAL_FANTASY_STATE_VALUE_ADAPTER_NOT_CERTIFIED"
        elif kind == KERNEL_FANTASY_FANTASY:
            reason = "FANTASY_FANTASY_ROBUST_POLICY_STATE_VALUE_NOT_CERTIFIED"
        else:
            raise AssertionError("unknown HU kernel kind")
        registry.block(state, reason=reason)
    return registry


@dataclass(frozen=True)
class BellmanStateEvaluation:
    state: HUContinuationState
    p0_value: float
    oracle_id: str
    samples: int
    standard_error: float


@dataclass(frozen=True)
class BellmanImage:
    continuation_input_sha256: str
    registry_manifest_sha256: str
    evaluations: tuple[BellmanStateEvaluation, ...]
    values: tuple[tuple[HUContinuationState, float], ...]
    sha256: str
    schema: str = IMAGE_SCHEMA
    authority: str = AUTHORITY

    def as_mapping(self) -> dict[HUContinuationState, float]:
        return {state: float(value) for state, value in self.values}


def evaluate_bellman_image(
    registry: OracleRegistry,
    continuation_values: Mapping[HUContinuationState, float],
    *,
    evidence_kind: str,
) -> BellmanImage:
    """Evaluate all 50 routes against exactly one SHA-bound continuation vector."""
    manifest = registry.assert_ready_for(evidence_kind)
    checked, continuation_sha = continuation_fingerprint(continuation_values)

    rows: list[BellmanStateEvaluation] = []
    values: dict[HUContinuationState, float] = {}
    route_by_state = {route.state: route for route in manifest.routes}
    for state in sorted(all_states()):
        route = route_by_state[state]
        oracle = registry.oracle_for(state)
        result = oracle.evaluate(state, checked)
        if result.state != state:
            raise AssertionError("one-hand oracle returned value for wrong state")
        if result.oracle_id != route.oracle_id:
            raise AssertionError("one-hand oracle_id drifted from frozen registry")
        if result.continuation_sha256 != continuation_sha:
            raise AssertionError(
                "one-hand oracle result is not bound to current continuation SHA"
            )
        value = float(result.p0_value)
        if not math.isfinite(value):
            raise AssertionError("one-hand oracle produced non-finite Bellman value")
        values[state] = value
        rows.append(
            BellmanStateEvaluation(
                state=state,
                p0_value=value,
                oracle_id=result.oracle_id,
                samples=int(result.samples),
                standard_error=float(result.standard_error),
            )
        )

    if set(values) != set(all_states()) or len(values) != 50:
        raise AssertionError("Bellman image must contain exactly 50 HU states")
    payload: dict[str, object] = {
        "schema": IMAGE_SCHEMA,
        "authority": AUTHORITY,
        "continuation_input_sha256": continuation_sha,
        "registry_manifest_sha256": manifest.sha256,
        "evaluations": [
            {
                "state": row.state.as_key(),
                "p0_value": row.p0_value,
                "oracle_id": row.oracle_id,
                "samples": row.samples,
                "standard_error": row.standard_error,
            }
            for row in rows
        ],
    }
    return BellmanImage(
        continuation_input_sha256=continuation_sha,
        registry_manifest_sha256=manifest.sha256,
        evaluations=tuple(rows),
        values=tuple((state, values[state]) for state in sorted(values)),
        sha256=_sha(payload),
    )


@dataclass(frozen=True)
class RelativeValueStep:
    iteration: int
    input_sha256: str
    image_sha256: str
    gain_anchor: float
    residual_linf: float
    output_sha256: str


@dataclass(frozen=True)
class RelativeValueRun:
    trace: BellmanTrace
    registry_manifest_sha256: str
    steps: tuple[RelativeValueStep, ...]
    final_values: tuple[tuple[HUContinuationState, float], ...]
    converged_numerically: bool
    tolerance_linf: float
    max_iterations: int
    sha256: str
    schema: str = RVI_SCHEMA
    authority: str = AUTHORITY
    field_promotion_blocked: bool = True

    def final_mapping(self) -> dict[HUContinuationState, float]:
        return {state: float(value) for state, value in self.final_values}


def run_relative_value_iteration(
    registry: OracleRegistry,
    initial_values: Mapping[HUContinuationState, float],
    *,
    max_iterations: int,
    tolerance_linf: float,
    evidence_kind: str,
    provenance: str,
    normalization_reference: HUContinuationState | None = None,
    minimum_iterations: int = 2,
) -> RelativeValueRun:
    """Run complete fail-closed relative-value iteration and emit an M4Y trace.

    Numerical residual convergence is recorded, never interpreted as strategic
    correctness by this layer.
    """
    if max_iterations <= 0 or minimum_iterations <= 0:
        raise ValueError("M4Z iteration budgets must be positive")
    if minimum_iterations > max_iterations:
        raise ValueError("minimum_iterations cannot exceed max_iterations")
    if not math.isfinite(float(tolerance_linf)) or tolerance_linf < 0.0:
        raise ValueError("M4Z tolerance must be finite/non-negative")
    if not str(provenance).strip():
        raise ValueError("M4Z run provenance must be non-empty")

    reference = normalization_reference or HUContinuationState(0, 0, 0)
    checked_initial, _ = continuation_fingerprint(initial_values)
    _initial_anchor, current = normalize_relative_values(
        checked_initial, reference=reference
    )
    current, current_sha = continuation_fingerprint(current)
    manifest = registry.assert_ready_for(evidence_kind)

    images: list[Mapping[HUContinuationState, float]] = []
    steps: list[RelativeValueStep] = []
    converged = False

    for iteration in range(max_iterations):
        image = evaluate_bellman_image(
            registry, current, evidence_kind=evidence_kind
        )
        raw = image.as_mapping()
        gain, normalized = normalize_relative_values(raw, reference=reference)
        normalized, output_sha = continuation_fingerprint(normalized)
        residual = max(
            abs(float(normalized[state]) - float(current[state]))
            for state in all_states()
        )
        images.append(raw)
        steps.append(
            RelativeValueStep(
                iteration=iteration,
                input_sha256=current_sha,
                image_sha256=image.sha256,
                gain_anchor=float(gain),
                residual_linf=float(residual),
                output_sha256=output_sha,
            )
        )
        current = normalized
        current_sha = output_sha
        if iteration + 1 >= minimum_iterations and residual <= tolerance_linf + EPS:
            converged = True
            break

    trace = freeze_bellman_trace(
        images,
        provenance=str(provenance),
        oracle_manifest_sha256=manifest.sha256,
        evidence_kind=evidence_kind,
        normalization_reference=reference,
    )
    payload: dict[str, object] = {
        "schema": RVI_SCHEMA,
        "authority": AUTHORITY,
        "trace_sha256": trace.sha256,
        "registry_manifest_sha256": manifest.sha256,
        "tolerance_linf": float(tolerance_linf),
        "max_iterations": int(max_iterations),
        "minimum_iterations": int(minimum_iterations),
        "converged_numerically": converged,
        "field_promotion_blocked": True,
        "steps": [
            {
                "iteration": step.iteration,
                "input_sha256": step.input_sha256,
                "image_sha256": step.image_sha256,
                "gain_anchor": step.gain_anchor,
                "residual_linf": step.residual_linf,
                "output_sha256": step.output_sha256,
            }
            for step in steps
        ],
    }
    return RelativeValueRun(
        trace=trace,
        registry_manifest_sha256=manifest.sha256,
        steps=tuple(steps),
        final_values=tuple((state, float(current[state])) for state in sorted(current)),
        converged_numerically=converged,
        tolerance_linf=float(tolerance_linf),
        max_iterations=int(max_iterations),
        sha256=_sha(payload),
    )
