# OpenOFC normal-flow / phase-flow diagnosis — 2026-08-19

## Latest field evidence

The latest user session did **not** execute the v3 runtime as a matched package. The log loaded `KKPoker_OpenOFC_JokerUltimate_v3.tm`, but the executable still expected TableMap contract 2. The runtime therefore did exactly what the contract guard is designed to do: it kept OpenOFC isolated from Hold'em and suppressed all autoplayer input. Repeated log lines state `Autoplayer suppressed until TableMap contract=2`.

This means the latest field run cannot be used as evidence that v3 normal-flow logic failed. It is evidence of an executable/TableMap version mismatch.

The same log independently proves that Joker `X` is valid. Raw perception reports `TABLEMAP_JOKER_X card=JK value=54 rank="X"`; the canonical inspector resolves that generic physical occurrence to `JK1`. Raw value 54 is the temporary generic Joker token, not an invalid card.

## Latest user TableMap audit

The newly supplied `KKPoker_OpenOFC_JokerUltimate_v3.tm` has SHA256:

`40dcf5c1e4651e8902e6debd5b78055c48942412c5f30c4a88fbc0dc51588109`

Its text-transform banks are now:

- T1 Hero board: complete A,K,Q,J,T,9..2 + c,d,h,s + X;
- T5 opponent board: complete A,K,Q,J,T,9..2 + c,d,h,s + X;
- T3 Hero incoming: complete A,K,Q,J,T,9..2 + c,d,h,s + X;
- T2 Hero discard tracker: missing only K and X.

The remaining T2 gaps are local discard-identity gaps. They do not prevent general round recognition. A K discarded by Hero can still become unreadable until that glyph is added; X discard is not expected in normal strategy but remains an explicit calibration gap.

## Semantic phase model frozen for v4

Normal OFC now uses semantic edges instead of arbitrary animation frames:

1. `WAIT_INITIAL_5`: a normal match begins only after a complete five-card Hero incoming set is recognized.
2. `ROUND_ACTIVE`: the current decision is arranged/verified and Confirm is sent once.
3. `WAIT_NEXT_3`: after Confirm, all partial/rejected animation frames are observational noise. R1..R4 begin only when the next complete three-card Hero incoming set is recognized at the expected monotonic round.
4. `WAIT_RESULT`: after R4 Confirm, the runtime stops trying to interpret scoring animations as playable card state.
5. `FANTASY_CONTINUATION`: a result screen that awards Fantasy is continuation of the same match chain.
6. `SAFE_END`: a debounced result screen with opponent discards face-up and no Hero/opponent Fantasy is a safe match-chain boundary.

The transaction phase (`IDLE / ARRANGING / CONFIRM_SENT`) remains separate from this match-phase model.

## Result and Fantasy markers

The result marker does not depend on discard rank/suit identity. Opponent discards are hidden backs during live rounds and become face-up on the scoring result screen. v4 counts face-up/not-back evidence in the first three opponent discard positions and requires two-of-three.

The supplied result evidence and the historical Fantasy replay set were used to calibrate three independent orange/gold marker probes for each physical chair. A player is considered to have a result-screen Fantasy marker only with two-of-three hits. These markers are read before card-state validation, so transient result animations cannot erase the safe-exit decision.

## Scheduled safe exit

OpenOFC no longer needs an `.ohf` formula merely to stop by time. v4 adds an OFC-native session policy:

- `s$openofc_stop_enabled 0/1`
- `s$openofc_stop_local_hhmm HHMM`
- `s$openofc_result_debounce_frames 2`

At the configured local time the runtime only arms `stop_requested`. It continues the current match chain. The table is closed only after `SAFE_END`. If Hero or opponent has Fantasy at the result screen, the stop remains pending and play continues.

Scheduled stopping defaults OFF.

## v4 package contract

Canonical TableMap:
`KKPoker_OpenOFC_JokerUltimate_v4.tm`

SHA256:
`09f5195ba710376142c6a59f1be80c0b93a35e44dfff995effb98dc8bb93df5b`

Runtime/TableMap contract: 4.

The package must be used as a unit. Mixing this TableMap with an older executable is intentionally blocked.

## Field acceptance target

The next simulator test must use the entire v4 package unchanged and prove:

- contract 4 active, with no contract suppression;
- R0 starts from five incoming cards;
- automatic Confirm;
- R1, R2, R3 and R4 each begin from the next complete three-card set;
- transition animations are logged as ignored rather than becoming a new phase;
- Joker X remains valid;
- after R4 the result marker is detected;
- if a result Fantasy marker appears, it is logged as continuation rather than safe end.

Scheduled close itself may remain disabled during the first normal-flow acceptance run.
