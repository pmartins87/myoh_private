# Ryzen strategic HU training — execution contract

This run is deliberately separate from the v5.8.1 field executable.  It trains
an offline full-action strategy and cannot change live clicks until convergence,
continuation value and production-loss gates pass.

## Why this run exists

The previous R3/R4 teacher pipeline is exact or sampled under an explicit
card-blind hidden-card belief.  It is valuable for leaf auditing, but once early
placements become strategic those public actions carry information about hidden
cards.  The global solver therefore learns all HU normal-hand information sets
jointly with outcome-sampling MCCFR.

The v2 runner fixes an important scaling requirement: every checkpoint contains
the exact PRNG state.  `N` uninterrupted iterations and `N1 + resume + N2`
iterations are required to produce the same solver state when `N=N1+N2`.
Every checkpoint is SHA-256 protected and atomically replaced.

## Safe smoke before the long run

From the repository root:

```bash
python tools/openofc_solver/apply_m1b_joker_semantics.py
python tools/openofc_solver/test_strategic_cfr.py
python tools/openofc_solver/test_strategic_runner.py
python tools/openofc_solver/strategic_cfr_runner.py \
  --iterations 1000 \
  --checkpoint-every 250 \
  --checkpoint runs/strategic_hu/seed20260825_n1000.json.gz \
  --summary runs/strategic_hu/seed20260825_n1000_summary.json
```

Do not start the multi-hour run unless those commands pass on the target Python
version.

## Long-run shape

Use independent seeds, not one enormous seed only.  Start with logarithmic
checkpoints (for example 10k, 30k, 100k, 300k, 1M) so policy drift can be
measured before spending days of CPU.  Keep the exact checkpoint file; do not
export only a distilled policy.

A resume continues the exact random stream:

```bash
python tools/openofc_solver/strategic_cfr_runner.py \
  --iterations 100000 \
  --resume runs/strategic_hu/seed20260825_n100000.json.gz \
  --checkpoint runs/strategic_hu/seed20260825_n200000.json.gz \
  --checkpoint-every 10000 \
  --epsilon 0.6
```

Compare checkpoints with:

```bash
python tools/openofc_solver/audit_strategic_convergence.py \
  runs/strategic_hu/seed20260825_n100000.json.gz \
  runs/strategic_hu/seed20260825_n200000.json.gz \
  --report runs/strategic_hu/n100k_to_n200k.json
```

The convergence report is **stability evidence only**.  Low policy drift cannot
be relabeled as exploitability or mathematical perfection.

## Required promotion gates

1. deterministic resume PASS;
2. multiple independent seeds with stable held-out performance;
3. exact evaluator parity remains PASS;
4. a separately implemented best-response/regret certificate establishes the
   chosen epsilon target for the declared HU current-hand game;
5. Fantasy/re-Fantasy continuation is coupled as an actual next-hand state, not
   a point heuristic;
6. production policy/search loss stays under its declared bound.

Until those gates pass the model authority remains `STRATEGIC_APPROX`.
