# OpenOFC v5.4.4 — Field Recovery

This branch addresses the three field failures isolated on 2026-08-22:

- Fantasy entry is no longer owned by one static `ofc_fantasy_active` pixel. Current-screen dynamic 14..17-card proof, prior Fantasy lineage, and the static hint are independent entry signals.
- `UNKNOWN` is an occupied physical card distinct from `EMPTY`. Same-round transient identity loss is repaired from lineage; one genuinely unread R1–R4 incoming is kept occupied and deliberately left unused while the two readable cards are played. R0 waits for the unread identity instead of inventing one.
- New-hand/next-round/reacquire decisions cross a non-blocking stabilization fence before the first drag; an old arranging transaction is abandoned when a fresh valid state proves that the game already advanced to another round.

Additional safety: ordinary normal-round policy prefers a still-loose non-Joker discard over a pending card, avoiding unsupported pending-to-loose reversal when a safe loose discard exists.

The branch is not a field release until the dedicated PR gate passes all regression tests and Release|Win32 build, after which the exact user TableMap v5.4.4 is injected into the downloadable field package.
