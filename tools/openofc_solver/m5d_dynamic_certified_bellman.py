from __future__ import annotations

"""Per-iterate certified outer Bellman orchestration for OpenOFC HU.

M5C deliberately binds Normal-route evidence to one exact continuation SHA.
That is the correct fail-closed boundary for a route, but it also means a static
M4Z registry cannot survive the first non-trivial Bellman update: V changes and
the old certificate becomes stale.

M5D resolves that orchestration problem without weakening any certificate.  A
registry factory is invoked at every outer iteration with the exact current V.
The returned registry must independently satisfy the requested M4Z evidence
kind before the 50-state image is evaluated.  A SHA-bound bundle records the
registry manifest used for every input continuation vector.

The real entry point forces REAL_BELLMAN_ITERATES.  A fixture entry point exists
only so deterministic CI can exercise the orchestration without manufacturing
strategic evidence.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Callable, Mapping

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    all_states,
    normalize_relative_values,
)
from m4y_bellman_trace import (
    BellmanTrace,
    EVIDENCE_FIXTURE,
    EVIDENCE_KINDS,
    EVIDENCE_REAL,
    freeze_bellman_trace,
)
from m4z_outer_bellman import OracleRegistry, evaluate_bellman_image

BUNDLE_SCHEMA = "openofc-m5d-dynamic-registry-bundle-v1"
RUN_SCHEMA = "openofc-m5d-dynamic-relative-value-run-v1"
AUTHORITY = "PER_ITERATE_SHA_BOUND_CERTIFIED_BELLMAN_ORCHESTRATOR"
EPS = 1e-12

RegistryFactory = Callable[
    [Mapping[HUContinuationState, float]], OracleRegistry
]


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


@dataclass(frozen=True)
class DynamicRegistryStep:
    iteration: int
    continuation_sha256: str
    registry_manifest_sha256: str
    bellman_image_sha256: str

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("M5D registry step iteration cannot be negative")
        for value in (
            self.continuation_sha256,
            self.registry_manifest_sha256,
            self.bellman_image_sha256,
        ):
            if not _is_sha256(value):
                raise ValueError("M5D registry step contains invalid SHA-256")


@dataclass(frozen=True)
class DynamicRegistryBundle:
    steps: tuple[DynamicRegistryStep, ...]
    evidence_kind: str
    sha256: str
    schema: str = BUNDLE_SCHEMA
    authority: str = AUTHORITY

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("M5D registry bundle requires at least one step")
        if self.evidence_kind not in EVIDENCE_KINDS:
            raise ValueError("M5D registry bundle evidence kind is invalid")
        if tuple(step.iteration for step in self.steps) != tuple(range(len(self.steps))):
            raise ValueError("M5D registry bundle iterations must be contiguous from zero")
        if self.sha256 != _sha(self.unsigned_payload()):
            raise ValueError("M5D registry bundle SHA-256 mismatch")

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority": self.authority,
            "evidence_kind": self.evidence_kind,
            "steps": [
                {
                    "iteration": step.iteration,
                    "continuation_sha256": step.continuation_sha256,
                    "registry_manifest_sha256": step.registry_manifest_sha256,
                    "bellman_image_sha256": step.bellman_image_sha256,
                }
                for step in self.steps
            ],
        }


def freeze_registry_bundle(
    steps: tuple[DynamicRegistryStep, ...],
    *,
    evidence_kind: str,
) -> DynamicRegistryBundle:
    if not steps:
        raise ValueError("M5D registry bundle requires steps")
    payload: dict[str, object] = {
        "schema": BUNDLE_SCHEMA,
        "authority": AUTHORITY,
        "evidence_kind": evidence_kind,
        "steps": [
            {
                "iteration": step.iteration,
                "continuation_sha256": step.continuation_sha256,
                "registry_manifest_sha256": step.registry_manifest_sha256,
                "bellman_image_sha256": step.bellman_image_sha256,
            }
            for step in steps
        ],
    }
    return DynamicRegistryBundle(
        steps=steps,
        evidence_kind=evidence_kind,
        sha256=_sha(payload),
    )


@dataclass(frozen=True)
class DynamicRelativeValueStep:
    iteration: int
    input_sha256: str
    registry_manifest_sha256: str
    image_sha256: str
    gain_anchor: float
    residual_linf: float
    output_sha256: str


@dataclass(frozen=True)
class DynamicRelativeValueRun:
    trace: BellmanTrace
    registry_bundle: DynamicRegistryBundle
    steps: tuple[DynamicRelativeValueStep, ...]
    final_values: tuple[tuple[HUContinuationState, float], ...]
    converged_numerically: bool
    tolerance_linf: float
    max_iterations: int
    evidence_kind: str
    provenance: str
    sha256: str
    schema: str = RUN_SCHEMA
    authority: str = AUTHORITY
    field_promotion_blocked: bool = True

    def final_mapping(self) -> dict[HUContinuationState, float]:
        return {state: float(value) for state, value in self.final_values}


def run_dynamic_relative_value_iteration(
    registry_factory: RegistryFactory,
    initial_values: Mapping[HUContinuationState, float],
    *,
    max_iterations: int,
    tolerance_linf: float,
    evidence_kind: str,
    provenance: str,
    normalization_reference: HUContinuationState | None = None,
    minimum_iterations: int = 2,
) -> DynamicRelativeValueRun:
    """Run outer RVI with a freshly gated registry at each exact current V.

    For REAL_BELLMAN_ITERATES every factory result must contain 50
    READY_CERTIFIED routes because M4Z's own `assert_ready_for` remains the
    authority.  M5D never upgrades, relabels, or reuses a stale route.
    """
    if evidence_kind not in EVIDENCE_KINDS:
        raise ValueError("M5D evidence kind is unsupported")
    if max_iterations <= 0 or minimum_iterations <= 0:
        raise ValueError("M5D iteration budgets must be positive")
    if minimum_iterations > max_iterations:
        raise ValueError("M5D minimum_iterations cannot exceed max_iterations")
    if not math.isfinite(float(tolerance_linf)) or tolerance_linf < 0.0:
        raise ValueError("M5D tolerance must be finite/non-negative")
    if not str(provenance).strip():
        raise ValueError("M5D provenance must be non-empty")

    reference = normalization_reference or HUContinuationState(0, 0, 0)
    if reference not in set(all_states()):
        raise ValueError("M5D normalization reference is outside HU catalog")

    checked_initial, _ = continuation_fingerprint(initial_values)
    _initial_gain, current = normalize_relative_values(
        checked_initial, reference=reference
    )
    current, current_sha = continuation_fingerprint(current)

    raw_images: list[Mapping[HUContinuationState, float]] = []
    registry_steps: list[DynamicRegistryStep] = []
    rvi_steps: list[DynamicRelativeValueStep] = []
    converged = False

    for iteration in range(max_iterations):
        # The factory receives exactly the vector whose SHA the route evidence
        # must bind to.  It is called again after every Bellman update.
        registry = registry_factory(current)
        if not isinstance(registry, OracleRegistry):
            raise TypeError("M5D registry factory must return OracleRegistry")
        manifest = registry.assert_ready_for(evidence_kind)
        image = evaluate_bellman_image(
            registry,
            current,
            evidence_kind=evidence_kind,
        )
        if image.continuation_input_sha256 != current_sha:
            raise AssertionError("M5D Bellman image used stale continuation SHA")
        if image.registry_manifest_sha256 != manifest.sha256:
            raise AssertionError("M5D Bellman image registry manifest drifted")

        raw = image.as_mapping()
        gain, normalized = normalize_relative_values(raw, reference=reference)
        normalized, output_sha = continuation_fingerprint(normalized)
        residual = max(
            abs(float(normalized[state]) - float(current[state]))
            for state in all_states()
        )
        if not math.isfinite(residual):
            raise AssertionError("M5D Bellman residual became non-finite")

        raw_images.append(raw)
        registry_steps.append(
            DynamicRegistryStep(
                iteration=iteration,
                continuation_sha256=current_sha,
                registry_manifest_sha256=manifest.sha256,
                bellman_image_sha256=image.sha256,
            )
        )
        rvi_steps.append(
            DynamicRelativeValueStep(
                iteration=iteration,
                input_sha256=current_sha,
                registry_manifest_sha256=manifest.sha256,
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

    bundle = freeze_registry_bundle(
        tuple(registry_steps), evidence_kind=evidence_kind
    )
    # M4Y accepts one SHA pointer for the oracle authority behind a trace.  For
    # M5D that pointer is the immutable aggregate of all per-iterate manifests.
    trace = freeze_bellman_trace(
        raw_images,
        provenance=(
            f"{str(provenance).strip()} | M5D dynamic registry bundle {bundle.sha256}"
        ),
        oracle_manifest_sha256=bundle.sha256,
        evidence_kind=evidence_kind,
        normalization_reference=reference,
    )

    payload: dict[str, object] = {
        "schema": RUN_SCHEMA,
        "authority": AUTHORITY,
        "trace_sha256": trace.sha256,
        "registry_bundle_sha256": bundle.sha256,
        "evidence_kind": evidence_kind,
        "provenance": str(provenance).strip(),
        "tolerance_linf": float(tolerance_linf),
        "max_iterations": int(max_iterations),
        "minimum_iterations": int(minimum_iterations),
        "converged_numerically": bool(converged),
        "field_promotion_blocked": True,
        "steps": [
            {
                "iteration": step.iteration,
                "input_sha256": step.input_sha256,
                "registry_manifest_sha256": step.registry_manifest_sha256,
                "image_sha256": step.image_sha256,
                "gain_anchor": step.gain_anchor,
                "residual_linf": step.residual_linf,
                "output_sha256": step.output_sha256,
            }
            for step in rvi_steps
        ],
    }
    return DynamicRelativeValueRun(
        trace=trace,
        registry_bundle=bundle,
        steps=tuple(rvi_steps),
        final_values=tuple(
            (state, float(current[state])) for state in sorted(current)
        ),
        converged_numerically=converged,
        tolerance_linf=float(tolerance_linf),
        max_iterations=int(max_iterations),
        evidence_kind=evidence_kind,
        provenance=str(provenance).strip(),
        sha256=_sha(payload),
    )


def run_dynamic_certified_relative_value_iteration(
    registry_factory: RegistryFactory,
    initial_values: Mapping[HUContinuationState, float],
    *,
    max_iterations: int,
    tolerance_linf: float,
    provenance: str,
    normalization_reference: HUContinuationState | None = None,
    minimum_iterations: int = 2,
) -> DynamicRelativeValueRun:
    """Production-facing entry point: fixtures are impossible by construction."""
    return run_dynamic_relative_value_iteration(
        registry_factory,
        initial_values,
        max_iterations=max_iterations,
        tolerance_linf=tolerance_linf,
        evidence_kind=EVIDENCE_REAL,
        provenance=provenance,
        normalization_reference=normalization_reference,
        minimum_iterations=minimum_iterations,
    )


def run_dynamic_fixture_relative_value_iteration(
    registry_factory: RegistryFactory,
    initial_values: Mapping[HUContinuationState, float],
    *,
    max_iterations: int,
    tolerance_linf: float,
    provenance: str,
    normalization_reference: HUContinuationState | None = None,
    minimum_iterations: int = 2,
) -> DynamicRelativeValueRun:
    """Regression-only entry point, visibly tagged SYNTHETIC_TEST_FIXTURE."""
    return run_dynamic_relative_value_iteration(
        registry_factory,
        initial_values,
        max_iterations=max_iterations,
        tolerance_linf=tolerance_linf,
        evidence_kind=EVIDENCE_FIXTURE,
        provenance=provenance,
        normalization_reference=normalization_reference,
        minimum_iterations=minimum_iterations,
    )
