from __future__ import annotations

"""Fail-closed per-state Bellman row artifacts and 50-state image assembly.

M4U separates kernel evidence from the outer M4T algebra.  A row is useful only
for the exact continuation vector that generated it. Partial bundles are allowed
for measurement/coverage, while full Bellman-image assembly is certified-only by
default.
"""

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from typing import Mapping, Sequence

from hu_bellman_iteration import (
    BellmanImage,
    BellmanStateEstimate,
    continuation_sha256,
)
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    hand_kernel_kind,
)
from strategic_continuation_cfr import validate_continuation_values

ROW_SCHEMA = "openofc-m4u-bellman-row-v1"
BUNDLE_SCHEMA = "openofc-m4u-bellman-row-bundle-v1"
AUTHORITY = "KERNEL_EVIDENCE_BOUND_BELLMAN_ROW"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_KERNEL_COUNTS = {
    KERNEL_NORMAL_NORMAL: 2,
    KERNEL_NORMAL_FANTASY: 16,
    KERNEL_FANTASY_FANTASY: 32,
}


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


@dataclass(frozen=True)
class BellmanRowArtifact:
    state: HUContinuationState
    input_continuation_fingerprint: str
    value_p0: float
    kernel_kind: str
    solver_kind: str
    authority: str
    evidence_sha256: str
    certified: bool = False
    error_bound_abs: float | None = None
    samples: int | None = None
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kernel_kind != hand_kernel_kind(self.state):
            raise ValueError(
                f"Bellman row kernel mismatch for {self.state.as_key()}: "
                f"{self.kernel_kind} != {hand_kernel_kind(self.state)}"
            )
        if not SHA_RE.match(self.input_continuation_fingerprint):
            raise ValueError("Bellman row continuation fingerprint must be SHA-256 hex")
        if not SHA_RE.match(self.evidence_sha256):
            raise ValueError("Bellman row evidence SHA must be SHA-256 hex")
        if not math.isfinite(self.value_p0):
            raise ValueError("Bellman row value must be finite")
        if not self.solver_kind or not self.authority:
            raise ValueError("Bellman row solver/authority must be non-empty")
        if self.error_bound_abs is not None and (
            not math.isfinite(self.error_bound_abs) or self.error_bound_abs < 0.0
        ):
            raise ValueError("Bellman row error bound must be finite and non-negative")
        if self.certified and self.error_bound_abs is None:
            raise ValueError("certified Bellman row requires an explicit absolute error bound")
        if self.samples is not None and self.samples < 0:
            raise ValueError("Bellman row sample count must be non-negative")
        # Canonical JSON validation also rejects NaN nested in diagnostics.
        _canonical_bytes(dict(self.diagnostics))

    def payload(self) -> dict:
        base = {
            "schema": ROW_SCHEMA,
            "state": self.state.as_key(),
            "input_continuation_fingerprint": self.input_continuation_fingerprint,
            "value_p0": float(self.value_p0),
            "kernel_kind": self.kernel_kind,
            "solver_kind": self.solver_kind,
            "authority": self.authority,
            "evidence_sha256": self.evidence_sha256,
            "certified": bool(self.certified),
            "error_bound_abs": (
                None if self.error_bound_abs is None else float(self.error_bound_abs)
            ),
            "samples": self.samples,
            "diagnostics": dict(self.diagnostics),
        }
        base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
        return base

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "BellmanRowArtifact":
        raw = dict(payload)
        expected = str(raw.pop("sha256", ""))
        if raw.get("schema") != ROW_SCHEMA:
            raise ValueError("unsupported Bellman row schema")
        if expected != hashlib.sha256(_canonical_bytes(raw)).hexdigest():
            raise ValueError("Bellman row SHA-256 mismatch")
        diagnostics = raw.get("diagnostics", {})
        if not isinstance(diagnostics, dict):
            raise ValueError("Bellman row diagnostics must be a mapping")
        return cls(
            state=_state_from_key(str(raw["state"])),
            input_continuation_fingerprint=str(raw["input_continuation_fingerprint"]),
            value_p0=float(raw["value_p0"]),
            kernel_kind=str(raw["kernel_kind"]),
            solver_kind=str(raw["solver_kind"]),
            authority=str(raw["authority"]),
            evidence_sha256=str(raw["evidence_sha256"]),
            certified=bool(raw["certified"]),
            error_bound_abs=(
                None if raw.get("error_bound_abs") is None else float(raw["error_bound_abs"])
            ),
            samples=(None if raw.get("samples") is None else int(raw["samples"])),
            diagnostics=diagnostics,
        )


