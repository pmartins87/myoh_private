# OpenOFC v5.4.3 real-Joker pixel fixture

This fixture is a clean real-pixel certification input. It is derived directly from the original replay BMP and does not use the corrupted historical HBITMAP transport, inferred pixels, synthetic Joker artwork, or expected-label-conditioned recognition.

## Provenance

- original archive source: `ofc fantasy.zip`
- original replay frame: `session_1/frame000005.bmp`
- source dimensions: `450x830`
- source BMP bytes: `1,494,054`
- source BMP SHA-256: `6ad9be294cabef91ee9d45a9fcfc9f324ed676df91a2e15d04e1db1b54e756b5`
- lossless crop ROI: `[80,98)-[290,306)`
- crop dimensions: `210x208`
- crop PNG bytes: `40,052`
- crop PNG SHA-256: `30274d1bc42b26d4254f6646079c69f7f7e4f780f35452ac8d4e5ebb5cfa2921`

The crop visibly contains the opponent arrangement from the real replay, including both physical Joker glyphs. The two Joker card rectangles in full-table coordinates are:

- red/orange Joker: `{87,104,133,166}`
- gray Joker: `{87,172,133,234}`

Other visible cards in the crop provide provenance/context but are not used as labels to guide the Joker recognizer.

## Transport

The PNG is transported as seven deterministic ASCII Base64 chunks under `b64/`. `tools/materialize_openofc_real_joker_frame5.py` verifies each text file by Git-blob SHA-1, validates strict Base64 syntax and exact chunk lengths, decodes exactly 40,052 bytes, then checks the final SHA-256 and PNG IHDR dimensions before materializing the image.

Expected chunk Git-blob SHA-1 values:

- `00`: `c1e1331860040279badd49156d1e5165cec4bd93`
- `01`: `bc65f5346f3ce940bd7ed2c88117c82b8d3263a1`
- `02`: `97bcf43c3850f84615b5472be5933a9397017648`
- `03`: `fb109f9bb6b08a9e33b4608f2afb7ed012581735`
- `04`: `88604f565aa25dae455703ec4a66eaa99947b644`
- `05`: `45c7fb7c538f71080772dd76d5a70586f15eb649`
- `06`: `05de489cb57e770d0738f6ba337ca140a84a3a68`

## Certification rule

The runtime gate must compose the lossless crop into a native top-down `450x830` HBITMAP at `(80,98)` and call the ordinary production `COFCFantasyPixelRecognizer::RecognizeArrangementSlots()` API on the two real Joker rectangles. It must recognize the first object as `JK1` and the second as `JK2`, with both occupied and physically unique.

`RecognizeArrangementSlotsAgainstExpected()` is explicitly forbidden for this gate because expected labels must not participate in classification.

Until the native Windows gate passes, the status remains:

`REAL_JOKER_PIXEL=NOT_YET_CERTIFIED`

Even after this gate passes, field authorization remains separate:

`FIELD_PACKAGE_AUTHORIZED=0`
