# OpenOFC normal-flow v3 diagnosis — playable log 2026-08-19

## Evidence

The uploaded playable log proves that Joker rank token `X` works in the normal TableMap path (`TABLEMAP_JOKER_X`). It also proves that v2 frequently reaches a valid round-0 decision, dispatches physical drags and verifies them, but then loses raw validity before transaction completion. No `DeepOFC CONFIRM` was emitted in the uploaded v2 run.

The main failure pattern is a vacated source slot whose `empty` transform remains false while rank/suit are blank. The most frequent example is `ofc_p1_bottom4`, which is valid while the dealt card is there and becomes `REJECTED rank_eval_or_contract_failed` after the card is dragged away. The former global `all_slots_ok` contract therefore converted a harmless transition hole into `NORMAL_REJECTED`, so the runtime never verified the rest of the placement plan or reached Confirm.

A second independent issue is simultaneous opponent placement. The previous scraper declared 1..4 opening public cards and intermediate 6/8/10/12 public cards impossible. Those counts are normal while the opponent is arranging OFC cards and must not invalidate Hero perception.

A third issue is TableMap calibration. The user-updated v2 TableMap has complete T1/T5 board banks, but T3 (Hero incoming) is missing `A`, `K`, `Q`, `9`; T2 (Hero discard tracker) is missing `K`, `X`. The playable trace contains a second-round `Ad` that could not be decoded in T3. These are calibration gaps and must remain explicit instead of being hidden by OCR/native fallbacks.

Finally, `ofc_p0_bottom2rank` was the only opponent board rank still assigned to incomplete bank T4. v3 moves it to T5.

## v3 changes

- transient `ScrapeOFCSlot` failures are tolerated as UNKNOWN at the slot level;
- exact Hero total/incoming contracts remain the final action gate, so an actually unreadable Hero incoming card cannot authorize play;
- partial opponent public-board progression is tolerated during simultaneous arrangement;
- `ofc_p0_bottom2rank` uses T5;
- TableMap/runtime contract is v3;
- an explicit `[OpenOFC DEADLINE] confirm_ready=1` trace precedes Confirm;
- Joker remains `X` in rank transforms;
- Fantasy stays on its separate dynamic source-detection path.

## Field acceptance target

The next simulator run must prove sequential normal play R0 -> R1 -> R2 -> R3 -> R4 without manual Confirm. For a non-dealer round, completed arrangement should immediately reach `OpenOFC DEADLINE` and `DeepOFC CONFIRM`. For a dealer round, early arrangement may remain provisional; after timer/opponent-final-information evidence, it must reanalyse if needed and then Confirm.

The runtime must not reintroduce OCR/native guessing into normal TableMap rank/suit recognition.
