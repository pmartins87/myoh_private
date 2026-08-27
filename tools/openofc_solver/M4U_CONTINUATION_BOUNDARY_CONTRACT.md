# M4U — continuation-safe certification boundary

## Why M4U exists

M4S measures the sealed Fantasy/Fantasy stack for one explicit continuation
vector and M4T decides whether the measured support, policy and function errors
meet explicit budgets. The outer 50-state Bellman solve then changes that
continuation vector.

That creates a dangerous boundary: a policy certified at `V0` is not
automatically certified at `V1`.

This is not a bookkeeping detail. M4O proposal support, M4P payoff values and
M4Q/M4R action-value targets all depend on `V(next_state)`. M4Q's inference
features currently contain own packet, public meta-state and own action, but no
continuation vector. Reusing one M4S certificate after Bellman changes `V` would
therefore be an unsupported strategic extrapolation.

M4U makes the dependency fail closed before the outer iteration is allowed to
consume sealed Fantasy/Fantasy approximations.

## SHA-bound certification manifest

`freeze_certification(...)` consumes:

- a valid SHA-bound M4T plan;
- one of the exact M4S reports that participated in that plan;
- an explicit human/machine provenance string.

It refuses to create a manifest unless:

- all four numeric M4T targets are explicit;
- the M4S report belongs to the exact M4T experiment signature;
- the report SHA is one of the plan inputs;
- at least one **complete progressive coverage tier** is present and
  `STATE_BUDGETS_PASS`.

The resulting `openofc-m4u-continuation-certification-v1` artifact freezes:

- M4T plan SHA;
- source M4S report SHA;
- generator fingerprint;
- exact continuation fingerprint;
- numeric error targets;
- complete certified state tiers;
- provenance;
- its own SHA-256.

The artifact permanently keeps `promotion_blocked=true`; it is routing evidence,
not a final equilibrium claim.

## Outer-solve firewall

`certification_route(...)` returns `CERTIFIED_APPROXIMATION_ALLOWED` only when:

1. the queried state is Fantasy/Fantasy;
2. that exact state belongs to a complete certified tier;
3. the supplied 50-state continuation vector has exactly the same SHA as the
   continuation vector measured by M4S.

Any changed Bellman iterate is blocked. No epsilon, rounding or "close enough"
comparison is hidden inside this gate.

This means the current architecture **cannot yet run an unrestricted outer
fixed-point iteration using one frozen M4Q/M4R policy**. That is an important
result: M4U prevents us from spending compute on a mathematically invalid loop.

## Exact continuation transport for fixed supports

M4U also factors every exact M4P support cell into:

`immediate_p0_points + V(next_state)`.

`build_factorized_support_payoff(...)` computes the poker score and exact next
state once. `materialize_factorized_payoff(...)` then reconstructs the ordinary
M4P payoff matrix for any complete continuation vector using only table lookup
and addition.

Regression tests compare this rematerialization against the independent existing
`build_exact_support_payoff_matrix(...)` under multiple continuation vectors and
require exact equality.

This removes repeated poker scoring when `V` changes, but deliberately makes no
claim that a support generated for `V0` still contains a near-best action for
`V1`.

## What remains continuation-dependent

Three layers still need a transport proof or a continuation-aware redesign:

1. **M4O support** — its exact teacher ranks proposals using `V`;
2. **M4R sealed policy** — the best mixture can change with `V`;
3. **M4Q action-value model** — its current inference feature contract does not
   include `V`.

Therefore M4U does not weaken M4T's thresholds and does not invent a local
trust-region radius from smoke data.

## Next milestone

M4V should remove the expensive continuation dependence structurally rather than
rerunning the whole corpus for every Bellman iterate. The preferred direction is
to train/factor the sealed policy on continuation-relevant terminal outcomes:

- immediate score;
- exact next-state identity/distribution;
- candidate-support robustness across a declared continuation family.

That would allow Q-values for a new `V` to be reconstructed from
`immediate + E[V(next_state)]` while preserving the hidden-information firewall.
Until that proof exists, the outer continuation loop remains blocked whenever
its `V` differs from the certified M4S anchor.
