# M5C — held-out strategic route certification firewall

## Purpose

M5A supplies continuation-aware fixed-policy/model value adapters. M5B adds
policy improvement at the current continuation vector. Neither component
existence nor a low training loss establishes that a one-hand policy is safe to
use as a Bellman operator.

M5C is the fail-closed promotion boundary between those probes and a REAL M4Z
50-state Bellman run.

## Explicit thresholds only

M5C contains no production strategic thresholds. A threshold manifest must be
supplied explicitly and is SHA-256 bound to its provenance.

Every kernel requires explicit limits for:

- minimum independent held-out seeds;
- minimum held-out samples;
- maximum value standard error;
- maximum unilateral-deviation gain.

Fantasy×Fantasy additionally requires explicit limits for:

- maximum M4X exact-teacher support gap;
- maximum held-out M4W action-value/model error.

Policy-imitation loss, top-1 agreement, training loss and smoke-test improvement
may be recorded elsewhere as diagnostics. They are deliberately insufficient for
strategic promotion.

## Evidence contract

Each route evidence object is bound to:

- one exact HU continuation state and kernel class;
- oracle identity;
- implementation SHA-256;
- continuation evidence/trace/family SHA-256;
- unique held-out seed identifiers;
- held-out sample count;
- the required strategic metrics;
- evidence kind and provenance;
- its own canonical SHA-256.

Fantasy×Fantasy evidence is rejected at construction time when support gap or
model-Q error is absent.

## Fail-closed promotion

`certify_route()` compares one evidence object against the explicit threshold
manifest. Any missing/insufficient or over-budget strategic criterion leaves the
route blocked.

`register_certified_route()` is the only M5C bridge into an M4Z
`OracleRegistry`. It requires a real-ready certificate, an exact oracle-id match
and the exact state/kernel identity. Synthetic/test evidence is refused.

Certification is state-local. One passing state cannot promote a whole kernel.
A complete real Bellman surface still requires 50 distinct ready certificates:
2 Normal×Normal, 16 Normal×Fantasy and 32 Fantasy×Fantasy.

## Strategic meaning

M5C does not declare the current policies good. It defines what evidence must
exist before we are allowed to make that claim operationally.

The next milestone is to generate the missing independent strategic evidence:

1. Normal×Normal: held-out unilateral-deviation / best-response evidence at
   current-V anchors plus value uncertainty;
2. Normal×Fantasy: one-sided held-out deviation evidence for the acting normal
   player plus value uncertainty;
3. Fantasy×Fantasy: M4X unrestricted support-gap + M5B support-restricted
   deviation + held-out M4W error over the Bellman continuation region;
4. freeze thresholds from a separately justified protocol;
5. certify state-by-state and only then enable the first REAL 50-state M4Z trace.

Authority:

`HELDOUT_STRATEGIC_ROUTE_CERTIFICATION_FIREWALL`
