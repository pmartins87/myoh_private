# M5A-A — Normal×Fantasy visible-policy state-value adapter

## Purpose

M4Z needs a one-hand value oracle for every one of the 50 HU continuation states.
M5A-A closes the first integration seam for the 16 asymmetric Normal×Fantasy
states without weakening the information boundary.

This milestone is **fixed-policy evaluation**, not Bellman optimality. It does
not by itself turn any M4Z route into `READY_CERTIFIED`.

## Visible policy contract

The policy receives only the exact suit24 canonical Normal×Fantasy key and its
public legal action keys. The accepted state schema contains:

- persistent normal/fantasy identities and button;
- Fantasy packet **count** (14..17), never its cards;
- current normal round;
- normal player's own board;
- normal player's remembered discards;
- current normal incoming packet.

The encoder rejects extra fields. `fantasy_packet`, complete deal plans, hidden
opponent cards, worlds and payoff matrices therefore cannot enter the policy
surface accidentally.

The action encoding reuses the normal/normal strategic action range; the delayed
Normal×Fantasy metadata occupies a collision-free prefix of the otherwise unused
opponent-board state range.

## Distillation

`normal_fantasy_policy_distillation.py` converts visited M4L tabular average
policies into the existing sparse action-conditioned model. The exact tabular
M4L node remains the teacher. Holdout keys use the existing stable SHA split.

A frozen policy snapshot records:

- model SHA-256;
- SHA-256 of the continuation vector used to train the source policy;
- provenance;
- snapshot SHA-256.

This prevents a trained policy from losing the continuation anchor under which
it was produced.

## State-value oracle

`NormalFantasyFixedPolicyOracle` is compatible with M4Z `OneHandOracle`:

1. sample a legal asymmetric chance world;
2. roll out the normal player using only the visible distilled policy;
3. evaluate the completed board with exact M4H by default (or an explicitly
   injected certified terminal evaluator with its own fail-closed fallback);
4. convert normal-player utility to persistent P0 perspective;
5. report mean, standard error, sample count, oracle id and exact continuation
   SHA-256.

The RNG is derived from policy snapshot + state + base seed, **not** from the
continuation vector. Bellman iterates therefore share common random numbers and
obtain lower-noise value differences.

## Sibling M5A component adapters

The staging branch now also contains:

- `m5a_normal_normal_oracle.py`: fixed distilled Normal×Normal policy rollout,
  exact current-hand+continuation terminal value, persistent-P0 role remap and
  common random numbers;
- `m5a_fantasy_fantasy_oracle.py`: M4W continuation-aware sealed policy over M4X
  robust union supports, with fail-closed rejection whenever V leaves the frozen
  M4X continuation region.

Together these files provide a structural `OneHandOracle` adapter for all three
kernel classes covering 2 + 16 + 32 = 50 HU states. They remain policy-evaluation
components; no route is promoted merely because an adapter object exists.

## Authority boundary

Normal×Fantasy authority:

`FIXED_VISIBLE_POLICY_NORMAL_FANTASY_VALUE_NOT_BELLMAN_OPTIMAL`

Normal×Normal authority:

`FIXED_VISIBLE_POLICY_NORMAL_NORMAL_VALUE_NOT_BELLMAN_OPTIMAL`

Fantasy×Fantasy authority:

`M4W_M4X_SEALED_FIXED_MODEL_VALUE_NOT_EQUILIBRIUM`

Creation of these adapters never registers a route as `READY_CERTIFIED`. A later
certification/policy-improvement milestone must establish held-out policy quality,
continuation robustness and strategic deviation bounds before M4Z may consume
them as real Bellman evidence.

## Next — M5B

Build continuation-aware policy-improvement and certification around the three
M5A adapters. M5B must distinguish policy evaluation from a strategic Bellman
operator, bind every trained snapshot to its evidence, measure held-out policy
and state-value error/deviation, and only then allow certified routes to populate
the real 50-state M4Z registry.
