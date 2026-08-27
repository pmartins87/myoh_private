# M4T — 50-state Bellman image and relative-value iteration contract

## Purpose

The exact HU continuation surface has 50 states and three one-hand kernel
families: Normal×Normal, Normal×Fantasy and Fantasy×Fantasy. M4T defines the
outer algebra that will eventually couple those kernels without assigning any
solver authority they have not earned.

M4T does **not** compute a one-hand equilibrium. It consumes one complete
Bellman image produced elsewhere and performs the exact relative-value plumbing
conditional on those supplied estimates.

## Bellman image

A `BellmanImage` contains:

- the complete 50-state continuation vector used as one-hand input;
- one `BellmanStateEstimate` for every one of the 50 states;
- persistent-player-0 one-hand value estimate;
- exact kernel-family ownership;
- solver kind and authority;
- optional absolute error bound and sample count;
- iteration index and SHA-bound payload.

The image rejects missing/extra states and rejects a row whose declared kernel
family disagrees with `hand_kernel_kind(state)`. This prevents, for example, a
Normal×Fantasy approximation from being silently inserted into one of the 32
Fantasy×Fantasy states.

## Outer relative-value step

Given Bellman image `T(V)`, M4T computes a reference-normalized update:

    V_next(s) = T(V)(s) - T(V)(s_ref)

and compares it to the input vector normalized in the same gauge. It reports:

- gauge-invariant gain estimate `T(V)(s_ref) - V(s_ref)`;
- sup-norm update delta;
- span delta;
- SHA of input and normalized output vectors.

No convergence threshold is frozen here. The numeric accuracy of `T(V)` belongs
to the one-hand kernel artifacts and later empirical gates.

## Player-exchange symmetry and gauge

The 50-state game has an exact player-label exchange automorphism, but a relative
value vector is defined only up to a global additive constant. Literal
`V(swap(s)) = -V(s)` therefore depends on gauge.

M4T uses a gauge-aware diagnostic instead of incorrectly requiring literal
antisymmetry after reference normalization. Across the 25 exchange pairs it
reports:

- mean pair sum;
- spread of pair sums;
- the global offset that projects to the antisymmetric gauge;
- maximum residual after that projection.

A pure global gauge shift changes the mean pair sum but leaves the pair-sum
spread zero. This distinguishes harmless normalization from a real symmetry
violation.

## Error propagation

If every one-hand state estimate supplies an absolute error bound `e_s`, the
reference-normalized output value at state `s` has conservative bound

    e_s + e_ref.

M4T reports the maximum of those bounds. If any state lacks a bound, the outer
bound is explicitly unknown rather than fabricated.

## Gate

The unit regression proves:

- a Bellman image equal to `V + constant` normalizes back to the same relative
  vector and reports the constant as gain;
- the outer update is invariant to a global shift of the input gauge;
- exchange-symmetric vectors shifted by a constant are recognized correctly;
- wrong state/kernel ownership is rejected;
- Bellman payloads are SHA-bound and tamper-evident;
- missing per-state error evidence propagates to an unknown outer error bound.

## CI strategy

M4T is developed on `openofc-strategy-post-m4s`, which is intentionally not
attached to the large historical PR while its Actions queue is congested. The
M4T workflow is `workflow_dispatch` only. This prevents another full storm of
legacy pull-request workflows while preserving an explicit test entry point.

## Next milestone

M4U should define the per-kernel **Bellman row artifact adapters**: Normal×Normal
from continuation MCCFR, Normal×Fantasy from M4L, and Fantasy×Fantasy from the
M4S/M4R stack. Each adapter must bind its row to the same input continuation SHA
and carry its own error budget. Only when all 50 rows can be assembled without
missing or uncertified ownership should iterative M4T updates begin.
