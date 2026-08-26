# M4C2 — bounded action-conditioned strategic generalization

## Purpose

M4 established that the exact suit-canonical tabular MCCFR implementation is a valuable oracle and correctness harness but is not a practical global representation: the early feasibility run created almost one new information-set key per decision node. M4B then coupled normal-hand utility to the exact cross-hand Fantasy continuation state instead of optimizing only the current hand. M4C preserved all strategically visible information in a fixed lossless feature contract.

M4C2 adds the first bounded learned representation on top of those foundations. It is intentionally an approximation and therefore carries no exact-solver authority.

## Representation

`strategic_advantage_model.py` receives the lossless M4C state features and the complete legal action features. A direct linear concatenation would be strategically inadequate because state coefficients cancel when comparing actions and action coefficients cannot depend on the board. M4C2 therefore adds deterministic signed-hashed **state x action interaction features**.

The default model has:

- 1 global bias;
- 216 direct action coordinates;
- 65,536 bounded interaction buckets;
- sparse AdaGrad state;
- Huber regression loss;
- no Python randomized hash dependency;
- no hidden-card, future-card or determinization input path.

The initial model is deliberately simple and auditable. It is a generalization probe, not the final architecture. A deeper CPU model is justified only if this bounded layer establishes that the held-out signal is learnable and identifies where linear interactions saturate.

## Bounded replay and exact resume

`DeterministicReservoir` bounds training memory and uses a counter-derived SplitMix64 selection rule equivalent to reservoir replacement. The selection decision depends only on `(seed, seen_count)`, so checkpoint resume does not depend on serializing an opaque random-generator state.

The checkpoint contains:

- model hyperparameters;
- sparse weights;
- AdaGrad accumulators;
- epoch/update counters;
- replay capacity, seed, seen count and retained examples;
- canonical SHA-256 integrity hashes.

The gate requires resumed training to produce byte-equivalent logical model/replay payloads to uninterrupted training.

## Exact teacher distillation

`strategic_policy_distillation.py` keeps the learned model downstream of the exact MCCFR table. The model does **not** steer the solver in M4C2.

For each exact information set, the tabular average strategy is converted into one action-conditioned target per legal action. Training weight grows only logarithmically with exact node visits. This provides a stable first supervised target while retaining exact MCCFR as authority.

A deterministic SHA-256 split reserves one fifth of exact information states as held-out states. No examples from that split are admitted to training by default. Evaluation reports:

- mean per-state policy L1 error;
- per-action RMSE;
- top-action agreement;
- target-policy entropy;
- exact counts of evaluated states/actions.

A held-out metric is a generalization diagnostic, not an exploitability certificate.

## Promotion rule

M4C2 cannot be promoted to production merely because training loss decreases. The strategic model must eventually satisfy all of the following layers:

1. stable held-out improvement across multiple independent deal seeds;
2. late-round calibration against exact R4 and R3 teachers;
3. continuation-coupled evaluation under the M4B Bellman objective;
4. best-response / exploitability diagnostics on sampled unabstracted subgames;
5. seed stability and no hidden-information leakage;
6. production distillation with a fallback to exact/safe logic whenever confidence is outside the certified envelope.

The next live field test remains deferred until the normal-game strategic model is ready for production integration. Field perception/runtime work can continue mechanically in parallel, but it is not the promotion gate for the intelligence track.
