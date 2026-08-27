# M5G — complete exact-V 50-state registry factory

## Purpose

M5D can rebuild the outer Bellman registry after every continuation update. M5C can certify the 18 states containing at least one Normal player, and M5E can certify the 32 sealed Fantasy/Fantasy states. M5G composes those boundaries into the exact callable that M5D needs.

M5G creates no strategic evidence. It accepts a fresh `PerVRoutePackage` for the exact current `V`, verifies complete coverage and only then returns an M4Z registry.

## Exact route partition

The HU catalog is frozen to:

- 2 Normal/Normal routes;
- 16 Normal/Fantasy routes;
- 32 Fantasy/Fantasy routes;
- 50 total routes.

The M5C manifest must contain exactly the first 18 states. The M5E manifest must contain exactly the 32 Fantasy/Fantasy states. Sets must be disjoint and their union must equal the complete M4Z catalog.

## Exact-V rules

Both upstream manifests must carry the SHA-256 of the exact continuation vector supplied to M5G. A package from `V_k` is rejected at `V_{k+1}` even when the latter remains inside an M4X support region.

`CompleteCertifiedRegistryFactory` calls its provider every time M5D calls the factory. Therefore policy/evidence generation may be repeated at every Bellman iterate without weakening the exact-V M5C/M5E firewalls.

## Fail-closed assembly

`assemble_certified_registry` starts from `default_blocked_registry()`, overlays the M5C Normal routes, overlays the M5E Fantasy routes, then calls M4Z's own `assert_ready_for(REAL_BELLMAN_ITERATES)`.

A returned M5G registry must therefore satisfy all of the following simultaneously:

- 18/18 M5C-certified Normal-containing routes;
- 32/32 M5E-certified Fantasy/Fantasy routes;
- 50/50 `READY_CERTIFIED` routes;
- 0 fixture routes;
- 0 blocked routes.

Any missing route, duplicate, overlap, stale continuation SHA, delegate identity drift or malformed upstream certificate prevents the registry from being returned.

## Evidence boundary

Authority:

`EXACT_V_COMPLETE_50_STATE_CERTIFIED_REGISTRY_FACTORY`

CI uses synthetic evidence objects only to test route cardinality and stale-SHA behavior. That does not establish strategic quality. Production use requires M5C records from real independent Normal held-out evaluation and M5E records from real M5F/M4N/M4W held-out evaluation under explicit frozen thresholds.

## Next

The architecture can now represent a fully certified dynamic Bellman iteration. The next work is evidence and scale: create real held-out producers for the Normal routes if any reference path is still missing, generate real M5F evidence for all 32 Fantasy routes, freeze defensible thresholds before judging those samples, and run the first M5D 50-state trace only when M5G can build 50/50 real-certified routes at every iterate.
