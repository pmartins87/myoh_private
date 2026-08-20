# OpenOFC phase-flow v4 acceptance contract

## Why this version exists

The previous field test accidentally paired TableMap contract 3 with an executable that still expected contract 2. The contract guard correctly suppressed the autoplayer, so that run did not actually test v3 execution. v4 packages executable and TableMap together and makes the phase model explicit.

## Normal semantic edges

- R0 READY: exactly five fully recognized Hero incoming cards.
- After Confirm: enter WAIT_NEXT_3; transition animation frames have no phase authority.
- R1..R4 READY: exactly three fully recognized Hero incoming cards at the next monotonic round index.
- After R4 Confirm: WAIT_RESULT.

Card motion, timer motion, score animation, partial opponent placement and temporarily unreadable optional slots do not themselves create a new phase.

## Result / continuation edge

A scoring result is recognized from face-up opponent discards, not discard rank/suit identity. Two of the first three opponent discard positions must be occupied by face-up cards (not empty, not backs).

A result-screen FANTASY marker is recognized independently for Hero and opponent using a two-of-three calibrated gold/orange probe bank. Fantasy means continuation of the same match chain.

SAFE_END requires:

1. debounced result screen;
2. no Hero result Fantasy;
3. no opponent result Fantasy.

## Session stop policy

Scheduled stop is independent from poker strategy/formulas.

TableMap configuration:

- `s$openofc_stop_enabled 0/1`
- `s$openofc_stop_local_hhmm HHMM`
- `s$openofc_result_debounce_frames 2`

At the deadline OpenOFC sets `stop_requested=1` and keeps playing. It closes the attached simulator table only at SAFE_END. If Fantasy is awarded, the stop request survives the continuation.

The feature defaults OFF.

## Calibration status

T1, T3 and T5 are complete for A,K,Q,J,T,9..2, c/d/h/s and X. T2 is missing only K and X. The T2 gaps do not affect result-boundary recognition.

## Field test

Use the packaged v4 executable and packaged v4 TableMap without replacing either file. The first line-level acceptance check is contract 4 ACTIVE with no contract suppression. Then prove autonomous R0 -> R1 -> R2 -> R3 -> R4 and result detection.

## Green artifact

Run `32269502427`, job `96122186347`, passed source repair, v4 semantic assertions, canonical TableMap validation, policy selftest, dependency build, OpenHoldem Win32 build, package collection and upload.

Artifact: `OpenOFC_PhaseFlow_v4_Windows`, ID `9371656233`, digest `sha256:a20a7457c6b66bd7760d69fcf49a1f40d0b678c82133ebc7bba06b2aec1fe299`.

The package contains exactly one TableMap. Its SHA256 is `09f5195ba710376142c6a59f1be80c0b93a35e44dfff995effb98dc8bb93df5b`.
