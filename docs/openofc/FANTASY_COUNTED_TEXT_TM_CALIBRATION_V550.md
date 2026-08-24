# OpenOFC v5.5.0 — Counted-text TableMap calibration

Status: replay-calibrated field-test candidate. This does not replace the live
KKPoker completion gate documented in `FANTASY_COUNTED_TEXT_V550.md`.

## Reproducible pipeline

The counted-text TableMap is produced in two fail-closed stages:

```text
original v5.4.4 Fantasy-text TM
  -> build_openofc_fantasy_counted_tm_v550.py
  -> counted regions for 6,7,8,9,11,12,13,14,15,16,17
  -> enrich_openofc_fantasy_t7_v550.py
  -> stable-frame T7 replay gate
```

Example:

```bash
python tools/build_openofc_fantasy_counted_tm_v550.py \
  KKPoker_OpenOFC_JokerUltimate_v5_4_4_FANTASY_TEXT_TEST.tm \
  counted_base.tm

python tools/enrich_openofc_fantasy_t7_v550.py \
  counted_base.tm FANTASY \
  KKPoker_OpenOFC_JokerUltimate_v5_5_0_FANTASY_COUNTED_TEXT_FIELD_TEST.tm
```

Pillow and NumPy are required only for the offline replay/calibration tools.
They are not runtime dependencies of OpenHoldem.

## Geometry contract

- Exactly 256 rank/suit regions are emitted: two regions per loose card for
  every supported stable count.
- Count 15 keeps the verified source rectangles exactly.
- Counts 6..16 use field-measured centers and inherit the verified count-15
  rotated rank/suit envelope by normalized-position interpolation.
- Count 17 is interpolated, remains explicitly uncalibrated in the TableMap,
  and is rejected by the runtime.
- Counts 1..5 and 10 are deliberately absent.

The builder rejects missing, duplicate, out-of-bounds or incomplete region
families and verifies that the opt-in symbols occur exactly once.

## Stable replay manifest

Nineteen visually audited frames cover counts 6, 7, 8, 9, 11, 12, 13, 14,
15 and 16. Transitional captures are deliberately excluded; in particular,
the supplied count-13 frame 5 still displays 15 loose cards, and count-15
frame 4 still displays 16.

The enrichment tool extracts exact T7 glyph records from the selected replay
rectangles, refuses cross-label pattern collisions, preserves the global T7
tolerance at 0.75, then executes the OpenHoldem-compatible fuzzy scan against
the final TableMap.

Current calibrated result:

```text
OPENOFC_V550_COUNTED_TM=PASS
regions=256
fantasy15=BYTE_COORDINATES_PRESERVED
fantasy17=FAIL_CLOSED

OPENOFC_V550_STABLE_REPLAY_T7=PASS
frames=19
observations=425
unique_patterns=349
decoded_fields=425
tolerance=UNCHANGED_0.75
```

Final field-test TableMap SHA-256:

```text
42f4576cf5ced80b326643bc074f1c6cbb5688fa2dadee0c998c1174f9591b35
```

## Safety boundary

This replay gate proves the supplied stable captures only. PR #13 remains
Draft and `FIELD_PACKAGE_AUTHORIZED=0` until a live Fantasy completes the full
sequence:

```text
count -> T7 identity -> policy/plan -> TOP -> MIDDLE -> BOTTOM
      -> 13-card verification -> Confirm
```

Do not set `openofc_fantasy17_calibrated=1` until a real 17-card frame has
been measured and added to the replay manifest.
