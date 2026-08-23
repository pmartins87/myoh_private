# OpenOFC Normal Solver v1

This directory is the offline strategy project for **normal KKPoker OFC Joker Ultimate**.
It is deliberately independent of TableMap, mouse execution and OCR. UI defects must never become strategy constraints.

## Mathematical contract

The pure engine models the rule screens captured from KKPoker:

- 5 starting cards; rounds 1-4 receive 3, place 2 and discard 1;
- rows are Top 3 / Middle 5 / Bottom 5;
- Bottom >= Middle >= Top or the hand fouls;
- row win = 1 point and a 3-row sweep adds a 3-point scoop bonus;
- KKPoker royalties are encoded exactly in `royalty()`;
- Ultimate + Joker uses two wild Jokers;
- QQ/KK/AA on top enters 14/15/16-card Fantasy; top trips enters 17-card Fantasy.

Fantasy continuation value is **not** represented by arbitrary heuristic points in the solver objective. The engine reports the Fantasy award separately so a later self-play value function can learn the actual continuation EV.

The only rule item intentionally isolated behind a parity gate is the exact tie-breaking semantics for resolving one/two wild Jokers across a complete board. The current implementation exhaustively enumerates distinct unused regular-card substitutions and selects the highest-royalty valid resolution, then bottom/middle/top strength. Long training runs must not be certified until this matches KKPoker/C++ regression evidence.

## Milestones

- **M0 — DONE:** pure cards, hand ranking, royalties, foul/scoop scoring, legal action generator, runtime-card mapping, exact terminal R4 oracle.
- **M0-LIVE — DONE:** the latest field log yielded a real fully observed R4 state. The exact oracle labels the unique optimum as `Th -> top`, `6s -> middle`, discard `7s`, worth +26 current-hand points.
- **M1:** parity tests against the production C++ evaluator and additional KKPoker Joker examples.
- **M2:** build a large exact R4 corpus from reachable self-play states and live snapshots.
- **M3:** solve R3 by chance sampling / backward induction using exact R4 leaves.
- **M4:** extend backward through R2, R1 and the 232 legal opening placements with information-set self-play.
- **M5:** distill teacher search into a fast policy/value model; keep search as an audit oracle.
- **M6:** integrate the trained policy behind the OpenOFC strategy interface and measure loss versus teacher, foul rate, points/hand, royalties, Fantasy entry and multi-seed stability.

## Smoke tests

From the repository root:

```bash
python tools/openofc_solver/test_engine.py
```

Label exact fully-observed R4 states in an OpenOFC log:

```bash
python tools/openofc_solver/extract_r4_log.py path/to/oh.log --out r4_labels.jsonl
```

The extractor deduplicates states and only labels snapshots with 11 Hero board cards, all 3 current incoming cards known, and a complete 13-card opponent board. It therefore does not leak hidden information into an allegedly exact label.
