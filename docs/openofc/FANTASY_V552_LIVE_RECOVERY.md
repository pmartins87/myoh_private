# OpenOFC v5.5.2 — Fantasy live recovery

This field build fixes the three failures observed in the live session captured
on 2026-08-25. The executable and the TableMap in this package are a required
pair. Do not reuse a v5.5.1 or older TableMap with this executable.

## What the live log proved

- TOP was sent as one selection/check transaction.
- MIDDLE was sent and later verified.
- BOTTOM was also sent at 20:37:05. Its six bounded clicks completed in 828 ms
  with a configured 110 ms gap, making the action look almost instantaneous.
- After BOTTOM, the strict upright classifier read one arranged card as `3h`,
  outside the original Fantasy lineage. Every subsequent frame was rejected, so
  the runtime could not reach the final Confirm.
- At 20:37:51 a different empty 16-card re-Fantasy fan appeared. All 16 current
  cards were decoded, but the scraper compared them with the previous 16-card
  lineage and rejected the new deal before canonical state/UI replacement.

## Corrections in v5.5.2

1. **Re-Fantasy rollover from the current screen.** An empty decoded 14–17 card
   fan whose physical set differs from the prior set resets the old lineage and
   becomes the new deal. Clearing and rebuilding the same physical hand keeps
   the existing lineage.
2. **Final 13-card lineage matching.** The final board is assigned one-to-one
   against the original 14–17 physical cards, permitting exactly 1–4 unused
   cards. A weak upright glyph can resolve to a valid lineage card, but an
   off-lineage card still fails closed.
3. **Exact visual row verification.** A TOP/MIDDLE/BOTTOM transaction succeeds
   only when the fresh raw visual row contains the exact target set. Canonical
   pending metadata cannot by itself acknowledge a click batch.
4. **Slower visible selection.** The enforced delay is 250 ms between every
   selected card and the row check. The bounded-input focus/interference guards
   remain active.
5. **Screen-order UI.** `FANTASY SCREEN ORDER` uses the current loose-card array
   exactly as scraped from left to right. It is not sorted. While perception is
   being reacquired, the UI explicitly says so instead of presenting the old
   incoming set as the current fan.

## Required files

- `OpenHoldem.exe`
- `KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm`
- the DLLs shipped beside the executable

The paired v5.5.2 TableMap is derived from the user's latest field-edited
v5.5.1. It preserves all 65 manual region adjustments and all 13 additional
font samples present in that file. The first v5.5.2 field package predating
this consolidation must not be used.

The main window must display `TABLEMAP PAIRED V552=OK`. If it displays a v5.5.2
TableMap requirement, close the table connection, load the TableMap shipped in
this package, and reconnect.

## Expected live markers

Normal successful markers include:

- `gap_ms=250`
- `verify=ROW_COMMIT_OK ... evidence=RAW_VISUAL_EXACT`
- `count=FINAL_COMPLEMENT ... identity=LINEAGE_SUBSET`
- `new_deal=CURRENT_SCREEN ... lineage=RESET replan=1` when re-Fantasy deals a
  different hand
- `known new hand; runtime reset` immediately after that new canonical hand is
  published

## Field-test acceptance

Capture one complete Fantasy through final Confirm and, when available, one
re-Fantasy transition. Preserve the `.log`, the last frame before each row
transaction, the 13-card final frame, and the first empty frame of the new
re-Fantasy hand.

Fantasy 17 remains fail-closed until a real 17-card frame is captured and its
geometry is calibrated. Counts 14–16 are the enabled initial live paths.
