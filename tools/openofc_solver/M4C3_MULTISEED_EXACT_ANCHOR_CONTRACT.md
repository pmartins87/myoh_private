# M4C3 — multiseed generalization + Bellman-safe exact R4 anchors

## Why this milestone exists

M4C2 created the first bounded state×action model and deterministic replay. Its smoke test proves plumbing, not strategic quality. M4C3 adds the first benchmark that can tell whether the representation generalizes across independent deal seeds and whether it learns a subset of decisions whose optimal labels are mathematically exact even before the Fantasy continuation vector is solved.

The next field test remains deferred. M4C3 is intelligence work only.

## Two independent evaluation surfaces

### 1. Exact-tabular MCCFR holdout

For every independent deal seed, the suit-canonical unabstracted MCCFR solver remains the policy teacher. A SHA-256 split reserves one fifth of exact information states from training. The bounded model is evaluated only on those disjoint states.

This measures generalization to unseen information states. It is **not** an exploitability certificate because the tabular teacher itself is still strategically approximate at finite sampling.

### 2. Bellman-safe dealer-R4 anchors

Dealer/button R4 is special: the non-dealer has already completed a public 13-card board, Hero has 11 placed cards plus a known private 3-card packet, and every legal Hero completion can be exhaustively evaluated.

A current-hand R4 optimum is not automatically a long-horizon optimum because an action may trade immediate points for a different Fantasy state. M4C3 therefore promotes an R4 state to an exact training anchor only when **every legal action produces the same Hero next-hand Fantasy mode**.

In that subset, the opponent terminal board and next button are fixed and the Hero Fantasy mode is action-invariant. Therefore the whole next meta-state is identical for all actions and

`argmax_a [points(a) + V(next_state)] = argmax_a points(a)`

for every possible continuation vector `V`.

These labels are exact under the full cross-hand objective without inventing any Fantasy bonus.

Transition-variant R4 states remain diagnostics only and are never injected as exact training labels.

## Exact-anchor metrics

Held-out continuation-invariant R4 states report:

- top-1 hit against the exact optimal-action set;
- probability mass assigned to exact-optimal actions;
- greedy point regret;
- expected point regret under the model policy;
- uniform-policy regret as a baseline.

The held-out split uses the same stable SHA-256 state partition as M4C2, so no exact R4 holdout state is admitted to replay.

## Multiseed benchmark

`strategic_multiseed_benchmark.py` trains one bounded model from multiple independent suit-canonical MCCFR teachers plus non-holdout Bellman-safe R4 anchors. It then reports policy and exact-anchor metrics separately for every seed and aggregate means.

The benchmark is deterministic for a fixed configuration and emits a canonical SHA-256 report fingerprint.

The CI smoke run intentionally sets `promotion_ready=false`. Numerical promotion thresholds will be frozen only after the first larger Ryzen baseline establishes variance across seeds. This prevents selecting a convenient threshold after seeing one small result.

## Ryzen baseline sequence

The first practical baseline should run at least five distinct seeds. A recommended starting point is:

```powershell
python tools/openofc_solver/apply_m1b_joker_semantics.py
python tools/openofc_solver/strategic_multiseed_benchmark.py `
  --seeds 20260826,20260827,20260828,20260829,20260830 `
  --cfr-iterations 2000 `
  --teacher-nodes 20000 `
  --r4-train 64 `
  --r4-holdout 32 `
  --replay-capacity 250000 `
  --epochs 6 `
  --buckets 65536 `
  --output m4c3_ryzen_baseline.json
```

This is a baseline, not a commitment to an arbitrarily huge run. CPU time, RAM, replay occupancy, held-out metrics and seed variance are inspected before increasing the budget.

## Promotion path after the baseline

1. freeze quality/stability thresholds from the multi-seed baseline protocol;
2. increase capacity only where metrics show underfitting rather than blindly increasing compute;
3. couple the distillation teacher to the M4B continuation objective once the continuation vector is available;
4. add certified R3 anchors only when their label is valid under the same continuation objective;
5. run sampled unabstracted best-response/exploitability diagnostics;
6. distill to a runtime policy with exact/safe fallback outside the certified envelope;
7. only then build the next field-test executable.
