# OpenOFC v5.4.3 HBITMAP v2 rebuild

## Decision

The legacy `openofc_v543_hbitmap` fixture transport is no longer a release blocker. It remains historical/provenance evidence only.

We are not rebuilding the OpenOFC recognizer from scratch. The production recognizer already passed a byte-verified real-pixel replay on `frame000033`. What is being rebuilt from zero is the **real-pixel HBITMAP certification corpus** so that no certification depends on partially recovered/corrupted Base64 from an old fixture.

`HBITMAP` is only the native Windows in-memory bitmap handle consumed by the production recognizer. It is not a file format and it is not the source of truth for the fixture. The source of truth is a lossless crop derived from an original replay frame with explicit provenance and hashes; CI decodes that crop into an HBITMAP and then calls the production recognizer.

## Clean source corpus

Source archive: user-supplied `ofc fantasy.zip`.

### Initial Fantasy screen

- source: `session_1/frame000033.bmp`
- source BMP size: `450x830`
- source BMP SHA-256: `42f004127d6de384cd4607ace71a102c92a458fa21e6e357b2e3155a0c84dd15`
- loose-card crop: `[20,630)..[430,735)` = `410x105`
- crop PNG bytes: `51149`
- crop PNG SHA-256: `36968956aa18c59d323e3a15be9fb74d86d33d873c993da158c8ee7e285fb1b9`
- expected physical cards: `Ah Ac Kh Js Jd Tc 9s 9c 7s 6s 6h 5h 3s 3c 2s`
- expected count: `15 loose / 15 unique`

This image has already passed the production path:

`PNG -> native HBITMAP -> RecognizeLooseObjectsUnbound() -> 15 exact cards -> COFCReconstructor`.

### Partial arrangement screen

- source: `session_1/frame000036.bmp`
- source BMP size: `450x830`
- source BMP SHA-256: `9a33a07c992e5b85f741c96ae4e14e6e26cb142aedb1dfa4a4400df2728d1737`
- arrangement crop: `[112,414)..[381,627)` = `269x213`
- arrangement PNG bytes: `56386`
- arrangement PNG SHA-256: `826f786d8c5b47a2e85b1d0195626dff70cb0a9c031a90c254b8807f7bceca50`
- arrangement PNG Git blob SHA-1: `c21e13bcbe1e1764c2c8a6c572185d281bb6524a`
- loose-card crop: `[20,630)..[430,735)` = `410x105`
- loose PNG bytes: `49363`
- loose PNG SHA-256: `ce6a83ff71aca8cf3b760a50f0f42b46ceb8ced2365da4a1ec571078e9195524`
- loose PNG Git blob SHA-1 after materialization must be `2f435fcdfec8644c99a63295736e45dbbee8578c`
- expected arranged bottom row: `Js 9s 7s 6s 3s`
- expected loose cards: `Ah Ac Kh Jd Tc 9c 6h 5h 3c 2s`
- expected union: `5 arranged + 10 loose = 15 unique physical cards`

The arrangement PNG is attached directly as a binary Git blob. The loose crop is transported as deterministic 8,000-character Base64 chunks and must decode to the exact SHA-256/Git-blob values above before any recognizer assertion is accepted.

## Joker coverage

Dual-Joker recognition remains a separate real-pixel sub-gate. It must be rebuilt from the original `joker_ofc_frames_and_rules.zip` BMP frames, not reconstructed from the corrupt legacy HBITMAP fixture. No synthetic Joker image may satisfy this gate.

## v2 certification rules

1. Every fixture must have an original replay-frame provenance record.
2. Every source frame and every lossless crop must have a frozen SHA-256.
3. Transport to GitHub must be independently hash-verifiable before recognizer execution.
4. CI must compose a native `450x830` HBITMAP and call production recognizer entry points.
5. No frame-specific recognition exception may be added to make a fixture pass.
6. The initial screen must prove exact count and identities.
7. The partial screen must prove arrangement + loose union and fresh-process reconstruction.
8. Joker coverage is independent and must use real captured pixels.
9. The old partially recovered `field_frame000000_loose` transport cannot block v2 once equivalent behavior is certified from clean original frames.
10. `FIELD_PACKAGE_AUTHORIZED=0` until v2 real-pixel, Joker, runtime/build and packaging/traceability gates are all green.

## Execution order

- V2-A: transport/materialize `frame000033` and `frame000036` clean crops with hash checks.
- V2-B: native HBITMAP initial + partial recognizer/reconstructor regression.
- V2-C: rebuild real Joker corpus from original BMP frames and certify physical Joker identity.
- V2-D: run generic Fantasy, bounded recovery, continuity, real-pixel, Joker and Release|Win32 gates together.
- V2-E: only then decide field-package authorization.

The previous historical fixture remains available for forensic comparison, but it is not repaired further unless an original byte-identical source becomes available.
