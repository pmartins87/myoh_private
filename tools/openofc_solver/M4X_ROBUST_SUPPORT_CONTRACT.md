# OpenOFC M4X — Robust Fantasy/Fantasy Support Across Continuation Regions

## Status

`DECLARED_REGION_BOUND_ONLY_NOT_BELLMAN_TRAJECTORY_CERTIFIED`

M4X is an architectural and mathematical gate. It does **not** promote the
Fantasy/Fantasy policy to runtime authority and does **not** claim that the
outer 50-state Bellman solve will remain inside any region merely because that
region was declared here.

## Why M4X exists

M4O reduces the million-plus Fantasy arrangements to a bounded own-information
candidate support. That support is deliberately bound to the continuation
vector used during proposal generation.

M4V/M4W remove a different problem: once an action already exists in a fixed
support, its value can be transported to a new continuation vector without
re-solving the poker combinatorics.

That still leaves a support-selection failure mode:

1. action `a` is omitted by M4O at `V0`;
2. Bellman changes the continuation vector to `V1`;
3. `a` becomes the best action at `V1`;
4. a continuation-aware value model can revalue retained actions correctly but
   can never choose the omitted action.

M4X attacks this failure mode directly.

## Frozen objects

### Continuation family

`freeze_continuation_family(...)` freezes:

- one or more complete 50-state continuation anchors;
- a common relative-value normalization reference;
- an explicit L-infinity radius around every anchor;
- provenance text;
- a SHA-256 of the evidence/trace manifest from which the family came;
- a deterministic family SHA-256.

All anchors must have the declared reference state equal to zero. This prevents
a meaningless additive bias/gauge shift from looking like strategic movement in
the continuation vector.

A test fixture may use synthetic anchors, but such a fixture is never strategic
evidence. Production use must point `source_sha256` at a preserved Bellman
trace/evidence artifact.

### Robust own-information support

`generate_robust_union_support(...)` calls M4O independently at every frozen
anchor and forms the exact union

`S_union = union_i S_M4O(V_i)`.

The runtime-visible inputs remain only:

- Hero private Fantasy packet;
- public HU continuation meta-state;
- player identity;
- frozen continuation-family metadata and proposal budgets.

The actual hidden opponent packet, completed opponent board, complete world and
payoff matrix are absent from the proposal API.

The union is SHA-bound to:

- the continuation-family SHA;
- the own-information visible fingerprint;
- state/player;
- proposal budgets and base seed;
- all canonical action keys produced at every anchor.

M4X deliberately does not trim the union after construction. A post-union cap
would require a new quality proof because it could remove the very action that
makes the support robust.

## Exact held-out audit

`audit_robust_support(...)` receives a completed opponent board only in the
offline teacher/evaluation path.

For a fixed held-out opponent board M4N provides the unrestricted exact
counterfactual Fantasy frontier. M4N's branchwise immediate optima are
continuation-independent, so the expensive exact frontier is constructed once
and reused for every continuation anchor.

For every anchor `V_i`, M4X measures

`gap_i = Q*_M4N(V_i) - max_{a in S_union} Q_a(V_i)`.

The result is non-negative up to numerical tolerance. Any negative material gap
is treated as an implementation error because a bounded support cannot beat the
unrestricted exact teacher.

## Exact continuation-region extension theorem

For a fixed complete hidden world and a fixed legal Fantasy action,

`Q_a(V) = immediate_a +/- V(next_state)`.

Therefore

`|Q_a(V) - Q_a(W)| <= ||V-W||_inf`.

The maximum over all legal actions is also 1-Lipschitz. The maximum over the
fixed robust support is also 1-Lipschitz. Consequently their difference, the
support gap, is 2-Lipschitz:

`gap(V) <= gap(W) + 2 ||V-W||_inf`.

So, for every vector inside an L-infinity ball of radius `r` around an audited
anchor,

`gap(V) <= gap(anchor) + 2r`.

`robust_support_gap_bound(...)` uses the nearest frozen anchor and the actual
distance of the supplied vector, producing the tighter bound

`gap(V) <= gap(nearest_anchor) + 2 * distance`.

The bound is pointwise in the hidden world. Because it holds pointwise, the same
upper bound also survives averaging over a held-out hidden-world distribution.

## What the theorem does not prove

The theorem does not prove any of the following:

- that the declared continuation family contains the converged Bellman vector;
- that future Bellman iterates stay inside the declared union of balls;
- that the radius is strategically representative;
- that M4O proposal budgets are sufficient;
- that the union remains compact enough for runtime;
- that the learned M4W outcome model is accurate;
- that the resulting sealed policy is an equilibrium.

Those are empirical/solver gates, not consequences of the Lipschitz algebra.

## Production evidence required after this milestone

The next milestone must replace synthetic region choice with real evidence. It
should preserve a SHA-versioned trace of the outer continuation iterates and
measure:

1. distance from every held-out Bellman iterate to the nearest M4X anchor;
2. fraction of iterates inside the declared region;
3. robust-support size distribution;
4. exact M4N support gaps on held-out worlds;
5. theorem upper bounds versus observed off-anchor gaps;
6. M4W immediate/outcome/Q errors on the same continuation region.

Only when the Bellman trajectory itself is shown to remain in a sufficiently
accurate region may this support become an input to continuation-aware fitted
self-play.

## Gate semantics

The executable regression test may print `OPENOFC_M4X_ROBUST_SUPPORT=PASS`.
That means only:

- SHA/gauge family plumbing is deterministic;
- union support remains own-information-only;
- anchor audit is dominated by the exact M4N teacher;
- the L-infinity extension bound is respected by an independent off-anchor
  regression point.

It is **not** a strategic promotion and is **not** permission to run field tests.

## Next milestone

**M4Y — Bellman-trace regional coverage + held-out M4W benchmark**

M4Y should use real continuation iterates/evidence, not hand-picked bonuses, to
freeze a defensible M4X family and measure both robust-support quality and M4W
prediction quality before continuation-aware self-play begins.
