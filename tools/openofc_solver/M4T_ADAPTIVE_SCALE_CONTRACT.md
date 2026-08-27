# M4T — evidence-driven adaptive scale planner

## Purpose

M4S finally measures the sealed Fantasy/Fantasy stack end to end, but a single
pilot cannot answer the next engineering question: **what should be made larger,
and when?** M4T converts independent M4S held-out reports into a deterministic,
machine-readable scale plan.

M4T is deliberately a planner, not a policy authority. It does not turn one good
pilot into a production claim and it does not invent acceptable error thresholds.

## Input firewall and comparability

Every input must be an unmodified `openofc-m4s-heldout-report-v1` report with a
valid SHA-256. M4T rejects:

- tampered reports;
- duplicate `base_seed` values presented as independent evidence;
- different generator fingerprints;
- different continuation vectors;
- different state catalogs or learner/measurement configuration.

This fail-closed rule prevents averaging results from two materially different
action supports or training regimes and calling the mixture “multiseed evidence”.
A changed configuration is a new experiment and must be analyzed separately.

## Evidence before tuning

Three evidence minima are explicit and CLI-configurable:

- independent base seeds;
- held-out worlds per state;
- exact M4N support-gap samples per state.

The shipped defaults (`3`, `6`, `12`) are **measurement-acquisition defaults**, not
promotion thresholds and not claims of statistical sufficiency for production.
If any state is below them, M4T recommends more independent evidence before
changing architecture. Suggested new seeds are deterministically derived from the
experiment signature and cannot duplicate supplied seeds.

## Numeric targets are never fabricated

The four actual error targets must be supplied explicitly:

1. maximum allowed **mean M4O exact-teacher support gap**;
2. maximum allowed **M4P support-restricted unilateral deviation**;
3. maximum allowed **mean M4Q/M4R action-value MAE**;
4. maximum allowed **held-out maximum absolute action-value error**.

When they are absent, the only valid decision after sufficient evidence is
`CALIBRATE_AND_SUPPLY_NUMERIC_TARGETS`.

## Error-directed scaling

After the evidence minima and explicit targets are present, M4T changes only the
levers connected to the failing budget:

- support loss high → increase M4O `synthetic_worlds` and `max_candidates`;
- support-restricted policy loss high → increase M4R self-play iterations and
  fitting epochs;
- function-generalization error high → increase M4Q model buckets, replay
  capacity and fitting epochs.

A support expansion changes the generator fingerprint and therefore requires a
new corpus namespace. Training/model expansion can reuse the same exact episode
corpus because the support generator is unchanged.

The current scaling factors are conservative engineering proposals (doubling),
not mathematical guarantees. Every changed configuration must return through M4S
held-out measurement.

## Progressive state coverage

M4T does not jump from F14/F14 directly to all 32 Fantasy/Fantasy states. Coverage
expands in rings:

1. F14/F14, both buttons;
2. F14/F15, F15/F14, F15/F15, both buttons;
3. the remaining F14–F16 pairings;
4. every pairing containing F17.

A measured tier must satisfy the supplied budgets before the next tier is
recommended. This keeps the expensive exact M4N teacher concentrated where it
still buys information.

## Outer continuation boundary

Only when all 32 Fantasy/Fantasy states have independent evidence and pass the
supplied three-part budget does M4T emit:

`OUTER_CONTINUATION_INTEGRATION_CANDIDATE`

Even then `promotion_blocked` remains true. The message means the sealed
Fantasy/Fantasy kernel is ready to be *tested* inside the 50-state continuation
fixed-point loop; it is not an equilibrium certificate by itself.

## Artifact

`plan_m4t_adaptive_scale.py` writes `openofc-m4t-adaptive-scale-plan-v1` JSON with:

- hashes of all input M4S reports;
- experiment signature and independent seeds;
- evidence requirements and explicit error targets;
- per-state evidence aggregates;
- per-state decisions;
- ordered recommended actions;
- next configuration proposal;
- SHA-256 of the complete plan.

## Gate

CI validates that:

- report tampering is rejected;
- duplicate seeds cannot inflate evidence;
- mixed experiment configurations cannot be aggregated;
- evidence acquisition precedes tuning;
- each failing error budget scales the intended subsystem;
- thresholds are never invented;
- passing F14/F14 expands to the next ring;
- all 32 passing states produce only an outer-integration *candidate* while
  promotion remains blocked.

## Next milestone

M4U should consume real Ryzen M4S/M4T evidence, freeze the first defensible
measurement thresholds with provenance, and create a continuation-oracle adapter
that can be switched on only for state families whose held-out budget is
certified. That keeps the 50-state Bellman solve from silently consuming an
uncertified strategic approximation.
