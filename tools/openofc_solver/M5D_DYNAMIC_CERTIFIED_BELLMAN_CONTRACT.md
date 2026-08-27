# M5D — per-iterate certified outer Bellman orchestration

## Problem closed by M5D

M5C intentionally binds each adaptive Normal route to the exact SHA-256 of the continuation vector used by its held-out evidence. That fail-closed rule is correct, but it means a static M4Z registry cannot simply be reused after a non-trivial Bellman update: the new continuation vector has a different SHA and the old route certificate must become stale.

M5D keeps the strict M5C rule and moves the rebinding responsibility into the outer loop.

For every relative-value iteration M5D:

1. receives the exact current 50-state continuation vector `V_k`;
2. calls a registry factory with that exact vector;
3. requires the returned registry to satisfy M4Z's requested evidence kind;
4. evaluates all 50 states against that same `V_k`;
5. records the continuation SHA, registry-manifest SHA and Bellman-image SHA;
6. normalizes the image into `V_{k+1}`;
7. calls the factory again for `V_{k+1}` rather than reusing the old registry.

No M5C certificate is widened from one SHA to another.

## Real versus fixture execution

`run_dynamic_certified_relative_value_iteration` hard-codes `REAL_BELLMAN_ITERATES`. M4Z therefore still requires every one of the 50 routes returned at every iteration to be `READY_CERTIFIED`.

`run_dynamic_fixture_relative_value_iteration` exists only for deterministic CI and remains visibly tagged `SYNTHETIC_TEST_FIXTURE`. It cannot be mistaken for strategic evidence.

## Dynamic registry bundle

M4Y historically stores a single oracle-manifest SHA for an entire trace. M5D creates an immutable aggregate `DynamicRegistryBundle` containing, for every iteration:

- exact input continuation SHA;
- exact registry-manifest SHA;
- exact Bellman-image SHA.

The bundle SHA is supplied to M4Y as the trace's oracle-manifest pointer. This preserves M4Y's existing trace/family tooling while truthfully representing that the certified route registry may change at every Bellman step.

## Safety boundary

M5D is orchestration only. It does not create strategic evidence, choose acceptance thresholds, upgrade failed routes, or certify Fantasy/Fantasy policy quality. Numerical convergence remains distinct from exploitability/equilibrium quality and `field_promotion_blocked` remains true.

Authority:

`PER_ITERATE_SHA_BOUND_CERTIFIED_BELLMAN_ORCHESTRATOR`

## Next

The remaining blocker for a first real dynamic 50-state trace is route evidence, especially the 32 Fantasy/Fantasy states. The next milestone should create a Fantasy/Fantasy held-out certification boundary compatible with M4X robust supports and M4W/M5B continuation-aware self-play, then provide a registry factory that combines those certificates with M5C Normal-route certificates at each exact Bellman iterate.
