# M4Y — Bellman-trace regional coverage + held-out M4W benchmark

## Purpose

M4X established a mathematically valid support-gap extension bound inside a
declared L∞ continuation region. It deliberately did **not** establish that the
outer 50-state Bellman trajectory stays inside that region.

M4Y closes the evidence-plumbing gap without manufacturing continuation values.

## Contract

`m4y_bellman_trace.py` provides four independent pieces:

1. **SHA-bound Bellman trace**
   - every row must contain all 50 HU continuation states;
   - each raw Bellman image is normalized to one declared relative-value gauge;
   - the removed reference value is preserved as `gain_anchor`;
   - the trace is explicitly tagged either `REAL_BELLMAN_ITERATES` or
     `SYNTHETIC_TEST_FIXTURE`;
   - provenance and an external oracle-manifest SHA are mandatory.

2. **Training-only M4X family derivation**
   - only a prefix declared as training evidence may choose anchors;
   - anchors are deterministic farthest-point centers under L∞;
   - the radius is the exact training covering radius;
   - holdout points cannot enlarge the radius or alter anchor choice.

3. **Held-out coverage**
   - every future/holdout iterate is measured against the frozen family;
   - escapes are reported rather than silently absorbed;
   - `REAL_TRACE_HOLDOUT_COVERED` is an evidence statement only, not strategic
     promotion.

4. **Held-out model/support diagnostics**
   - M4W is scored on immediate utility, 25-way transition distribution and
     reconstructed Q across held-out continuation vectors;
   - a fixed M4X robust support may be checked against exact M4N on trace points;
   - inside-region points mechanically verify
     `gap(V) <= gap(anchor) + 2 ||V-anchor||∞`;
   - outside-region points receive no theorem bound and require family expansion
     or new evidence.

## Anti-self-deception rules

Synthetic vectors are permitted only in unit/regression fixtures and must carry
`SYNTHETIC_TEST_FIXTURE`. They cannot be presented as Bellman evidence.

M4Y defines no strategic acceptance threshold for support gap, Q error,
cross-entropy, exploitability or convergence. Measured numbers stay measured
numbers until a downstream gate freezes defensible thresholds and provenance.

A real trace label must correspond to iterates emitted by the future integrated
50-state outer Bellman oracle. M4Y does not infer that provenance from numbers.

## Current status

`TRACE_CONSUMER_AND_HELDOUT_AUDITOR_READY_BELLMAN_ORACLE_PENDING`

The repository currently has continuation-aware component solvers for
Normal×Normal and Normal×Fantasy plus the M4W/M4X Fantasy×Fantasy path, but no
integrated 50-state Bellman driver that can truthfully emit
`REAL_BELLMAN_ITERATES`.

## Next milestone — M4Z

Build the fail-closed 50-state one-hand-oracle registry / outer relative-value
driver. It must:

- route each of the 50 states to the correct kernel;
- carry the exact current continuation vector into every one-hand oracle;
- refuse uncertified approximations rather than substitute zero continuation;
- normalize every complete Bellman image through the same reference state;
- emit M4Y-compatible trace rows plus per-state oracle provenance;
- keep field promotion blocked until all 50 state routes are integration-ready.

M4Z may initially run as an orchestration/provenance skeleton with deliberately
blocked routes. A blocked route is preferable to fabricating a Bellman iterate.
