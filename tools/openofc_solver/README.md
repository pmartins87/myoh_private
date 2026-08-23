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

M1 is complete.

**M1a — PASS.** The Python exact core is tested against the production C++ evaluator after materializing the standalone C++ test shim with the real OpenHoldem `StdDeck` representation (`value = suit * 13 + rank`, suit order hearts/diamonds/clubs/spades). The old standalone test shim had accidentally used a rank-major `/4` representation, so its previous self-tests were internally consistent but not bit-for-bit representative of production card values.

Authoritative CI run `32625573072` passed both jobs. The C++/Python parity gate checked, with deterministic seed `20260823`:

- all 54 canonical runtime values (52 regular cards + 2 Jokers) for card mapping;
- 2,060 complete non-Joker rows for rank and royalty parity;
- 1,539 complete non-Joker 3/5/5 boards for foul, rank, royalty and Fantasy-award parity;
- the existing native C++ baseline-policy standalone self-test after correcting its test-only card mapping.

That is 3,653 non-Joker parity comparisons with zero mismatches.

**M1b — PASS.** The KKPoker rule contract is now interpreted as row-local Joker substitution because each row is scored separately. Physical dealt cards remain globally unique, while a Joker may represent a card identity visible in another row. Within a single row, exact represented playing cards must remain distinct, preventing impossible constructs such as a double-Ace flush. See `RULE_CONTRACT_M1B_JOKERS.md`.

Authoritative strict run `32647078283` passed the targeted M1b semantic tests and a widened deterministic Joker parity corpus. After materializing the same rule contract into Python and C++:

- 512 one-Joker random complete boards;
- 256 two-Joker random complete boards;
- 2 targeted historical mismatch boards;

were compared for a total of **770 Joker boards with zero mismatches**. Combined with M1a, the exact Python core and materialized C++ evaluator now agree on the certified rule surface used to start teacher-data generation.

## Position/information asymmetry

Heads-up KKPoker OFC is not one information state. The player left of the button acts first in a round and the button acts last. Therefore:

- **Dealer/button R4:** opponent has already completed the round. The opponent final 13-card board is public, so the terminal R4 decision can be solved exactly by exhaustive action enumeration.
- **Non-dealer R4:** opponent's current 3-card packet and final placements are still unknown when Hero acts. This is an information-set decision and must optimize expectation over chance plus opponent policy; it is not legitimately labelable by the fully observed R4 oracle.

M2 is therefore split into an exact dealer-R4 teacher corpus first, then an information-set non-dealer R4 teacher once an opponent response model/search policy exists. This prevents hidden future information from leaking into training labels.

## Milestones

- **M0 — DONE:** pure cards, hand ranking, royalties, foul/scoop scoring, legal action generator, runtime-card mapping, exact terminal R4 oracle.
- **M0-LIVE — DONE:** the latest field log yielded a real fully observed R4 state. The exact oracle labels the unique optimum as `Th -> top`, `6s -> middle`, discard `7s`, worth +26 current-hand points.
- **M1a — DONE:** production OpenHoldem card representation corrected in the standalone parity harness; 3,653 non-Joker C++/Python comparisons PASS.
- **M1b — DONE:** row-local Joker semantics certified; targeted tests PASS; 770 Joker board comparisons PASS with zero mismatches.
- **M2a — IN PROGRESS:** generate reachable **dealer/button R4** states and exact labels without hidden-information leakage.
- **M2b:** build the non-dealer R4 information-set teacher using chance sampling plus an opponent response policy/search.
- **M3:** solve R3 by chance sampling / backward induction using R4 teachers as leaves, preserving dealer/non-dealer information sets.
- **M4:** extend backward through R2, R1 and the 232 legal opening placements with information-set self-play.
- **M5:** distill teacher search into a fast policy/value model; keep search as an audit oracle.
- **M6:** integrate the trained policy behind the OpenOFC strategy interface and measure loss versus teacher, foul rate, points/hand, royalties, Fantasy entry and multi-seed stability.

## Smoke tests

From the repository root the CI materializes the M1b rule semantics first, then runs:

```bash
python tools/openofc_solver/test_engine.py
python tools/openofc_solver/test_m1b_joker_semantics.py
```

Label exact fully-observed R4 states in an OpenOFC log:

```bash
python tools/openofc_solver/extract_r4_log.py path/to/oh.log --out r4_labels.jsonl
```

The extractor deduplicates states and only labels snapshots with 11 Hero board cards, all 3 current incoming cards known, and a complete 13-card opponent board. It therefore does not leak hidden information into an allegedly exact label.
