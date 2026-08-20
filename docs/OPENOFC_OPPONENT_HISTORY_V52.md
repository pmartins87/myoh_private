# OpenOFC opponent history v5.2

## Purpose

Opponent discard identities are strategically valuable and are **not** gameplay gates.
They are terminal evidence used to reconstruct how the opponent played every normal
OFC round and to build player-specific statistics/exploitation models.

## Evidence model

During R0..R4 the runtime keeps the latest complete public board snapshot for both
players whenever the opponent board reaches the legal committed totals:

- R0: 5 cards
- R1: 7 cards
- R2: 9 cards
- R3: 11 cards
- R4: 13 cards

The snapshot for a round is overwritten while the same complete total remains
visible, so the last stable arrangement is retained before the next round grows the
board.

At the scoring/result transition the opponent's four hidden discards turn face-up.
The **first face-up discard edge** is the durability trigger:

1. save the current 450x830 table bitmap to `OpenOFC_Data/opponent_frames/`;
2. append a `REVEAL_EDGE_PARTIAL` hand envelope to
   `OpenOFC_Data/opponent_hands.jsonl` immediately;
3. keep reading the four discard identities passively across subsequent frames;
4. once all four are recognized, append a terminal upgrade with the same `hand_id`;
5. if all five round snapshots are present, terminal status is `COMPLETE_REVEAL`.

If a font/glyph is missing, gameplay continues. The evidence frame and partial hand
remain available for later calibration/reprocessing.

## Exact normal-round reconstruction

R0 is fully public after commitment, so its five incoming cards equal the five cards
in the opponent R0 board snapshot.

For R1..R4:

`added_cards = board_after - board_before`

There must be exactly two added board cards. The chronological result-discard slot
for that round supplies the third card:

`incoming = added_cards + discard[round-1]`

The row containing each added card in `board_after` gives its exact placement. Thus a
complete terminal reveal reconstructs all opponent incoming triples, both placements
and every discard without trying to scrape hidden discard identities during play.

## Identity

The clean TableMap restores player-name OCR as OFC-native regions (`ofc_p0_name`,
`ofc_p1_name`). The SQLite importer reuses `PlayerAliases` from `oppdb.db` when that
table exists, matching the AoF identity model.

## SQLite import

Runtime C++ writes a dependency-free append-only outbox. SQLite ingestion is kept out
of the real-time mouse/scrape process so a database lock or schema migration can never
freeze play.

Importer:

`python tools/import_openofc_opponent_hands.py --jsonl OpenOFC_Data/opponent_hands.jsonl --db oppdb.db`

Namespaced tables:

- `OFCHandAudit`
- `OFCReconstructedActions`
- `OFCOpponentCoverage`

Only exact complete reconstructions receive `ActionStatsEligible=1`.

## Next statistics gate

After field evidence proves the collector, the next layer will aggregate opponent
placement/discard tendencies conditional on round, dealer status, public Hero board,
opponent board and incoming composition. Those player-specific distributions can then
be compared against the baseline policy to estimate exploitability/edge and later feed
an opponent-aware policy.
