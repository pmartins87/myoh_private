# M4H — one-pass exact Fantasy frontier

## Decision from M4G

The first measured F14 exact frontier miss on GitHub Actions required 2.325493091 seconds for 504,504 constrained mask pairs, or 0.430016328 frontiers/s. A cache hit required only about 0.001411285 s. The result proves that exact memoized reuse is excellent, but a fresh two-pass Python frontier is too expensive to place naively at the terminal of very large strategic training runs.

The immediate engineering response is to remove duplicated exact work before introducing approximation.

## Exact factorization

M4D computed two continuation-independent branches by calling the full delayed-Fantasy optimizer twice:

- force no re-Fantasy;
- force re-Fantasy.

Both calls traverse the same Bottom/Middle mask pairs and rebuild equivalent row-rank structure. M4H traverses every Bottom/Middle pair once and maintains two top envelopes simultaneously. Every candidate is assigned to exactly one semantic branch:

- no re-Fantasy: Bottom is below quads and Top is not trips;
- re-Fantasy: Bottom is quads-or-better or Top is trips.

The branch maximum uses the same immediate HU scorer, row-local Joker semantics and deterministic rank/mask tie-break as the original two-pass proof.

## Authority and parity

This optimization remains exact. The original M4D two-pass frontier is retained as an independent reference oracle. The M4H gate requires deterministic physical F14 worlds to match the reference on:

- branch reachability;
- exact immediate points;
- exact next HU state;
- chosen 13 physical board cards;
- discarded physical cards;
- canonical value-record key.

Only after this parity passes does the gate measure fresh one-pass throughput for F14/F15/F16/F17.

## Practical interpretation

M4H is not a strategic-quality milestone and does not relax the field-test hold. Its purpose is to lower the cost of exact labels and establish the actual cost curve across all Fantasy sizes. If even the one-pass kernel remains too slow for in-trajectory use, exact frontiers become an offline teacher corpus and a separately certified terminal approximator is trained against them. Exact/safe fallback remains available outside the approximator's certified envelope.
