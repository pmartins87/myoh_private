# M4Z — fail-closed 50-state oracle registry and outer relative-value driver

## Purpose

M4Y can consume real Bellman iterates, but the repository did not yet have a
single component that could truthfully produce a complete 50-state Bellman
image. M4Z creates that integration boundary.

## State surface

The registry is total over the exact HU catalog:

- 2 Normal×Normal states;
- 16 Normal×Fantasy asymmetric states;
- 32 Fantasy×Fantasy sealed states.

Every state has exactly one explicit route. A route is either blocked,
`READY_CERTIFIED`, or `READY_FIXTURE`.

## Fail-closed rules

A `REAL_BELLMAN_ITERATES` image requires **all 50** routes to be
`READY_CERTIFIED`.

`READY_FIXTURE` exists only for deterministic regression tests. A fixture route
cannot be relabelled as real evidence.

Every one-hand result must return the SHA-256 of the exact continuation vector it
used. M4Z rejects a result if that SHA differs from the vector supplied to the
50-state image. There is no implicit zero-continuation substitute.

## Relative-value iteration

`run_relative_value_iteration`:

1. validates and gauge-normalizes the current 50-state vector;
2. evaluates one complete 50-state Bellman image against that same vector;
3. normalizes the image at the declared reference state;
4. records the L∞ residual and gain anchor;
5. repeats until budget exhaustion or numerical tolerance;
6. emits the raw images through M4Y as a SHA-bound trace.

`converged_numerically` means only that the normalized iterate residual reached
the requested tolerance. It is not an exploitability or strategic certificate.

`field_promotion_blocked` is always true at M4Z.

## Current integration baseline

`default_blocked_registry()` intentionally exposes the present truth:

- Normal×Normal: component solver exists, state-value adapter not certified;
- Normal×Fantasy: component solver exists, state-value adapter not certified;
- Fantasy×Fantasy: M4W/M4X plumbing exists, robust policy/state-value route not
  certified.

The outer driver is therefore ready to orchestrate, while a real 50-state run
is still blocked. This is deliberate.

## Next milestone — M5A

Build fixed-policy state-value adapters for the three kernel classes and an
offline certification harness:

- Normal×Normal average-policy evaluator under arbitrary current V;
- Normal×Fantasy average-policy evaluator under arbitrary current V;
- Fantasy×Fantasy continuation-aware M4W policy over M4X robust supports;
- per-route held-out error/deviation provenance;
- only certified route manifests may flip from `BLOCKED` to
  `READY_CERTIFIED`.

The first real M4Y Bellman trace must be emitted only after those adapters are
available for all 50 states.
