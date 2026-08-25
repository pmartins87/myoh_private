# OpenOFC v5.7.0 — Exact Fantasy 14–17 search kernel

## Status

This milestone replaces the old exactly-15-card, royalty-first Fantasy search
as the mathematical search authority. It does not change TableMap perception,
mouse geometry, row batching or Confirm handling.

## Exact scope

`COFCFantasyExactSolver` accepts every complete, unique physical Fantasy deal
from 14 through 17 cards, including `JK1` and `JK2`. It considers every ordered
five-card bottom/middle mask pair. For the remaining cards it constructs the
complete top-rank frontier and keeps the strongest top compatible with middle.
Weaker tops for the same remainder are admissibly dominated and cannot improve
row score, royalties or re-Fantasy.

The shared `COFCExactEvaluator` remains the only rules authority for:

- Joker substitution;
- 3/5/5 ordering and foul;
- row ranks and tie breakers;
- top/middle/bottom royalties;
- Fantasy 14/15/16/17 entry;
- KKPoker re-Fantasy: trips top or quads-or-better bottom.

The solver returns exactly 13 physical placements and `N - 13` unused physical
cards. It preserves the identity of both Jokers.

## Production authority before EV calibration

During Hero Fantasy the KKPoker presentation occludes the opponents' boards.
Immediate row points therefore cannot be known from the live screen. The exact
long-run value of re-Fantasy also has not yet been calibrated.

For that reason v5.7.0 uses a theorem-safe production rule. The exact candidate
may replace the smart baseline only if all of the following hold:

- top is at least as strong;
- middle is at least as strong;
- bottom is at least as strong;
- royalties are no lower;
- re-Fantasy is not lost;
- at least one dimension is strictly better.

Such a candidate is no worse against any terminal opponent board and does not
need an invented conversion between current points and future Fantasy value.
The complete search kernel is also the foundation for the next offline EV
calibration and MCCFR training stages.

## Mechanical evidence

The standalone C++ gate covers:

- exact Fantasy counts 14, 15, 16 and 17;
- exact physical-card coverage and `N - 13` unused cards;
- the combinatorial bottom/middle mask-pair count for every deal size;
- two physical Jokers;
- legal, non-fouled selected board;
- idempotence of the selected maximal layout;
- duplicate-card fail-closed behavior.

The 17-card deterministic test examines 4,900,896 ordered bottom/middle mask
pairs. Windows CI compiles the same code with MSVC before the Release Win32
OpenHoldem build. A second differential gate compares the production
`COFCExactEvaluator` against the certified Python rules engine over all 54
runtime card values, 2,060 rows, 1,539 non-Joker boards and 770 Joker boards.

## Next mathematical milestone

The next stage must learn the missing scalar utility from self-play rather than
guess it:

1. sample hidden opponent completions under the current strategy;
2. estimate the marginal value of continuing Fantasy;
3. solve each Fantasy deal against that calibrated terminal distribution;
4. feed exact Fantasy terminal values into External Sampling MCCFR for normal
   R4→R3→R2→R1→opening backward improvement;
5. report exploitability/regret proxies, points per hand, foul rate, royalty EV,
   Fantasy entry EV and seed stability.

External Sampling MCCFR remains the global solver. DCFR remains reserved for
bounded conditioned subgames.
