# M5E — exact-V Fantasy/Fantasy route certification

## Purpose

M4X, M4W, M5A and M5B provide the structural pieces needed to evaluate and improve sealed Fantasy/Fantasy play. M5E adds the fail-closed evidence boundary required before any of those approximations may be registered as `READY_CERTIFIED` in a real M4Z Bellman image.

M5E is deliberately bound to one exact continuation SHA. M5D handles outer iteration by rebuilding certificates and the 50-state registry after `V` changes.

## Evidence required per Fantasy/Fantasy route

A passing record freezes:

- exact HU state and exact continuation-vector SHA;
- M4X family SHA and source SHA;
- proof that the evaluated `V` is inside that family region;
- oracle id, model SHA and implementation SHA;
- exact-teacher support gap;
- support-restricted unilateral-deviation gain;
- held-out M4W action-value mean and maximum error;
- state-value standard error;
- positive held-out world and seed counts;
- explicit externally supplied acceptance budgets for every metric;
- independent reference authority and provenance;
- deterministic pass/fail result and record SHA.

M5E never derives a threshold from the sample being judged. Any failed metric blocks certification.

## Certification and runtime firewall

`freeze_certification` accepts only passing, unique route records that match the exact current continuation SHA and the exact M4X family.

`CertifiedFantasyFantasyOracle` rechecks the frozen oracle id, model SHA and family SHA before it can face M4Z. On every evaluation it also rechecks the exact continuation SHA and the delegate result. Any stale vector or model/family/oracle drift is blocked.

`register_certified_fantasy_routes` overlays only individually certified Fantasy/Fantasy states. Missing Fantasy states and all Normal states remain in their previous registry status.

## Strategic boundary

Authority:

`CONTINUATION_SHA_BOUND_HELDOUT_FANTASY_ROUTE_FIREWALL`

M5E is a route certificate, not a global equilibrium certificate. Every evidence and manifest object keeps `promotion_blocked=true`. A real 50-state Bellman step still requires all 18 Normal-containing routes to pass M5C and all 32 Fantasy/Fantasy routes to pass M5E at the same exact continuation vector. M5D then orchestrates the next Bellman step and forces fresh certification after `V` changes.

## Next

Build the held-out Fantasy evidence producer that measures these five metrics from real M4X/M4N/M4W/M5B worlds, then combine M5C and M5E into one per-iterate registry factory for the first real 50-state M5D trace.
