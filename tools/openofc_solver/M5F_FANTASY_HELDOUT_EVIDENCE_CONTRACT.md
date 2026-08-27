# M5F — held-out Fantasy/Fantasy evidence producer

## Purpose

M5E defines the certification firewall. M5F produces the five strategic measurements that firewall consumes from real OpenOFC components.

For every held-out sealed Fantasy/Fantasy world, M5F evaluates the exact current continuation vector against the same M4X robust supports and M4W model intended for the route.

## Production metrics

M5F measures:

- **support gap:** unrestricted exact M4N response utility minus the best action present in the fixed M4X robust support. For each held-out world, both players are audited against every opponent support board and the maximum conditional gap is retained. This is deliberately conservative for mixtures over those boards;
- **support-restricted unilateral deviation:** exact M4P payoff matrix plus the current M4W support policies, reported as total unilateral-deviation gain;
- **M4W action-value MAE and maximum error:** the model's current-V Q predictions are compared with exact M4V continuation-linear action targets built from the exact M4U factorization and the frozen current opponent mixtures;
- **state-value standard error:** chance-world uncertainty of the exact M4P expected profile value under the current M4W support policies.

Every report is bound to the exact state, continuation SHA, M4X family SHA, M4W model SHA and oracle id.

## Threshold separation

`FantasyEvidenceBudgets` is mandatory. M5F has no strategic threshold defaults and never derives a budget from the held-out sample being judged. The caller supplies all five maximum tolerances and M5F forwards the measured quantities and those unchanged limits into M5E.

## CI fixture boundary

The production support-gap evaluator is `exact_support_gap`, which invokes the exact M4N-backed M4X `evaluate_robust_support_at` path.

Tests may inject a lightweight `support_gap_evaluator` only to exercise evidence plumbing deterministically and cheaply. Such a test remains a CI fixture and is not strategic evidence. Real certification artifacts must use the exact production evaluator and real held-out worlds/seeds.

## Authority and promotion boundary

Authority:

`REAL_M4X_M4N_M4P_M4V_M4W_HELDOUT_EVIDENCE_PRODUCER`

M5F does not promote a route or the full strategy. Its report and the M5E record retain `promotion_blocked=true`. A real M5D Bellman step still requires independently passing M5C evidence for every Normal-containing route and M5E evidence generated from real M5F measurements for every Fantasy/Fantasy route at the exact same continuation vector.

## Next

M5G should assemble a per-iterate registry factory that consumes real M5C and M5E artifacts for the exact current `V`, overlays all 50 certified routes on M4Z, and refuses to return a real-ready registry unless route coverage is exactly 50/50 with no stale continuation SHA.
