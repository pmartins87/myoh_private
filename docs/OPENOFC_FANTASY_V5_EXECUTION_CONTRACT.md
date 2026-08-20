# OpenOFC Fantasy v5 — execution contract

## Scope

This document freezes the first field-derived execution design for KKPoker Joker Ultimate Fantasy after review of two independent user replay sessions on 2026-08-19.

The goal is not to make Fantasy depend on fixed source slots. The loose fan is a dynamic visual object set whose cards reflow after row submission/clear operations.

## Field evidence now established

1. A 16-card Fantasy was observed from a fully loose fan through multiple placements. As cards entered rows, the remaining fan recentred and changed spacing/angles.
2. A separate 15-card Fantasy was observed with the same dynamic-fan behaviour.
3. Direct click on a loose card raises/selects that card while the rest of the fan remains materially stable until row submission.
4. When a row is empty, a yellow check button is available next to that row and can commit the currently selected/raised cards into the row.
5. Once a row contains cards, the same action area becomes a red X. Clicking it clears the entire row and returns those cards to the loose fan, causing a new fan reflow.
6. The client exposes hand-strength helper buttons (Pair, Two Pair, Trips, Straight, Flush, Full House, Quads, Straight Flush). They select candidate cards but do not choose strategically correct cards.
7. Loose cards can also be dragged onto cards already on the board to swap positions. Board cards can likewise be dragged onto each other to swap.

## Primary execution method: batch-select + row check

The v5 primary executor SHALL NOT use the hand-strength helper buttons as strategy authority.

For each target row:

1. Start from a fresh bitmap and dynamically detect every current loose physical card.
2. Bind each solver target card to its current click-safe source rectangle.
3. Select every target card for that row by direct click. No full scrape occurs between these card-select clicks because selected cards change vertical presentation.
4. Click the row's yellow check button once.
5. Capture a fresh bitmap.
6. Re-recognize the fixed arrangement row and the newly reflowed loose fan.
7. Prove exact row membership and exact physical-card conservation before proceeding to another row.

Preferred initial row order: Bottom (5), Middle (5), Top (3). This removes five cards from the fan as early as possible and makes subsequent fan geometry easier, while row membership rather than within-row order is strategically meaningful.

## Why helper hand-strength buttons are not primary

The client helper may select a valid instance of a pair/trips/etc., but the OpenOFC solver may need another physical instance because of row ordering, royalties, Joker usage, future row strength, or discard choice. Using the helper would outsource a strategic decision to client UI logic. It may later be considered only as an optional verified accelerator, never as decision authority.

## Recovery hierarchy

### First recovery: clear one row

If post-submit verification proves that the row does not contain exactly the solver target set:

1. click that row's red X;
2. wait for a fresh bitmap;
3. prove the row is empty and all cleared physical cards returned to the loose lineage;
4. re-detect the fan from scratch;
5. retry that row once.

This is the preferred recovery because the field replay directly proves the whole-row clear semantics.

### Second recovery: physical swap

Card-on-card swap is retained as a later repair primitive, not the first implementation. A swap changes two physical locations in one gesture and therefore requires stronger two-card transactional verification. It is useful for future late repair/minimal-edit optimization after the direct batch executor is stable.

## Dynamic source geometry

There is no persistent `src00`, `src01`, ... semantic identity.

After every successful row submission or row clear:

`fresh bitmap -> detect loose rank anchors/components -> fit current fan geometry -> classify cards -> bind physical card identity to current rectangle`

Only that fresh mapping may authorize the next click batch.

A selected/raised-card intermediate frame is deliberately outside the recognition contract. The executor selects the complete row from one already-certified geometry snapshot and immediately submits the row before asking the scraper for another strategic observation.

## Fantasy size contract: 14..17

The solver receives N physical cards, where 14 <= N <= 17, chooses exactly 13 board cards, and marks N-13 cards unused.

Important correction for 14-card Fantasy: current `RecognizeCurrentLooseObjects()` requires at least two detected loose anchors, which cannot certify the final state when 13 board cards leave only one unused card. v5 SHALL NOT require loose-card recognition after all 13 target cards are proven on the board. The remaining unused set is derived exactly as:

`original Fantasy physical set - final 13-card board set`

This works for 14, 15, 16 and 17 without needing to visually classify the final 1..4 leftovers.

## Finalization

The existing replays establish row selection, row submission, fan reflow and row clear semantics. They do not yet provide a fully documented frame pair for the exact UI state after all 13 solver cards have been placed and immediately before/after the final Fantasy submission.

Implementation may proceed through complete 13-card board construction now. Final Fantasy Confirm authority must remain fail-closed until a field replay or live capture proves the exact final submission control/state transition.

## Acceptance gates

V5-A — Offline replay recognition
- recognize the complete initial loose set in both supplied sessions;
- preserve exact card uniqueness across every observed reflow;
- recognize fixed row membership after row submissions/clears;
- never use fixed loose source slot identity.

V5-B — Physical row executor
- from a fresh live Fantasy, select a complete target row by click;
- submit with yellow check;
- verify exact row membership and fan conservation;
- repeat 5/5/3.

V5-C — Recovery
- deliberately/observationally detect a wrong row;
- clear it with red X;
- prove cards returned to the fan;
- rebuild from fresh geometry.

V5-D — Finalization
- prove 13 target cards on board;
- derive unused set by set difference;
- prove and execute the final Fantasy submission control;
- verify transition out of Fantasy.

V5-E — Cardinalities
- field prove at least 14-card and 15/16-card sessions;
- retain 17-card support in the same geometry/count-general path.