@dataclass(frozen=True)
class BellmanRowBundle:
    input_continuation_fingerprint: str
    rows: tuple[BellmanRowArtifact, ...]
    source: str
    authority: str = AUTHORITY

    def __post_init__(self) -> None:
        if not SHA_RE.match(self.input_continuation_fingerprint):
            raise ValueError("bundle continuation fingerprint must be SHA-256 hex")
        if not self.source:
            raise ValueError("Bellman row bundle source must be non-empty")
        states = [row.state for row in self.rows]
        if len(states) != len(set(states)):
            raise ValueError("Bellman row bundle contains duplicate states")
        if any(
            row.input_continuation_fingerprint != self.input_continuation_fingerprint
            for row in self.rows
        ):
            raise ValueError("Bellman row bundle mixes continuation fingerprints")

    def payload(self) -> dict:
        base = {
            "schema": BUNDLE_SCHEMA,
            "authority": self.authority,
            "source": self.source,
            "input_continuation_fingerprint": self.input_continuation_fingerprint,
            "rows": [row.payload() for row in sorted(self.rows, key=lambda row: row.state)],
        }
        base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
        return base

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "BellmanRowBundle":
        raw = dict(payload)
        expected = str(raw.pop("sha256", ""))
        if raw.get("schema") != BUNDLE_SCHEMA:
            raise ValueError("unsupported Bellman row bundle schema")
        if expected != hashlib.sha256(_canonical_bytes(raw)).hexdigest():
            raise ValueError("Bellman row bundle SHA-256 mismatch")
        rows_raw = raw.get("rows")
        if not isinstance(rows_raw, list):
            raise ValueError("Bellman row bundle rows missing")
        return cls(
            input_continuation_fingerprint=str(raw["input_continuation_fingerprint"]),
            rows=tuple(BellmanRowArtifact.from_payload(row) for row in rows_raw),
            source=str(raw["source"]),
            authority=str(raw["authority"]),
        )


@dataclass(frozen=True)
class BellmanCoverageReport:
    total_rows: int
    certified_rows: int
    rows_by_kernel: Mapping[str, int]
    certified_by_kernel: Mapping[str, int]
    missing_by_kernel: Mapping[str, tuple[str, ...]]

    @property
    def complete(self) -> bool:
        return self.total_rows == 50 and all(not values for values in self.missing_by_kernel.values())

    @property
    def fully_certified(self) -> bool:
        return self.complete and self.certified_rows == 50


def coverage_report(rows: Sequence[BellmanRowArtifact]) -> BellmanCoverageReport:
    by_state = {row.state: row for row in rows}
    if len(by_state) != len(rows):
        raise ValueError("coverage input contains duplicate states")
    rows_by_kernel = {kind: 0 for kind in EXPECTED_KERNEL_COUNTS}
    certified_by_kernel = {kind: 0 for kind in EXPECTED_KERNEL_COUNTS}
    missing = {kind: [] for kind in EXPECTED_KERNEL_COUNTS}
    for state in all_states():
        kind = hand_kernel_kind(state)
        row = by_state.get(state)
        if row is None:
            missing[kind].append(state.as_key())
        else:
            rows_by_kernel[kind] += 1
            if row.certified:
                certified_by_kernel[kind] += 1
    return BellmanCoverageReport(
        total_rows=len(rows),
        certified_rows=sum(1 for row in rows if row.certified),
        rows_by_kernel=rows_by_kernel,
        certified_by_kernel=certified_by_kernel,
        missing_by_kernel={kind: tuple(values) for kind, values in missing.items()},
    )


def merge_bundles(
    bundles: Sequence[BellmanRowBundle],
    *,
    source: str = "merged-m4u-bundles",
) -> BellmanRowBundle:
    parts = tuple(bundles)
    if not parts:
        raise ValueError("merge requires at least one Bellman row bundle")
    fingerprint = parts[0].input_continuation_fingerprint
    if any(part.input_continuation_fingerprint != fingerprint for part in parts):
        raise ValueError("cannot merge bundles from different continuation vectors")
    rows = tuple(row for part in parts for row in part.rows)
    return BellmanRowBundle(fingerprint, rows, source)


def assemble_bellman_image(
    input_values: Mapping[HUContinuationState, float],
    rows: Sequence[BellmanRowArtifact],
    *,
    iteration: int,
    require_certified: bool = True,
) -> BellmanImage:
    checked = validate_continuation_values(input_values)
    fingerprint = continuation_sha256(checked)
    supplied = tuple(rows)
    report = coverage_report(supplied)
    if not report.complete:
        missing_counts = {
            kind: len(values) for kind, values in report.missing_by_kernel.items() if values
        }
        raise ValueError(f"cannot assemble incomplete 50-state Bellman image: {missing_counts}")
    if any(row.input_continuation_fingerprint != fingerprint for row in supplied):
        raise ValueError("Bellman rows were not generated from the supplied continuation vector")
    if require_certified and not report.fully_certified:
        raise ValueError(
            f"certified Bellman image requires 50 certified rows; have {report.certified_rows}"
        )
    estimates = {
        row.state: BellmanStateEstimate(
            value_p0=row.value_p0,
            kernel_kind=row.kernel_kind,
            solver_kind=row.solver_kind,
            authority=row.authority,
            error_bound_abs=row.error_bound_abs,
            samples=row.samples,
        )
        for row in supplied
    }
    return BellmanImage(iteration=iteration, input_values=checked, estimates=estimates)
