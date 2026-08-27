# M4S — resumable multiseed sealed-Fantasy measurement runner

## Purpose

M4O–M4R establish a bounded sealed Fantasy/Fantasy strategic stack, but unit
regressions cannot determine whether its approximation budgets are acceptable on
real CPU resources. M4S is the first end-to-end measurement runner for that
question.

It intentionally defaults to a small **F14/F14, both-button** pilot. Expansion to
all 32 Fantasy/Fantasy meta-states is a measured decision, not a default that can
accidentally consume days of Ryzen time.

## Deterministic episode materialization

For every `(meta-state, split, world index)` M4S derives a stable world seed from:

- base seed;
- exact state key;
- `train` or `heldout` split;
- world index;
- purpose tag.

Each complete episode materializes:

1. the two physical Fantasy packets;
2. independent M4O own-information candidate supports for P0/P1;
3. the exact M4P zero-sum support payoff matrix;
4. proposal metadata/fingerprints and continuation SHA.

The episode is written atomically to a SHA-bound JSON record. A matching existing
record is loaded and reused without regenerating expensive M4N/M4O teacher work.
A generator/continuation fingerprint mismatch fails closed instead of silently
mixing corpora.

## Train/held-out firewall

Train and held-out worlds are physically separate cache trees and use different
seed derivations. Only train episodes enter M4R replay/training. Held-out episodes
are evaluated after the configured self-play iterations and are never inserted
into replay.

## Three independent error budgets

For each held-out world M4S reports:

1. **M4O support loss** — sampled exact M4N teacher gap versus the best M4O
   candidate against an opponent action sampled from the current sealed policy;
2. **M4P within-support policy loss** — exact support-restricted unilateral
   deviation gain under the current learned profile;
3. **M4Q/M4R function-generalization loss** — absolute error between model Q
   predictions and exact M4P current-opponent-policy action-value targets.

Support-gap sampling is intentionally configurable because it invokes the
expensive unrestricted exact teacher. `--support-gap-samples 0` disables that
budget only for engineering smoke runs; it cannot be used for promotion.

## Continuation values

If no continuation file is supplied, M4S uses the explicit all-zero continuation
baseline. This is useful for throughput/engineering calibration only. A JSON
state-key mapping (or `{ "values": ... }`) can supply all 50 continuation values;
validation is exact and complete, and the continuation SHA enters every generator
fingerprint.

## Resumability and artifacts

M4S writes:

- `episodes/train/.../world_XXXXX.json`;
- `episodes/heldout/.../world_XXXXX.json`;
- deterministic `M4S_MODEL_REPLAY.json.gz`;
- `M4S_HELDOUT_REPORT.json` with configuration, per-world metrics, aggregate
  metrics, three-budget definitions, checkpoint SHA and report SHA.

## Gate

CI does not launch the expensive exact corpus. The M4S unit gate proves:

- episode serialization/deserialization is SHA-bound and lossless;
- tampering is rejected;
- generator fingerprints respond to configuration changes;
- Fantasy-pair/button catalog parsing is deterministic;
- held-out diagnostics expose the policy and function budgets without invoking
  the costly support-gap teacher when samples are explicitly zero.

The Ryzen pilot itself is evidence, not a CI unit test.

## Pilot command

From repository root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File tools/openofc_solver/run_m4s_ryzen_pilot.ps1
```

The wrapper uses conservative F14/F14 settings and preserves its episode cache on
reruns.

## Promotion status

`MULTISEED_MEASUREMENT_ONLY_NOT_POLICY_PROMOTION`

No numeric threshold is frozen in M4S. First collect independent multiseed
measurements, then set thresholds based on observed scale and practical error.

## Next milestone

After the F14/F14 pilot, M4T should turn the measured runner into an adaptive
scale plan: increase seeds/support/synthetic worlds where each error budget needs
it, then expand through asymmetric F14–F17 pairings. Only after stable held-out
error budgets exist should the 50-state outer continuation iteration consume
these kernels as strategic oracles.
