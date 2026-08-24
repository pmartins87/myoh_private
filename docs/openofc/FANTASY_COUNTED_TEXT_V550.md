# OpenOFC v5.5.0 — Counted TableMap Text Fantasy

Status: **experimental / PR #13 remains Draft until live KKPoker completion**.

## Why this branch exists

Field testing through v5.4.9 proved that Fantasy detection, canonical reconstruction, policy, planning and bounded physical input can all be reached. The recurring failure moved to loose-card identity: the custom native rank recognizer could reject valid glyphs or occasionally produce an off-lineage identity after KKPoker reflowed the hand.

v5.5.0 therefore separates two problems that were previously coupled:

1. **How many loose cards are currently visible?** — geometry only.
2. **Which physical cards are they?** — OpenHoldem TableMap text transforms for the selected count only.

The native recognizer is retained for fixed arrangement verification from the v5.4.10 lineage, but it is no longer the loose-hand identity authority in the counted-text route.

## Stable loose-card state machine

The Fantasy executor commits complete rows in this order:

`TOP(3) -> MIDDLE(5) -> BOTTOM(5)`

For a starting Fantasy of 14..17 cards, the only loose-card counts requiring clickable source identity are:

| Stage | Loose counts |
|---|---|
| Initial | 14, 15, 16, 17 |
| After TOP | 11, 12, 13, 14 |
| After MIDDLE | 6, 7, 8, 9 |
| After BOTTOM | no mapped source family required |

The unique mapped set is therefore:

`6,7,8,9,11,12,13,14,15,16,17`

Count 10 and count 5 are not stable states in this execution path. Counts 1..4 can exist physically after BOTTOM, but there is no further card-selection click. Once the verified board contains 13 cards, unused identities are derived from exact physical lineage:

`unused = original Fantasy deal - verified 13-card arrangement`

No click rectangle is fabricated for those final unused cards.

## Field calibration

The supplied `FANTASY.zip` contains stable replay frames for:

`6,7,8,9,11,12,13,14,15,16`

Transitional frames are excluded. Count 17 has no real supplied frame; its current geometry is only interpolated from count 16 and the test TableMap keeps:

`openofc_fantasy17_calibrated = 0`

The runtime rejects a detected count-17 state until this symbol is explicitly enabled after real field calibration.

## Geometry-only count detector

`COFCFantasy15PixelRecognizer::DetectLooseCount()` uses the existing dynamic rank-anchor extraction but does **not** classify rank or suit.

For each supported count it compares the current ordered anchor geometry to a measured template. Up to two **extra** false anchors may be dropped exhaustively; missing expected anchors are never tolerated. The score is based on x/y residual plus an explicit false-anchor penalty. Acceptance requires both:

- best score <= 8.0;
- best-vs-second margin >= 3.0.

A supplied count-9 fixture contains a real false lower-glyph anchor around x=192; the regression requires the matcher to reject that extra anchor and still choose count 9.

## Count-selected TableMap identity

After count `N` is selected, the scraper evaluates only:

`ofc_fantasyNN_00rank/suit ... ofc_fantasyNN_(N-1)rank/suit`

The test TableMap uses the user's T7 font bank. Every slot must produce a valid physical card, every card must be unique, and with prior lineage every card must belong to the exact original Fantasy deal.

A dedicated TableMap opt-in is mandatory:

`openofc_fantasy_tablemap_text_by_count = 1`

Missing opt-in fails closed rather than interpreting an older TableMap using the new namespace.

## Joker identity

T7 can return `X` for a Joker. `X` is not enough to identify the two physical KKPoker Jokers, so v5.5.0 classifies only the exact selected rank rectangle:

- persistent red/orange Joker marker -> JK1;
- persistent gray/black Joker marker -> JK2;
- ambiguous color -> reject the observation.

This classifier runs only after T7 has already returned `X`, so red suit/rank pixels on ordinary cards cannot independently turn a card into a Joker.

## Safety boundaries

- No global rank/suit threshold is loosened.
- The count detector does not invent card identities.
- The text route must be explicitly enabled by the TableMap.
- Count 17 remains disabled until a real frame exists.
- Duplicate and off-lineage physical cards fail closed.
- Final unused 1..4 cards have no clickable source geometry.
- Normal OpenOFC and bounded-input behavior remain inherited from the v5.4.10 materialization lineage.

## Authoritative gate

Workflow: `OpenOFC v5.5.0 counted-text authoritative PR gate`.

The gate materializes v5.3 through v5.4.10, applies v5.5.0/v5.5.0a, runs counted-text and historical Fantasy regressions, canonical 14..17 tests, continuity/UNKNOWN tests, and builds `OpenHoldem Release|Win32` before publishing a field-test artifact.

A green CI run is build/regression evidence only. PR #13 stays Draft until a live KKPoker Fantasy completes:

`count -> T7 identity -> policy/plan -> TOP -> MIDDLE -> BOTTOM -> 13-card verification -> Confirm`.
