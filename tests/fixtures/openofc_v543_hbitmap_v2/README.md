# OpenOFC v5.4.3 HBITMAP v2 fixture corpus

This directory is the clean replacement for the corrupted historical HBITMAP transport fixture.

Canonical source provenance:

- `session_1/frame000033.bmp`, SHA-256 `42f004127d6de384cd4607ace71a102c92a458fa21e6e357b2e3155a0c84dd15`.
- `session_1/frame000036.bmp`, SHA-256 `9a33a07c992e5b85f741c96ae4e14e6e26cb142aedb1dfa4a4400df2728d1737`.

Required v2 crops from `frame000036`:

- arrangement ROI `[112,414)..[381,627)`, 269x213, PNG bytes 56386, SHA-256 `826f786d8c5b47a2e85b1d0195626dff70cb0a9c031a90c254b8807f7bceca50`;
- loose ROI `[20,630)..[430,735)`, 410x105, PNG bytes 49363, SHA-256 `ce6a83ff71aca8cf3b760a50f0f42b46ceb8ced2365da4a1ec571078e9195524`.

Expected production recognition:

- arranged bottom row: `Js 9s 7s 6s 3s`;
- loose, left to right: `Ah Ac Kh Jd Tc 9c 6h 5h 3c 2s`;
- union: exactly 15 unique physical cards.

The crop transport is considered valid only after exact chunk/blob verification and exact decoded byte SHA verification. No fuzzy repair, inferred bytes, or frame-specific recognition exception may satisfy this gate.

`FIELD_PACKAGE_AUTHORIZED=0`
