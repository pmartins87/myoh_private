# M4U — kernel-evidence Bellman rows and fail-closed assembly

## Purpose

M4T defines the exact outer 50-state Bellman/relative-value algebra. M4U defines
how one-hand kernel evidence is allowed to enter that algebra.

A Bellman row is bound to one exact continuation-vector SHA and one exact HU
meta-state. Partial bundles are useful for measurement and coverage, but a full
Bellman image is assembled in **certified-only mode by default**.

## Row contract

Every `BellmanRowArtifact` contains:

- exact HU continuation state;
- input continuation SHA-256;
- persistent-player-0 one-hand value;
- exact kernel family (`NORMAL_NORMAL`, `NORMAL_FANTASY_ASYMMETRIC`, or
  `FANTASY_FANTASY`);
- solver kind and authority;
- evidence SHA-256;
- sample count when applicable;
- optional absolute value-error bound;
- explicit `certified` flag;
- arbitrary JSON-safe diagnostics;
- its own SHA-bound payload.

Kernel ownership is checked against `hand_kernel_kind(state)`. A certified row is
invalid unless it carries an explicit non-negative absolute error bound.

## Coverage

The exact state catalog is fixed at:

- 2 Normal×Normal rows;
- 16 Normal×Fantasy rows;
- 32 Fantasy×Fantasy rows.

`coverage_report()` tracks total/certified counts per family and lists every
missing state. Partial bundles can be merged only when they share the same input
continuation SHA and do not duplicate states.

## Fail-closed Bellman assembly

`assemble_bellman_image()` requires all 50 rows and checks that every row was
produced from the supplied continuation vector. Its default
`require_certified=True` rejects a complete image containing even one provisional
row. Exploratory assembly exists only through the explicit
`require_certified=False` override and propagates missing error bounds into M4T.

This prevents descriptive measurements from silently becoming solver authority.

## M4S Fantasy×Fantasy adapter

`m4s_fantasy_bellman_adapter.py` converts a completed M4S output directory into
**provisional** Fantasy×Fantasy rows. It verifies:

- the M4S report SHA;
- model-checkpoint SHA;
- continuation-vector SHA;
- held-out cached episode integrity.

For each measured Fantasy×Fantasy state it recomputes the learned sealed policy
on held-out worlds and reports the chance-sample mean of exact M4P profile value.
It also preserves:

- descriptive chance-sample standard error;
- mean/max support-restricted deviation;
- held-out action-value error;
- sampled exact M4O support-gap evidence when present.

These statistics are informative but are **not** converted into an absolute
Bellman-row error certificate. The adapter therefore sets `certified=False` and
`error_bound_abs=None`.

## Why descriptive stderr is not a certificate

A sample standard error describes dispersion under sampled chance worlds. It does
not, by itself, bound:

- M4O omitted-action support loss;
- M4R within-support strategic deviation;
- function approximation bias;
- finite-sample chance error with a specified confidence guarantee.

M4U keeps those distinctions explicit rather than manufacturing a single false
"±" number.

## Gate

The dispatch-only M4U regression verifies:

- exact 2/16/32 state-family coverage;
- full 50-row certified assembly;
- one provisional row blocks default assembly;
- explicit exploratory assembly preserves unknown error evidence;
- partial bundle merge is SHA/fingerprint safe;
- row bundles are tamper-evident;
- a synthetic M4S held-out directory produces a provisional Fantasy×Fantasy row
  with correct sample/diagnostic aggregation and cannot assemble an incomplete
  50-state image.

## CI strategy

Like M4T, M4U lives on `openofc-strategy-post-m4s` with a
`workflow_dispatch`-only gate while the historical PR Actions queue is saturated.

## Next milestone

M4V should add equivalent provisional/certified adapters for:

1. Normal×Normal continuation-MCCFR evaluation;
2. Normal×Fantasy M4L evaluation.

Those adapters must estimate **policy value over independent chance worlds**, not
training loss. After all three kernel families can emit same-SHA row bundles, the
next work is to build rigorous per-row error certificates and only then permit a
certified M4T iteration.
