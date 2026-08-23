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

## M2a exact dealer-R4 corpus

Authoritative smoke run `32647659339` is GREEN. It generated 128 deterministic reachable deals and emitted 71 dealer/button R4 states after the default filter removed states with no non-fouled action. A second independent pass recomputed every stored action value and label from the state description and certified all 71 records. The sample contained 55 states involving at least one Joker, legal-action counts of 3 or 6, and best immediate scores from -10 to +16.

The smoke also exposed an important training-design property: **63 of 71 states had more than one point-optimal action**. In this sample every such point tie also had the same zero Fantasy award, so these are legitimate terminal equivalences for the current-hand objective, not a reason to manufacture a single arbitrary class label. M2 therefore stores the complete action-value vector plus the full set of point-optimal actions. Distillation must optimize values / set-valued targets rather than force one arbitrary action when several are mathematically tied.

The reachability sampler used for rounds 0-3 is explicitly tagged `UNIFORM_LEGAL_REACHABILITY_ONLY_NOT_TEACHER`. Its earlier random legal actions exist only to generate reachable R4 states; they must never be treated as demonstrations of good strategy.

The large-corpus path is resumable and auditable through `run_r4_dealer_shards.py`. Every shard has a deterministic deal-id range, SHA-256 completion marker and independent exact-label recomputation before it is accepted. The generator itself fails closed if the certified M1b Joker materialization is absent.

## Milestones

- **M0 — DONE:** pure cards, hand ranking, royalties, foul/scoop scoring, legal action generator, runtime-card mapping, exact terminal R4 oracle.
- **M0-LIVE — DONE:** the latest field log yielded a real fully observed R4 state. The exact oracle labels the unique optimum as `Th -> top`, `6s -> middle`, discard `7s`, worth +26 current-hand points.
- **M1a — DONE:** production OpenHoldem card representation corrected in the standalone parity harness; 3,653 non-Joker C++/Python comparisons PASS.
- **M1b — DONE:** row-local Joker semantics certified; targeted tests PASS; 770 Joker board comparisons PASS with zero mismatches.
- **M2a-SMOKE — DONE:** deterministic reachable dealer-R4 corpus generated, fully recomputed/audited, artifact published by CI.
- **M2a-SCALE — IN PROGRESS:** certify resumable shards, then generate a medium corpus before a large Ryzen run.
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
python tools/openofc_solver/test_r4_dealer_corpus.py
```

Generate and independently audit a dealer/button R4 corpus:

```bash
python tools/openofc_solver/apply_m1b_joker_semantics.py
python tools/openofc_solver/generate_r4_dealer_corpus.py --out r4.jsonl --attempts 1000
python tools/openofc_solver/audit_r4_dealer_corpus.py r4.jsonl
```

For resumable multi-core generation:

```bash
python tools/openofc_solver/run_r4_dealer_shards.py --out-dir runs/r4_dealer --attempts 100000 --attempts-per-shard 10000 --parallel-shards 1 --workers-per-shard 15
```

Label exact fully-observed R4 states in an OpenOFC log:

```bash
python tools/openofc_solver/extract_r4_log.py path/to/oh.log --out r4_labels.jsonl
```

The extractor deduplicates states and only labels snapshots with 11 Hero board cards, all 3 current incoming cards known, and a complete 13-card opponent board. It therefore does not leak hidden information into an allegedly exact label.
