# M4D — exact continuation-independent delayed-Fantasy frontier

## Practical bottleneck

The exact delayed Fantasy solver is combinatorial. Before top-row envelope pruning, the number of Bottom×Middle mask pairs is:

- F14: 252,252;
- F15: 756,756;
- F16: 2,018,016;
- F17: 4,900,896.

Calling that search inside every strategic trajectory or every outer Bellman iteration would be mathematically clean and computationally wasteful.

## Exact factorization

For a fixed Fantasy packet and a completed normal opponent board, the normal opponent's Fantasy qualification and the next button are fixed. The Fantasy player's own arrangement changes only one meta-state variable: whether that player re-Fantasies.

Therefore every legal Fantasy arrangement belongs to one of at most two terminal classes:

1. no re-Fantasy;
2. re-Fantasy.

For each reachable class M4D solves the maximum **immediate** HU score exactly once. Afterwards, for any continuation vector `V`, the exact delayed response is simply:

`max(best_immediate_no + V(next_no), best_immediate_yes + V(next_yes))`

with the continuation value converted to the Fantasy player's persistent-player perspective.

This means changes to the 50-state continuation vector require only O(1) arithmetic for an already materialized terminal frontier; the 14–17-card arrangement search is not repeated.

## How constrained branches are obtained without modifying the trusted search kernel

The existing exact delayed-response solver is used twice with an artificial continuation margin. The maximum possible absolute HU hand score under the current royalty table is 103 points:

- maximum board royalties = 22 TOP + 50 MIDDLE + 25 BOTTOM = 97;
- maximum rows+scoop swing = 6;
- therefore score range is [-103,+103] and the largest immediate difference between two arrangements is 206.

M4D uses a continuation margin of 1000 points to force one qualifier branch. Because 1000 > 206, any reachable arrangement in the desired branch must beat every arrangement outside that branch. If the exact solver still returns the other branch, the desired branch is mathematically unreachable for that packet/board.

The artificial value is used only to discover the constrained exact optimum; it is discarded from the frontier. No heuristic Fantasy reward enters production evaluation.

## Authority

`EXACT_FANTASY_RESPONSE_FRONTIER` is exact for the delayed-response timing model and the certified row/Joker/scoring rules. It does not by itself prove that KKPoker always permits waiting until the normal board is complete. That timing rule remains a field-contract assumption supported by observed replays and must remain explicit.

## Strategic consequence

M4D makes outer continuation solving materially more practical. It also suggests the correct approximation boundary if terminal frontier generation remains too expensive at scale: learn/cache the two constrained immediate frontier values from exact teachers, while keeping the Bellman combination itself exact and transparent.
