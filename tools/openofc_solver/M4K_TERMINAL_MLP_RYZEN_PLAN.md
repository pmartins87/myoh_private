# M4K — CPU terminal MLP + staged Ryzen exact-corpus plan

## Measured reason for the architecture

M4H passed exact parity with the independent M4D two-pass oracle and measured one fresh one-pass frontier on GitHub Ubuntu as follows:

| Fantasy size | exact Bottom/Middle pairs | fresh exact frontier | cache hit |
| --- | ---: | ---: | ---: |
| F14 | 252,252 | 1.12896 s | 0.00130 s |
| F15 | 756,756 | 2.45927 s | 0.00138 s |
| F16 | 2,018,016 | 15.91322 s | 0.00141 s |
| F17 | 4,900,896 | 108.88590 s | 0.00148 s |

F14 improved by about 2.06x versus the M4G two-pass implementation. The F16/F17 curve still makes exact fresh solves unsuitable as a naive terminal operation inside millions of MCCFR trajectories.

The project therefore keeps exact search as the teacher/fallback and learns a very cheap terminal model from exact M4I rows.

## Why M4K is different from the M4J probe

M4J intentionally used a small sparse pairwise model to validate the complete teacher/split/abstention/error-measurement pipeline. On a ten-world F14 smoke corpus its held-out sample was only two worlds; it correctly remained blocked from production. The observed held-out point error was large and confident coverage was zero, so there is no basis for promoting that low-capacity probe.

M4K adds a compact two-hidden-layer NumPy MLP. It remains CPU-friendly:

- input: 221 exact oracle-only terminal-world coordinates;
- default hidden layers: 128 and 64;
- outputs: two reachability logits + two normalized immediate-point predictions;
- binary cross-entropy for branch reachability;
- masked Huber loss for exact branch points;
- Adam optimizer;
- deterministic epoch order;
- exact optimizer-state save/load;
- no GPU requirement;
- output can later be exported directly to C++ as fixed float matrices.

This is still an approximation probe. Exact held-out evidence, not neural-network training loss, controls promotion.

## Staged Ryzen corpus

The M4I shard runner already supports independent processes, deterministic half-open world ranges, SHA-bound manifests and zero-regeneration resume. Use staged growth rather than committing months blindly.

### R0 — mechanics pilot

Generate 1,000 exact worlds per Fantasy size. Purpose: measure the user's actual Ryzen throughput, RAM behavior, branch balance and Joker strata. No production threshold is inferred from this stage.

### R1 — model-selection corpus

If R0 is healthy, grow to at least 10,000 worlds per F14/F15/F16/F17. Compare M4J and M4K, hidden widths, calibration thresholds and continuation-utility error on a fixed untouched holdout. Freeze architecture only after this comparison.

### R2 — certification corpus

Grow adaptively rather than uniformly. Add exact worlds preferentially to strata with the largest held-out error:

- F16/F17;
- one/two Joker packets;
- worlds where both re-Fantasy branches are reachable;
- worlds close to the branch-switch boundary for realistic continuation deltas;
- later, worlds sampled from the actual learned normal-player reach distribution.

Exact corpus generation stops when confidence intervals on the error budget, rather than a round-number sample count, meet the promotion target.

## Promotion boundary

A terminal model may be called from strategic training only if an explicit envelope is frozen from exact held-out data. Outside that envelope it must abstain and use an exact/cached fallback or contribute a mathematically accounted worst-case error to the strategic certificate.

The terminal approximation is one component of final exploitability, not a substitute for it. The next field test remains deferred until the normal-game strategy itself is trained/certified and integrated.
