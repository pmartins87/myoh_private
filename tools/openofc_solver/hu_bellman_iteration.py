from __future__ import annotations

"""Strict 50-state Bellman-image contract and relative-value iteration algebra.

M4T does not solve any one-hand kernel.  It binds one complete set of one-hand
value estimates to the exact continuation vector that produced them, verifies
state/kernel ownership, and performs the gauge-invariant outer relative-value
step required by the HU continuation game.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping

from hu_continuation import (
    HUContinuationState,
    all_states,
    canonical_states,
    hand_kernel_kind,
    normalize_relative_values,
    swap_players,
)
from strategic_continuation_cfr import validate_continuation_values

IMAGE_SCHEMA = "openofc-m4t-bellman-image-v1"
STEP_SCHEMA = "openofc-m4t-relative-value-step-v1"
AUTHORITY = "OUTER_BELLMAN_ALGEBRA_ONLY_KERNEL_VALUES_SUPPLIED"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _state_from_key(key: str) -> HUContinuationState:
    try:
        button, p0, p1 = key.split(":")
        if not button.startswith("B") or not p0.startswith("P0F") or not p1.startswith("P1F"):
            raise ValueError
        return HUContinuationState(int(button[1:]), int(p0[3:]), int(p1[3:]))
    except Exception as exc:
        raise ValueError(f"invalid HU continuation state key: {key!r}") from exc


def continuation_payload(values: Mapping[HUContinuationState, float]) -> dict[str, float]:
    checked = validate_continuation_values(values)
    return {state.as_key(): float(checked[state]) for state in sorted(checked)}


def continuation_sha256(values: Mapping[HUContinuationState, float]) -> str:
    return hashlib.sha256(_canonical_bytes(continuation_payload(values))).hexdigest()


@dataclass(frozen=True)
class BellmanStateEstimate:
    value_p0: float
    kernel_kind: str
    solver_kind: str
    authority: str
    error_bound_abs: float | None = None
    samples: int | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.value_p0):
            raise ValueError("Bellman state value must be finite")
        if not self.kernel_kind or not self.solver_kind or not self.authority:
            raise ValueError("Bellman estimate ownership/authority fields must be non-empty")
        if self.error_bound_abs is not None and (
            not math.isfinite(self.error_bound_abs) or self.error_bound_abs < 0.0
        ):
            raise ValueError("Bellman absolute error bound must be finite and non-negative")
        if self.samples is not None and self.samples < 0:
            raise ValueError("Bellman sample count must be non-negative")

    def payload(self) -> dict:
        return {
            "value_p0": float(self.value_p0),
            "kernel_kind": self.kernel_kind,
            "solver_kind": self.solver_kind,
            "authority": self.authority,
            "error_bound_abs": (
                None if self.error_bound_abs is None else float(self.error_bound_abs)
            ),
            "samples": self.samples,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "BellmanStateEstimate":
        return cls(
            value_p0=float(payload["value_p0"]),
            kernel_kind=str(payload["kernel_kind"]),
            solver_kind=str(payload["solver_kind"]),
            authority=str(payload["authority"]),
            error_bound_abs=(
                None
                if payload.get("error_bound_abs") is None
                else float(payload["error_bound_abs"])
            ),
            samples=(None if payload.get("samples") is None else int(payload["samples"])),
        )


@dataclass(frozen=True)
class BellmanImage:
    iteration: int
    input_values: Mapping[HUContinuationState, float]
    estimates: Mapping[HUContinuationState, BellmanStateEstimate]
    authority: str = AUTHORITY

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("Bellman iteration must be non-negative")
        checked = validate_continuation_values(self.input_values)
        required = set(all_states())
        supplied = set(self.estimates)
        if supplied != required:
            missing = sorted(state.as_key() for state in required - supplied)
            extra = sorted(state.as_key() for state in supplied - required)
            raise ValueError(
                f"Bellman image must contain all 50 state estimates; "
                f"missing={missing[:3]} extra={extra[:3]}"
            )
        estimates = dict(self.estimates)
        for state, estimate in estimates.items():
            expected = hand_kernel_kind(state)
            if estimate.kernel_kind != expected:
                raise ValueError(
                    f"Bellman state {state.as_key()} belongs to {expected}, "
                    f"not {estimate.kernel_kind}"
                )
        object.__setattr__(self, "input_values", checked)
        object.__setattr__(self, "estimates", estimates)

    @property
    def input_fingerprint(self) -> str:
        return continuation_sha256(self.input_values)

    def raw_values(self) -> dict[HUContinuationState, float]:
        return {state: float(self.estimates[state].value_p0) for state in all_states()}

    def payload(self) -> dict:
        base = {
            "schema": IMAGE_SCHEMA,
            "iteration": self.iteration,
            "authority": self.authority,
            "input_values": continuation_payload(self.input_values),
            "input_sha256": self.input_fingerprint,
            "estimates": {
                state.as_key(): self.estimates[state].payload()
                for state in sorted(all_states())
            },
        }
        base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
        return base

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "BellmanImage":
        raw = dict(payload)
        expected = str(raw.pop("sha256", ""))
        if raw.get("schema") != IMAGE_SCHEMA:
            raise ValueError("unsupported Bellman image schema")
        actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
        if expected != actual:
            raise ValueError("Bellman image SHA-256 mismatch")
        raw_values = raw["input_values"]
        raw_estimates = raw["estimates"]
        if not isinstance(raw_values, dict) or not isinstance(raw_estimates, dict):
            raise ValueError("Bellman image mappings are missing")
        values = {_state_from_key(str(key)): float(value) for key, value in raw_values.items()}
        input_sha = continuation_sha256(values)
        if str(raw.get("input_sha256", "")) != input_sha:
            raise ValueError("Bellman image input continuation fingerprint mismatch")
        estimates = {
            _state_from_key(str(key)): BellmanStateEstimate.from_payload(value)
            for key, value in raw_estimates.items()
        }
        return cls(
            iteration=int(raw["iteration"]),
            input_values=values,
            estimates=estimates,
            authority=str(raw["authority"]),
        )


@dataclass(frozen=True)
class ExchangeGaugeDiagnostic:
    pair_sum_mean: float
    pair_sum_spread: float
    gauge_offset_to_antisymmetry: float
    max_antisymmetry_residual_after_projection: float


def exchange_gauge_diagnostic(
    values: Mapping[HUContinuationState, float],
) -> ExchangeGaugeDiagnostic:
    checked = validate_continuation_values(values)
    reps = canonical_states()
    pair_sums = [
        float(checked[state]) + float(checked[swap_players(state)])
        for state in reps
    ]
    mean = sum(pair_sums) / len(pair_sums)
    spread = max(pair_sums) - min(pair_sums)
    offset = 0.5 * mean
    residual = max(
        abs(
            (float(checked[state]) - offset)
            + (float(checked[swap_players(state)]) - offset)
        )
        for state in reps
    )
    return ExchangeGaugeDiagnostic(
        pair_sum_mean=float(mean),
        pair_sum_spread=float(spread),
        gauge_offset_to_antisymmetry=float(offset),
        max_antisymmetry_residual_after_projection=float(residual),
    )


@dataclass(frozen=True)
class RelativeValueStep:
    iteration: int
    reference_state: HUContinuationState
    input_fingerprint: str
    output_fingerprint: str
    gain_estimate: float
    output_values: Mapping[HUContinuationState, float]
    sup_norm_delta: float
    span_delta: float
    normalized_output_error_bound: float | None
    input_exchange: ExchangeGaugeDiagnostic
    output_exchange: ExchangeGaugeDiagnostic
    authority: str = AUTHORITY

    def payload(self) -> dict:
        base = {
            "schema": STEP_SCHEMA,
            "iteration": self.iteration,
            "reference_state": self.reference_state.as_key(),
            "input_fingerprint": self.input_fingerprint,
            "output_fingerprint": self.output_fingerprint,
            "gain_estimate": float(self.gain_estimate),
            "output_values": continuation_payload(self.output_values),
            "sup_norm_delta": float(self.sup_norm_delta),
            "span_delta": float(self.span_delta),
            "normalized_output_error_bound": self.normalized_output_error_bound,
            "input_exchange": self.input_exchange.__dict__,
            "output_exchange": self.output_exchange.__dict__,
            "authority": self.authority,
        }
        base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
        return base


def relative_value_step(
    image: BellmanImage,
    *,
    reference_state: HUContinuationState | None = None,
) -> RelativeValueStep:
    if reference_state is None:
        reference_state = HUContinuationState(0, 0, 0)
    input_values = validate_continuation_values(image.input_values)
    raw_values = image.raw_values()
    _input_anchor, input_normalized = normalize_relative_values(
        input_values, reference=reference_state
    )
    _raw_anchor, output_normalized = normalize_relative_values(
        raw_values, reference=reference_state
    )
    delta = {
        state: float(output_normalized[state]) - float(input_normalized[state])
        for state in all_states()
    }
    sup_delta = max(abs(value) for value in delta.values())
    span_delta = max(delta.values()) - min(delta.values())
    gain = float(raw_values[reference_state]) - float(input_values[reference_state])

    bounds = [image.estimates[state].error_bound_abs for state in all_states()]
    if any(bound is None for bound in bounds):
        normalized_bound = None
    else:
        ref_bound = float(image.estimates[reference_state].error_bound_abs or 0.0)
        normalized_bound = max(float(bound or 0.0) + ref_bound for bound in bounds)

    output_sha = continuation_sha256(output_normalized)
    return RelativeValueStep(
        iteration=image.iteration,
        reference_state=reference_state,
        input_fingerprint=image.input_fingerprint,
        output_fingerprint=output_sha,
        gain_estimate=gain,
        output_values=output_normalized,
        sup_norm_delta=float(sup_delta),
        span_delta=float(span_delta),
        normalized_output_error_bound=normalized_bound,
        input_exchange=exchange_gauge_diagnostic(input_normalized),
        output_exchange=exchange_gauge_diagnostic(output_normalized),
    )
