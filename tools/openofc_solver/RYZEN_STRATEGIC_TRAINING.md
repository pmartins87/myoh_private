# Ryzen strategic HU training — execution contract

This run is deliberately separate from the v5.8.1 field executable. It trains
an offline **heads-up only** full-action strategy and cannot change live clicks
until convergence, continuation value and production-loss gates pass.

## Scope and design rule

The target game is HU only. No three-player equilibrium work is required.
Mathematical rigor must remain practical on the available workstation: before
spending hours or days of CPU, every scale increase is measured for throughput,
RAM growth, information-set growth and checkpoint size.

The solver may reduce cost only with transformations that preserve the declared
HU game or with approximations whose loss is separately bounded. The preferred
path is therefore exact suit symmetry, exact canonicalization, variance
reduction, resumable sampling and parallelism before any abstraction.

## Why this run exists

The previous R3/R4 teacher pipeline is exact or sampled under an explicit
card-blind hidden-card belief. It is valuable for leaf auditing, but once early
placements become strategic those public actions carry information about hidden
cards. The global solver therefore learns all HU normal-hand information sets
jointly with outcome-sampling MCCFR.

The v2 runner stores the exact PRNG state. `N` uninterrupted iterations and
`N1 + resume + N2` iterations are required to produce the same solver state when
`N=N1+N2`. Every checkpoint is SHA-256 protected and atomically replaced.

The production training path uses `--suit-canonical`. This is an exact 24-way
suit-isomorphism reduction, not an action abstraction.

## Phase 0 — target-machine correctness smoke

From the repository root:

```bash
python tools/openofc_solver/apply_m1b_joker_semantics.py
python tools/openofc_solver/test_strategic_cfr.py
python tools/openofc_solver/test_strategic_suit_symmetry.py
python tools/openofc_solver/test_strategic_runner.py
python tools/openofc_solver/test_strategic_feasibility.py
```

Do not start a long run unless all commands pass on the target Python version.

## Phase 1 — measured feasibility calibration

Run a short suit-canonical probe first:

```bash
python tools/openofc_solver/strategic_feasibility.py \
  --iterations 100 \
  --seed 20260825 \
  --epsilon 0.6 \
  --checkpoint runs/strategic_hu/feasibility_n100.json.gz \
  --report runs/strategic_hu/feasibility_n100.json
```

Repeat at a larger logarithmic point only after inspecting the report, for
example 1k and then 10k. The report records:

- iterations/second and episodes/second;
- information sets and their growth rate;
- current/peak RSS when the OS exposes it;
- compressed checkpoint size;
- first-order runtime/disk projections clearly marked as diagnostic only.

Optional hard budgets can fail the run automatically instead of letting an
accidental configuration exhaust the machine:

```bash
python tools/openofc_solver/strategic_feasibility.py \
  --iterations 1000 \
  --checkpoint runs/strategic_hu/feasibility_n1000.json.gz \
  --report runs/strategic_hu/feasibility_n1000.json \
  --max-wall-seconds 3600 \
  --max-rss-mb 24000 \
  --max-checkpoint-mb 8000
```

The numbers above are examples, not project assumptions. Set them to the actual
machine budget before the real run.

## Phase 2 — resumable strategic run

Start with logarithmic checkpoints instead of committing immediately to a huge
sample count. A first production-shaped command is:

```bash
python tools/openofc_solver/strategic_cfr_runner.py \
  --iterations 10000 \
  --checkpoint-every 1000 \
  --seed 20260825 \
  --epsilon 0.6 \
  --suit-canonical \
  --checkpoint runs/strategic_hu/seed20260825_n10000.json.gz \
  --summary runs/strategic_hu/seed20260825_n10000_summary.json
```

A resume continues the exact random stream:

```bash
python tools/openofc_solver/strategic_cfr_runner.py \
  --iterations 20000 \
  --resume runs/strategic_hu/seed20260825_n10000.json.gz \
  --checkpoint runs/strategic_hu/seed20260825_n30000.json.gz \
  --checkpoint-every 2000 \
  --epsilon 0.6
```

The resumed checkpoint remembers that it is `suit24-exact`; a raw solver cannot
silently replace it.

## Phase 3 — evidence before more CPU

Compare checkpoints with:

```bash
python tools/openofc_solver/audit_strategic_convergence.py \
  runs/strategic_hu/seed20260825_n10000.json.gz \
  runs/strategic_hu/seed20260825_n30000.json.gz \
  --report runs/strategic_hu/n10k_to_n30k.json
```

The convergence report is **stability evidence only**. Low policy drift cannot
be relabeled as exploitability or mathematical perfection.

Only continue to larger checkpoints (for example 100k, 300k, 1M) when the
measured gain justifies the projected CPU/RAM/disk cost. Independent seeds are
required; one enormous seed is not sufficient evidence.

## Practical stop / redesign rule

If a scale step is projected to exceed the available resources, do not simply
launch it. First attempt exact cost reductions or variance reduction. If an
approximation becomes necessary, preserve the unabstracted solver as the oracle
and measure the approximation's loss explicitly. An unmeasured abstraction can
be useful experimentally but cannot receive `STRATEGIC_CERTIFIED` authority.

## Required promotion gates

1. deterministic resume PASS;
2. HU-only scope and resource-feasibility probe PASS on the target workstation;
3. multiple independent seeds with stable held-out performance;
4. exact evaluator parity remains PASS;
5. a separately implemented best-response/regret certificate establishes the
   chosen epsilon target for the declared HU current-hand game;
6. Fantasy/re-Fantasy continuation is coupled as an actual next-hand state, not
   a point heuristic;
7. production policy/search loss stays under its declared bound;
8. the certified training and inference path fits the actual CPU/RAM/disk budget.

Until those gates pass the model authority remains `STRATEGIC_APPROX`.
