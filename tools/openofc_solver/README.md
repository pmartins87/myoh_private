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

## Production parity gate

M1 is deliberately split into non-Joker and Joker parity.

**M1a — PASS.** The Python exact core is now tested against the production C++ evaluator after materializing the standalone C++ test shim with the real OpenHoldem `StdDeck` representation (`value = suit * 13 + rank`, suit order hearts/diamonds/clubs/spades). The old standalone test shim had accidentally used a rank-major `/4` representation, so its previous self-tests were internally consistent but not bit-for-bit representative of production card values.

Authoritative CI run `32625573072` passed both jobs. The C++/Python parity gate checked, with deterministic seed `20260823`:

- all 54 canonical runtime values (52 regular cards + 2 Jokers) for card mapping;
- 2,060 complete non-Joker rows for rank and royalty parity;
- 1,539 complete non-Joker 3/5/5 boards for foul, rank, royalty and Fantasy-award parity;
- the existing native C++ baseline-policy standalone self-test after correcting its test-only card mapping.

That is 3,653 non-Joker parity comparisons with zero mismatches.

**M1b — OPEN.** The diagnostic Joker corpus compared 146 complete boards and found 2 mismatches, both on two-Joker boards. The mismatches isolate one semantic question rather than a generic evaluator disagreement: the production C++ evaluator resolves each row independently, while the first Python implementation treated Joker substitutions as globally unavailable if the represented physical card appeared in another row. KKPoker's rule says the two Jokers can represent any other playing card to form the strongest hand as long as the board is not fouled, but this wording does not explicitly define cross-row substitution identity. Do not start long training runs until M1b is resolved against the rule contract and targeted KKPoker evidence.

The Joker diagnostic is intentionally non-fatal to M1a and is uploaded by CI as `OpenOFC_Joker_Parity_Diagnostic`.

## Milestones

- **M0 — DONE:** pure cards, hand ranking, royalties, foul/scoop scoring, legal action generator, runtime-card mapping, exact terminal R4 oracle.
- **M0-LIVE — DONE:** the latest field log yielded a real fully observed R4 state. The exact oracle labels the unique optimum as `Th -> top`, `6s -> middle`, discard `7s`, worth +26 current-hand points.
- **M1a — DONE:** production OpenHoldem card representation corrected in the standalone parity harness; 3,653 non-Joker C++/Python comparisons PASS.
- **M1b — OPEN:** settle row-local Joker substitution semantics and certify targeted one/two-Joker parity against KKPoker evidence.
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
