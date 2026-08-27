# M4R — generalized sealed Fantasy self-play probe

## Purpose

M4Q can learn own-information candidate action values under a declared opponent
mixture. M4R replaces the fixed mixture with the current learned sealed policy
and performs synchronous fitted self-play updates on exact M4P support matrices.

This remains a strategic probe. It is not yet an equilibrium certificate.

## Inference firewall

The runtime-facing function `policy_for_private_support` accepts only:

- the learned M4Q model;
- one player's own Fantasy packet;
- that player's candidate support;
- public HU meta-state and player identity;
- temperature.

Its signature has no opponent packet, opponent board, complete world or payoff
matrix argument. It constructs only M4P own-information features before asking
the model for support probabilities.

## Offline synchronous update

For each complete sampled training episode:

1. freeze the current model;
2. infer P0 and P1 support policies independently from their own private packets;
3. use the exact M4P payoff matrix to compute each candidate's exact expected
   action value against the *frozen* opponent policy;
4. collect both players' own-information M4Q examples;
5. only after all episodes have produced targets, add them to deterministic
   replay and fit the model;
6. re-evaluate the updated model on the same exact matrices for diagnostics.

The synchronous ordering prevents one player in an episode from seeing an update
that the other player did not have when its labels were generated.

## Diagnostics

Every episode reports the exact M4P support-restricted unilateral-deviation gap
under the current sealed policies. M4R aggregates mean and maximum gap before and
after each fitted iteration.

A single iteration is not required to reduce the gap monotonically: function
approximation, finite replay, bounded action support and softmax temperature can
all produce non-monotone fitted policy dynamics. Promotion must therefore rely
on multiseed held-out trends and explicit error budgets rather than a fragile
one-step assertion.

## Authority

M4R is permanently tagged

`GENERALIZED_SEALED_SELFPLAY_PROBE_NOT_EQUILIBRIUM`

until later gates demonstrate strategic stability and bounded exploitability-like
error under independent held-out worlds.

## Existing three-part error budget

1. **M4O support gap** against unrestricted M4N teacher;
2. **M4P support-restricted deviation gain** under the learned policy;
3. **M4Q/M4R function/generalization error** on exact matrix-derived targets.

M4R does not erase or merge these budgets.

## Gate

The regression gate requires:

- inference API exposes no hidden-opponent/full-world argument;
- an untrained zero model produces the expected uniform support policy;
- first self-play labels equal exact uniform-opponent M4P expectations;
- same seeds/episodes produce byte-logically identical model and replay states;
- iteration reports remain finite and non-negative where mathematically required;
- a second target generation uses the newly updated sealed opponent policies;
- authority remains explicitly non-equilibrium.

## Next milestone

M4S should add a deterministic multiseed episode/corpus runner with independent
train/held-out splits, M4O proposal generation, iterative M4R training and a
machine-readable report containing all three error budgets by Fantasy count,
player, Joker count and opponent Fantasy-count pairing. Those measurements will
decide whether candidate-support size, synthetic-world count, model capacity and
self-play temperature need expansion before any continuation fixed-point solve.
