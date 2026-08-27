# M5C — Continuation-SHA-bound Normal route certification

## Purpose

M5B train-at-current-V Normal/Normal and Normal/Fantasy oracles are policy-improvement probes.  M5C is the fail-closed evidence boundary required before any such approximation may enter a real M4Z Bellman image.

A route is eligible only when independent held-out evidence passes explicit externally supplied budgets and is frozen against the exact continuation-vector SHA, oracle configuration SHA, implementation SHA and evidence provenance.  M5C never derives its acceptance threshold from the smoke/evaluation sample being judged.

## Evidence contract

Each route evidence record freezes:

- exact HU continuation state and kernel kind;
- exact continuation-vector SHA-256;
- adaptive oracle id and configuration SHA-256;
- implementation SHA-256;
- model value, independent reference value, absolute error;
- held-out sample count and standard error;
- explicit maximum absolute-value-error and standard-error budgets;
- independent-reference authority and provenance;
- deterministic pass/fail result and record SHA-256.

Failed evidence cannot be inserted into a certification manifest.

## Runtime contract

`CertifiedAdaptiveNormalOracle` checks the certification manifest before every evaluation.  A changed continuation vector, absent state, kernel mismatch, oracle-id drift or tampered manifest blocks evaluation.  Successful delegate results are rechecked for state, continuation SHA and oracle id before being returned to M4Z.

`register_certified_normal_routes` overlays only the individually certified Normal routes on an existing M4Z registry.  All other states remain exactly as they were—normally `BLOCKED`.  Therefore partial M5C evidence cannot accidentally make the 50-state real Bellman image ready.

## Authority boundary

M5C authority is `CONTINUATION_SHA_BOUND_HELDOUT_NORMAL_ROUTE_FIREWALL`.

M5C certifies individual Normal-hand routes only.  Every evidence and certification object keeps `promotion_blocked=true`; it is not a claim that the full OpenOFC strategy is equilibrium-quality or operationally ready.  Fantasy/Fantasy remains under its own M4U/M4X/M5A/M5B evidence chain.  Real M4Z execution still requires all 50 routes to be independently `READY_CERTIFIED`.
