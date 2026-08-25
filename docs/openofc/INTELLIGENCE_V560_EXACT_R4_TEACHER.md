# OpenOFC v5.6.0 — exact terminal oracle and R4 teacher

## Outcome

v5.6.0 starts the mathematical-solver lineage without weakening the live
runtime. It adds one audited terminal utility and an exhaustive normal-round-4
teacher. The field-calibrated v5.5.2 TableMap is unchanged byte-for-byte.

This release is exact over a deliberately bounded domain. It is not yet a claim
that the entire imperfect-information game has been solved.

## Audit of `oh_0(20260825-050450).log`

The supplied field log contains 52 decision entries and 31 confirmed actions.
There are 192 rejected raw scrapes and two runtime faults:

1. At `2026-08-24 23:55:33`, normal-play post-drag verification did not find
   the requested physical card in the requested row. The fresh scrape showed a
   different UI placement. The runtime abandoned the transaction and entered
   reacquisition; it did not continue from invented state.
2. At `2026-08-25 00:01:56`, the Fantasy target top row was
   `[6h,8h,As]`, while fresh pixels reconstructed `[As,5h,6h]`. The bounded
   row retry expired and the runtime again entered reacquisition.

Both failures are consistent with a TableMap source/identity or click-position
disagreement. No policy deadlock, stale-action reuse, unbounded retry or silent
Confirm was found. The 192 raw failures are dominated by rank/suit ambiguity,
duplicate physical identities and transitional frames. They are correctly
fail-closed, and remain TM-calibration work rather than intelligence changes.

## M0 exact terminal oracle

`COFCExactEvaluator` is the single rules authority for terminal search and
training:

- exact 3-card top and 5-card middle/bottom comparison;
- wheel through royal straight flush;
- up to two distinct physical Jokers (`JK1` and `JK2`);
- duplicate-card rejection and completed-board foul detection;
- top, middle and bottom royalties;
- Fantasy entry tiers 14/15/16/17;
- KKPoker Joker Ultimate re-Fantasy qualification from top trips or bottom
  quads or better;
- pairwise row points, three-point scoop bonus, foul scoring and royalty
  differential.

Unknown cards, generic unresolved Jokers and incomplete boards never receive a
guessed terminal value.

## Exact normal R4 teacher

At the last normal round, Hero has three incoming cards and must place two and
discard one. The teacher enumerates all `3 × 3 × 3 = 27` discard/row
assignments and rejects those that exceed row capacity or violate physical-card
identity.

When every active opponent already has a complete visible terminal board, each
legal candidate receives exact showdown points. The existing smart baseline is
replaced only if a candidate satisfies both conditions:

- exact immediate score is not lower;
- Fantasy tier is not lower;

and at least one condition is strictly better. This Pareto gate deliberately
does not invent a conversion factor between one current point and future
Fantasy value.

If an opponent board is incomplete, an incoming identity is unknown, or any
other exact precondition is absent, the smart v5.3 action is retained. The live
log exposes this as `engine=HYBRID_EXACT_R4_V560` and records exact availability,
candidate counts, baseline/selected points and baseline/selected Fantasy tier.

## Verification gates

The deterministic standalone suite covers:

- royalty and Fantasy entry on a known valid board;
- foul suppression of royalties and Fantasy;
- Joker substitution into top trips;
- scoop plus royalty-differential scoring;
- exhaustive R4 replacement of a deliberately fouled baseline;
- baseline preservation without a terminal opponent;
- production-policy composition through the same Pareto contract.

The source regression pins the production TableMap SHA-256 to
`28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6`.

## Solver roadmap

The remaining game is imperfect-information and cannot be made exact by adding
larger heuristic weights. The next milestones are:

1. Generate a reproducible R4 dataset from the exact oracle, including chance
   outcomes and opponent information sets.
2. Solve small conditioned R4/R3 subgames with regret minimization and measure
   exploitability against the exact terminal utility.
3. Back up values from R4 to R3, then R2, R1 and the opening.
4. Train the global policy with External Sampling MCCFR; use DCFR for bounded
   subgames where full traversal is tractable.
5. Distill the converged policy for live latency, while retaining the exact
   oracle as the regression teacher.

Required metrics are points per hand, loss versus exact teacher, regret or
exploitability, foul rate, royalty EV, Fantasy-entry EV and seed-to-seed
stability. A learned policy is promoted only when it beats the currently
deployed policy under held-out deterministic deals and never violates legality
or physical-card identity.
