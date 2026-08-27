# OpenOFC v5.4.4 — Field Recovery

This branch addresses the field failures isolated on 2026-08-22:

- Fantasy entry is no longer owned by one static `ofc_fantasy_active` pixel. Current-screen dynamic 14..17-card proof, prior Fantasy lineage, and the static hint are independent entry signals.
- `UNKNOWN` is an occupied physical card distinct from `EMPTY`. Same-round transient identity loss is repaired from lineage; one genuinely unread R1–R4 incoming is kept occupied and deliberately left unused while the two readable cards are played. R0 waits for the unread identity instead of inventing one.
- New-hand/next-round/reacquire decisions cross a non-blocking stabilization fence before the first drag; an old arranging transaction is abandoned when a fresh valid state proves that the game already advanced to another round.
- Dealer-side provisional arrangement remains strategy-reversible. While the opponent is still playing, Hero may pre-arrange to save clock. Once opponent final information is revealed, the policy is run again from the final canonical state with no discard bias from current UI positions.
- If the final solution changes which card is discarded, a card already placed provisionally can now be dragged back to any proven-empty one of `ofc_hero_in0drag`, `ofc_hero_in1drag`, or `ofc_hero_in2drag`. The reverse gesture is transactional: one drag, mandatory fresh scrape, proof that exactly that pending placement disappeared while every other pending placement stayed unchanged, then continuation of the final plan.

## Strategic/executor separation

Physical UI limitations must not constrain the poker policy. The policy chooses the best final arrangement from the information currently available. The executor is responsible for transforming the current visual layout into that strategy safely. In particular, the final solver may choose as discard a card that was provisionally placed before the opponent revealed the final board.

The v5.4.4C patch removes the temporary `have_loose_nonjoker_discard` preference and the `moving back to loose is unsupported` TurnPlan prohibition. Reverse movement is currently certified for normal discard rounds R1–R4; Fantasy uses its separate batch/fan transaction model and is intentionally unchanged by this patch.

The branch is not a field release until the dedicated CI path passes materialization, UNKNOWN/full-replan regression, generic Fantasy 14–17 regression, runtime continuity regressions, dependency build, and Release|Win32 build. Only then is the exact user TableMap v5.4.4 injected into the downloadable field package.
