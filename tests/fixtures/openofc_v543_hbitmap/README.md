# OpenOFC v5.4.3 real-pixel HBITMAP fixtures

These fixture crops are derived losslessly from the user's KKPoker/OpenHoldem v5.3 field-failure replay frames. They are not synthetic card renders and are not feature-level substitutes.

The native test reconstructs a 450x830 HBITMAP and copies the exact decoded RGB pixels back into the coordinates consumed by the production recognizer. Pixels outside the exercised recognizer regions are intentionally blank and are never used by the tested recognition path.

## Provenance

- `field_frame000000_loose.png`
  - source frame: local field replay `frame000000(2).png`
  - source full-frame SHA-256: `d8b71ee5d07ae6d9b28abf9f9fe6f9b9e9b4d0b2ca1e3db69973e4ddc1ec04fe`
  - exact crop: `[20,630) .. [430,735)` (410x105)
  - crop SHA-256: `0da9c2a507071eab052f78f88c1f376be88005c5894976f26628964e960cd729`
  - purpose: active Fantasy initial field state, 15 current loose cards, including both physical Jokers.

- `field_frame000005_arrangement.png`
  - source frame: local field replay `frame000005(1).png`
  - source full-frame SHA-256: `74455719bd15970ac4e2a750f6055536d40bf391c0f71cdb007264ebbce5afb3`
  - exact crop: `[112,414) .. [381,627)` (269x213)
  - crop SHA-256: `71a8cc1e67122a0de140402209ca7c5cc37ce78d1b96702e1380c303295a60d0`
  - purpose: five current tentative Hero placements in the bottom row.

- `field_frame000005_loose.png`
  - source frame: local field replay `frame000005(1).png`
  - source full-frame SHA-256: `74455719bd15970ac4e2a750f6055536d40bf391c0f71cdb007264ebbce5afb3`
  - exact crop: `[20,630) .. [430,735)` (410x105)
  - crop SHA-256: `6c02d4e6c2d9900ce75c705b3e4cf9c4fca04308e75eb4cc4ca115a1d7749bbd`
  - purpose: ten loose Hero cards in the same partial-arrangement field state.

## Gate contract

`COFCFantasyHBitmapSelftest.cpp` must prove, through the production HBITMAP pixel recognizer:

1. the initial field crop yields 15 unique physical cards and preserves `JK1` and `JK2`;
2. the partial field state yields exactly five arranged + ten loose cards;
3. the exact physical-card union is 15 unique cards;
4. the result can bootstrap `COFCReconstructor::ReconstructCurrentScreen` with no prior process state;
5. missing dealer identity remains explicit uncertainty and does not invalidate the current-screen Fantasy state.

This fixture gate does **not** certify unseen real initial-fan geometries for counts 14, 16 or 17. Those counts are covered by the native state/policy gate; real pixel captures are still required for geometry-specific field certification.

`FIELD_PACKAGE_AUTHORIZED=0` until the complete packaging/traceability gate explicitly changes it.
