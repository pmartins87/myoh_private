# M4W — own-information continuation-outcome model

## Purpose

M4V proved that, for fixed candidate supports and a fixed opponent support
mixture, every exact action value is linear in the current 50-state continuation
vector:

`Q_a(V) = immediate_a + Σ_s c[a,s] V(s)`.

M4W changes what the generalizer learns. Instead of fitting one scalar Q that is
valid only at the continuation vector used to generate the corpus, the new probe
learns two continuation-independent quantities from the same M4P own-information
state/action features:

1. player-perspective expected immediate current-hand utility;
2. a categorical distribution over the **25 possible next Fantasy-mode pairs**
   `(P0 mode, P1 mode)`, where each mode is `0/14/15/16/17`.

The next button is deterministic HU alternation, so 25 mode pairs are sufficient
to reconstruct the reachable next state. At policy inference the current Bellman
vector is applied only after the model predicts those quantities:

- P0: `Q = immediate + E[V(next_state)]`;
- P1: `Q = immediate - E[V(next_state)]`.

Thus changing `V` no longer makes the learned target definition itself stale.

## Information firewall

`SparseFantasyOutcomeModel.policy_for_private_support(...)` accepts:

- the model;
- the acting player's own packet;
- that player's own candidate support;
- public current HU meta-state;
- player identity;
- current continuation vector;
- temperature.

There is no opponent packet, opponent board, complete sampled world or payoff
matrix argument. The continuation vector is public solver state, not hidden poker
information.

Complete-world information is used only by the offline exact M4U/M4V teacher to
create immediate/outcome labels.

## Target semantics

M4V stores signed next-state coefficients because the global continuation vector
is always from persistent P0 perspective. M4W converts them to an ordinary
positive probability target:

- P0 M4V coefficients sum to `+1` and are used directly;
- P1 M4V coefficients sum to `-1` and are sign-reversed to probability mass.

The model therefore learns one physically interpretable transition distribution
for either player, while perspective enters only when Q is reconstructed.

## Probe model

The first M4W implementation is deliberately bounded and CPU-friendly:

- same lossless own-information M4P state/action features;
- same deterministic hashed state×action interactions used by the M4Q family;
- one sparse Huber/AdaGrad immediate-utility head;
- 25 sparse softmax/AdaGrad next-mode heads;
- deterministic example ordering by seed and epoch;
- model payload exposes optimizer state for reproducibility diagnostics.

This architecture is a **probe**, not the final capacity choice. M4S-style
held-out measurement must determine whether its immediate and transition errors
are acceptable.

## Exact structural gate

Before measuring approximation quality, M4W proves that its target semantics are
correct. The regression gate:

1. creates a real sealed F14/F15 sampled world;
2. builds exact M4U factorized support payoffs;
3. builds exact M4V targets under non-uniform opponent mixtures;
4. converts them to M4W immediate + transition-distribution labels;
5. reconstructs Q under two materially different 50-state continuation vectors;
6. requires equality with the independent M4V exact Q values to `1e-12` for both
   players;
7. verifies the inference API has no hidden-opponent/full-world surface;
8. verifies untrained equal-Q support is uniform;
9. verifies repeated training with identical seed/examples is deterministic.

A gate PASS therefore certifies target transport and information plumbing only;
it is not a strategic-quality PASS.

## What M4W solves

The scalar-Q continuation-anchor problem is removed from the learner interface.
One trained outcome model can, in principle, be evaluated against different
Bellman vectors without redefining its labels.

This also means M4U's exact SHA firewall remains useful: the old scalar M4Q/M4R
path stays bound to its certified anchor, while a future promoted M4W path can
have a different certification contract based on outcome prediction error.

## Remaining hard problem

The **candidate support** is still continuation-dependent. M4O proposes actions
using exact teachers under one supplied `V`; a different continuation vector may
make an omitted arrangement optimal. M4W does not claim otherwise.

The opponent support policy also changes with `V`, but this part is comparatively
cheap: M4V coefficients can be recomputed from an already factorized support
matrix once a new opponent mixture is available.

## Next milestone

M4X should attack support robustness directly. It should evaluate one own packet
against a declared family of continuation vectors and measure the union-support
missed-best-response gap with the unrestricted M4N teacher. The family must be
constructed with explicit provenance and bounded range rather than arbitrary
hand-picked bonuses.

If a compact union support remains accurate across that family, the expensive
M4O generation can become an offline support-construction step while M4W handles
fast continuation-aware policy evaluation inside the outer 50-state solve.
