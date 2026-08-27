# M5B-A — continuation-aware M4W fitted self-play

## Purpose

M5A made all three HU kernel classes evaluable through fixed policy/model
adapters. That is necessary plumbing but still only policy evaluation. M5B-A
starts the policy-improvement layer for the 32 sealed Fantasy×Fantasy states.

The old M4R scalar-Q learner was tied to one continuation vector. M5B-A instead
uses the M4W learned object: player-perspective immediate utility plus the
probability distribution over the 25 next Fantasy-mode pairs.

## Synchronous self-play step

For every offline episode with fixed own-information supports:

1. evaluate the current M4W sealed policies under the current V;
2. freeze both opponent mixtures;
3. use the exact M4U immediate+next-state factorization;
4. lift those factors through the frozen mixtures with M4V;
5. convert the exact linear targets into M4W continuation-independent outcome
   examples;
6. fit the M4W model synchronously;
7. re-evaluate exact support-restricted unilateral-deviation diagnostics.

The complete chance world and factorized payoff are offline teachers only. The
policy-facing API remains own packet + own support + public meta-state + V.

## Why this matters

The policy can change as V changes without retraining its target definition from
scratch: immediate utility and next-state distributions remain meaningful across
continuation vectors. Opponent mixtures are nevertheless re-frozen at the
current V on every fitted self-play iteration, so strategic response is not
assumed invariant.

## Evidence boundary

The report records before/after mean and maximum support-restricted deviation,
training loss and example count. A lower training loss or a smoke-test decrease
in deviation is **not** an equilibrium certificate.

Full-game quality still requires:

- M4X exact-teacher support-gap evidence over the relevant Bellman region;
- held-out worlds/seeds;
- explicit deviation/error thresholds;
- stability across fitted iterations and continuation anchors;
- eventual outer 50-state Bellman convergence plus global strategic validation.

Authority:

`CONTINUATION_AWARE_M4W_FITTED_SELFPLAY_PROBE_NOT_EQUILIBRIUM`

## Next

Add the analogous train-at-current-V improvement wrappers for Normal×Normal and
Normal×Fantasy, then freeze a fail-closed M5B route certificate that can promote
M4Z routes only from held-out evidence rather than from component existence.
