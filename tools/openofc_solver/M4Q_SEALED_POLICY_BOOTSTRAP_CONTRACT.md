# M4Q — sealed Fantasy action-value bootstrap

## Scope

M4P provides exact support payoffs and a lossless own-information feature
contract. M4Q adds the first bounded generalizing model that can map

    (own private Fantasy packet, public HU meta-state, candidate arrangement)

into an action-value estimate and then a normalized policy over an M4O support.

This milestone is deliberately labelled **bootstrap**, not equilibrium.

## Training-label contract

`fantasy_fantasy_bootstrap.py` constructs action-value labels from one exact M4P
support payoff matrix and an explicitly supplied opponent mixture.

For player 0 candidate `i`:

    Q0(i) = sum_j sigma1(j) * A[i,j]

For player 1 candidate `j`:

    Q1(j) = -sum_i sigma0(i) * A[i,j]

where `A` is exact P0 utility `current points + V(next state)`.

If a mixture is omitted, the module uses a clearly declared uniform support
mixture. Uniform is a bootstrap baseline only. It is never described or stored
as a solved opponent policy.

Although complete-world information is necessarily used to create these offline
labels, each emitted `FantasyPolicyExample` contains only M4P own-information
state features, candidate-action features, target, weight and source metadata.
No opponent card identity survives into model inference input.

## Generalizing model

`SparseFantasyActionValueModel` is a Fantasy-specific adaptation of the bounded
M4C2 engineering pattern:

- direct sparse candidate-action membership terms;
- deterministic signed-hashed state x action interactions;
- Huber regression;
- sparse AdaGrad optimizer;
- deterministic training order;
- deterministic bounded reservoir replay;
- SHA-bound checkpoint payloads;
- gzip checkpoints with fixed `mtime=0` for byte-stable compression;
- softmax action selection restricted to the supplied M4O support.

The M4P state/action feature ranges are used directly. M4Q does not reuse the
normal-game feature semantics from M4C2.

## Authority boundary

Model authority is permanently tagged

`STRATEGIC_BOOTSTRAP_GENERALIZATION_NOT_EQUILIBRIUM`

for this milestone. A low training loss cannot upgrade that authority. Promotion
requires iterative strategic training and held-out deviation diagnostics.

## Error-budget decomposition

The Fantasy/Fantasy approximation now has explicit layers:

1. **M4O support gap**: unrestricted exact M4N teacher minus best action in the
   bounded support on held-out complete worlds;
2. **M4P within-support deviation gain**: strategic gain available by changing
   action inside the bounded matrix;
3. **M4Q function-approximation error**: predicted action value/policy versus
   exact M4P targets under the declared opponent mixture.

These budgets must remain separately reportable. They must not be collapsed into
one opaque "accuracy" number.

## Gate

M4Q regression requires:

- bootstrap targets exactly reproduce M4P matrix expectations;
- arbitrary non-negative opponent weights are normalized explicitly and produce
  the corresponding exact targets;
- two same-seed training runs produce identical model/replay payloads;
- inferred support policy is finite, positive and normalized;
- save/load round-trip preserves model and replay exactly;
- authority remains bootstrap-only.

## Next milestone

M4R should replace the fixed bootstrap mixture with an iterative sealed strategic
loop. A practical first candidate is double-oracle/fictitious-play style support
iteration: evaluate current mixed supports exactly with M4P, generate best-response
pressure with M4N/M4O, retrain the own-information model, and measure both support
gap and within-support deviation on held-out multiseed worlds. No equilibrium
claim should be made until those diagnostics stabilize under an explicit error
budget.
