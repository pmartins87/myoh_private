from __future__ import annotations

"""Full 50-state per-V registry factory for M5D.

M5C certifies the 18 states containing at least one Normal player. M5E certifies
the 32 sealed Fantasy/Fantasy states. M5G is the composition boundary: it accepts
only complete exact-V certification packages, overlays both onto M4Z's blocked
baseline, verifies exact 50/50 coverage, and returns the registry factory shape
required by M5D.

M5G does not manufacture evidence. The provider must build fresh artifacts for
the exact continuation vector supplied by M5D. Missing routes, stale SHAs,
duplicate states, wrong kernel counts, delegate drift, or partial certificates
fail closed before a registry can be returned.
"""

from dataclasses import dataclass
from typing import Callable, Mapping

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    hand_kernel_kind,
)
from m4y_bellman_trace import EVIDENCE_REAL
from m4z_outer_bellman import OracleRegistry, default_blocked_registry
from m5c_normal_route_certification import (
    register_certified_normal_routes,
    validate_certification as validate_normal_certification,
)
from m5e_fantasy_route_certification import (
    register_certified_fantasy_routes,
    validate_certification as validate_fantasy_certification,
)

AUTHORITY = "EXACT_V_COMPLETE_50_STATE_CERTIFIED_REGISTRY_FACTORY"
NORMAL_ROUTE_COUNT = 18
FANTASY_ROUTE_COUNT = 32
TOTAL_ROUTE_COUNT = 50


@dataclass(frozen=True)
class PerVRoutePackage:
    normal_manifest: Mapping[str, object]
    fantasy_manifest: Mapping[str, object]
    normal_normal_oracle: object
    normal_fantasy_oracle: object
    fantasy_oracle: object
    provenance: str

    def __post_init__(self) -> None:
        if not str(self.provenance).strip():
            raise ValueError("M5G route package provenance must be non-empty")


RoutePackageProvider = Callable[
    [Mapping[HUContinuationState, float]], PerVRoutePackage
]


def _route_keys(manifest: Mapping[str, object]) -> tuple[str, ...]:
    routes = manifest.get("certified_routes")
    if not isinstance(routes, (list, tuple)):
        raise ValueError("M5G certification route catalog is missing")
    return tuple(str(route["state"]) for route in routes)  # type: ignore[index]


def _expected_route_sets() -> tuple[set[str], set[str]]:
    normal: set[str] = set()
    fantasy: set[str] = set()
    for state in all_states():
        kind = hand_kernel_kind(state)
        if kind in (KERNEL_NORMAL_NORMAL, KERNEL_NORMAL_FANTASY):
            normal.add(state.as_key())
        elif kind == KERNEL_FANTASY_FANTASY:
            fantasy.add(state.as_key())
        else:
            raise AssertionError("unknown HU kernel kind")
    if len(normal) != NORMAL_ROUTE_COUNT or len(fantasy) != FANTASY_ROUTE_COUNT:
        raise AssertionError("M5G expected HU route partition changed")
    return normal, fantasy


def validate_route_package(
    package: PerVRoutePackage,
    continuation_values: Mapping[HUContinuationState, float],
) -> str:
    """Validate exact-V coverage and return the continuation SHA."""
    _checked, continuation_sha = continuation_fingerprint(continuation_values)
    validate_normal_certification(package.normal_manifest)
    validate_fantasy_certification(package.fantasy_manifest)

    if str(package.normal_manifest.get("continuation_sha256", "")) != continuation_sha:
        raise RuntimeError("M5G Normal certification is stale for current V")
    if str(package.fantasy_manifest.get("continuation_sha256", "")) != continuation_sha:
        raise RuntimeError("M5G Fantasy certification is stale for current V")

    normal_keys = _route_keys(package.normal_manifest)
    fantasy_keys = _route_keys(package.fantasy_manifest)
    if len(normal_keys) != len(set(normal_keys)):
        raise RuntimeError("M5G Normal certification contains duplicate routes")
    if len(fantasy_keys) != len(set(fantasy_keys)):
        raise RuntimeError("M5G Fantasy certification contains duplicate routes")
    if set(normal_keys) & set(fantasy_keys):
        raise RuntimeError("M5G Normal/Fantasy certification route sets overlap")

    expected_normal, expected_fantasy = _expected_route_sets()
    if set(normal_keys) != expected_normal:
        missing = sorted(expected_normal - set(normal_keys))
        extra = sorted(set(normal_keys) - expected_normal)
        raise RuntimeError(
            f"M5G Normal route coverage is not 18/18; missing={missing[:3]} extra={extra[:3]}"
        )
    if set(fantasy_keys) != expected_fantasy:
        missing = sorted(expected_fantasy - set(fantasy_keys))
        extra = sorted(set(fantasy_keys) - expected_fantasy)
        raise RuntimeError(
            f"M5G Fantasy route coverage is not 32/32; missing={missing[:3]} extra={extra[:3]}"
        )
    if len(normal_keys) + len(fantasy_keys) != TOTAL_ROUTE_COUNT:
        raise AssertionError("M5G complete route count is not 50")
    return continuation_sha


def assemble_certified_registry(
    package: PerVRoutePackage,
    continuation_values: Mapping[HUContinuationState, float],
) -> OracleRegistry:
    """Overlay an exact complete package and prove M4Z real-readiness."""
    validate_route_package(package, continuation_values)
    registry = default_blocked_registry()
    normal_count = register_certified_normal_routes(
        registry,
        package.normal_manifest,
        normal_normal_oracle=package.normal_normal_oracle,
        normal_fantasy_oracle=package.normal_fantasy_oracle,
    )
    fantasy_count = register_certified_fantasy_routes(
        registry,
        package.fantasy_manifest,
        fantasy_oracle=package.fantasy_oracle,
    )
    if normal_count != NORMAL_ROUTE_COUNT or fantasy_count != FANTASY_ROUTE_COUNT:
        raise AssertionError("M5G registered route cardinality drifted")
    manifest = registry.assert_ready_for(EVIDENCE_REAL)
    if manifest.ready_certified != TOTAL_ROUTE_COUNT or manifest.blocked != 0:
        raise AssertionError("M5G registry failed complete certified coverage")
    return registry


class CompleteCertifiedRegistryFactory:
    """M5D-compatible callable; asks provider for fresh exact-V artifacts each call."""

    authority = AUTHORITY

    def __init__(self, provider: RoutePackageProvider) -> None:
        self.provider = provider
        self.calls = 0
        self.last_continuation_sha256: str | None = None
        self.last_registry_manifest_sha256: str | None = None
        self.last_package_provenance: str | None = None

    def __call__(
        self,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> OracleRegistry:
        _checked, continuation_sha = continuation_fingerprint(continuation_values)
        package = self.provider(continuation_values)
        if not isinstance(package, PerVRoutePackage):
            raise TypeError("M5G provider must return PerVRoutePackage")
        registry = assemble_certified_registry(package, continuation_values)
        frozen = registry.freeze_manifest()
        self.calls += 1
        self.last_continuation_sha256 = continuation_sha
        self.last_registry_manifest_sha256 = frozen.sha256
        self.last_package_provenance = package.provenance
        return registry
