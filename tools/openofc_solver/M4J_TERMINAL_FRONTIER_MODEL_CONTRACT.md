# M4J — terminal Fantasy-frontier approximation probe

## Scope

M4J is the first learned terminal approximation downstream of the exact M4I teacher corpus. It is deliberately **not** production authority. The exact M4H/M4I oracle remains the reference and fallback.

## Model

The input is the 221-dimensional lossless oracle-only M4I terminal-world feature vector. Because the quality of a Fantasy frontier is combinatorial, M4J does not use a purely additive model. It adds deterministic signed pairwise interactions among active world features and conditions those interactions on the branch:

- branch 0: leave Fantasy;
- branch 1: re-Fantasy.

The model has two independent sparse AdaGrad heads:

1. branch reachability (logistic loss);
2. immediate HU points conditional on reachability (Huber loss, normalized by the proven +/-103 point bound).

The representation is bounded by a fixed pair-hash table and has deterministic training order and payload identity.

## Safety interface

The model is not forced to answer every terminal world. At evaluation time a branch is accepted only when its reachability probability is confidently low or high. Ambiguous worlds are **abstentions** and remain candidates for exact fallback.

Held-out evaluation reports:

- branch reachability accuracy;
- reachable-branch point MAE/RMSE;
- confident-world coverage;
- mean and maximum error of the final terminal choice across a fixed grid of continuation-value deltas.

The last metric is essential: low branch-score RMSE is not enough if errors cause the wrong branch to be selected when re-Fantasy continuation value changes.

## Data split

M4I world ids are deterministic and independent of the exact labels. M4J reserves `world_id % 5 == 0` as held-out and trains on the other four buckets. Because shard ids are contiguous within each Fantasy size, the split is exactly stratifiable and cannot accidentally produce an empty held-out set in a complete five-world block.

## Promotion rule

M4J remains `APPROXIMATION_PROBE_NOT_PRODUCTION` until a Ryzen-scale corpus establishes, across independent seeds and all F14-F17 sizes:

1. stable held-out reachability accuracy;
2. bounded immediate-point error;
3. high confident coverage;
4. bounded continuation-adjusted utility error;
5. error stratification by Fantasy size and Joker count;
6. exact fallback for abstentions/out-of-envelope states;
7. a propagated strategic error budget showing how terminal approximation contributes to final exploitability.

The smoke workflow may report poor metrics and freezes no quality threshold. The next field test remains deferred.
