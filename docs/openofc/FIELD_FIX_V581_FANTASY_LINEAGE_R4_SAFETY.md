# OpenOFC v5.8.1 — Fantasy staged-lineage recovery and R4 safety

## Field failures reproduced

The 2026-08-25 v5.8.0 log contains two different cases.

### Fantasy stopped after TOP

The initial Fantasy set had 14 physical cards. After the TOP commit the fresh
screen correctly contained three arranged cards and eleven loose cards. One
count-specific T7 field nevertheless returned a different, valid-looking
identity. Set subtraction therefore produced four apparent arranged cards:

```text
prior=14 occupied=3 loose=11 expected_arranged=4
```

v5.8.0 rejected every later frame and never reached MIDDLE.

v5.8.1 accepts only the uniquely provable one-card form of this discrepancy:

1. `prior == occupied + loose` must still hold exactly;
2. the lineage delta must be exactly one;
3. the upright arranged glyphs must match three of the four lineage candidates;
4. exactly one candidate and exactly one off-lineage loose source must remain;
5. replacing that source identity must recreate the original physical set
   exactly, without duplicates.

When all five proofs hold, the source rectangle is preserved, only its identity
is corrected, a BMP+HTML replay is requested, and execution continues. Any
second divergence or ambiguous assignment remains fail-closed.

This protects all operational partitions: 14–17 initial cards, 11–14 after
TOP, 6–9 after MIDDLE, and 1–4 inferred unused cards after BOTTOM.

### Frame 000 normal R4

The exact state was:

```text
TOP:    Ad As --
MIDDLE: 9d Jd Qd Kd --
BOTTOM: 6h 2d 6d 3s Qs
R4:     Ah 6s JK1
```

All 27 discard/row assignments were enumerated. There were zero non-foul
completions: TOP was already at least a pair of Aces, BOTTOM was only a pair of
Sixes, and no remaining assignment could build a compatible MIDDLE. The foul
was therefore created before R4; changing the last click cannot repair it.

The v5.8.1 R4 teacher now exposes this proof in telemetry (`baseline_foul`,
`selected_foul`, `safe_candidates`, `opponent_terminal`). It also fixes the
general missing-opponent case: if the baseline would foul but any non-foul Hero
completion exists, that completion is selected even before the opponent's last
two cards are visible. If the baseline is already safe, hidden opponent data is
not guessed and the existing policy remains unchanged.

Avoiding the specific frame-000 trap earlier than R4 remains an information-set
solver problem for the non-dealer R3/R2 policy. v5.8.1 does not mislabel that
larger milestone as solved.
