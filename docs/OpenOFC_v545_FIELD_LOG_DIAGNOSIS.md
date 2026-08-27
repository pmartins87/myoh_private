# OpenOFC v5.4.5 — field-stall diagnosis and observability contract

Field evidence: KKPoker/OpenHoldem session 2026-08-22 19:42–19:46 using the v5.4.4 field-test binary and `KKPoker_OpenOFC_JokerUltimate_v5_4_4.tm`.

## 1. Dealer pre-arrangement was mistaken for a freeze

Opening example: Hero dealer received `2c Jc Qc Kc Ac`.

The controller correctly entered provisional mode, moved `2c` to middle, verified the drag, then intentionally withheld Confirm while `hero_timer_active=0` and `decision_finalizable=0` so the final decision could be recalculated after the opponent exposed final information.

Representative runtime markers:

- `mode=PROVISIONAL dealer=1 hero=1 timer=0 finalizable=0`
- `arrangement_complete=1 confirm=HELD timer=0`
- `waiting=1 dealer=1 hero=1 timer=0 confirm=HELD`

This is strategy-correct but operationally opaque. v5.4.5 therefore exposes human-readable runtime state in the OpenHoldem status bar, including `AGUARDANDO OPONENTE - Confirm retido`, `OPONENTE FINALIZOU - recalculando`, `VERIFICANDO MOVIMENTO`, `RECUPERANDO LEITURA - sem agir`, and related states.

## 2. Genuine stall: surplus phantom UNKNOWN_OCCUPIED

A separate nondealer opening reproduced a real freeze. Hero had five known opening cards, and all five real identities became visible on the board, but one extra row slot remained classified as `UNKNOWN_OCCUPIED`. The raw cardinality became six instead of five. The scraper emitted `state=TRANSITION board=6 loose=0 sum=6 action=WAIT`; canonical lineage remained valid and action-required, but the raw observation stayed invalid, so Tick repeatedly returned `action=NONE reason=INVALID_PERCEPTION`.

The same +1 occupancy shape also appeared at subsequent round transitions (for example board+current 9 when 8 was expected).

v5.4.4 intentionally made UNKNOWN different from EMPTY, which fixed false negatives but exposed this opposite failure mode: a false-positive occupied region can become a phantom physical card.

## 3. v5.4.5 exact-lineage deghost rule

Do not revert UNKNOWN semantics. UNKNOWN remains occupied unless there is deterministic contradictory evidence.

v5.4.5 clears only surplus UNKNOWN row occupancy when canonical lineage proves the complete expected physical set exactly:

1. same-round proof: previous fully-known board + previous fully-known incoming exactly form the expected round set; every identity is currently visible; raw occupancy exceeds expected cardinality only through UNKNOWN row slots;
2. next-round proof: all three newly dealt cards are still loose, the previous committed board persists, the exact required number of previous incoming cards is visibly committed, and surplus occupancy is confined to UNKNOWN row slots.

If an expected known identity is missing, previous lineage contains UNKNOWN, or the surplus cannot be explained entirely by UNKNOWN row slots, no deghost is allowed.

Runtime diagnostic marker:

`[OpenOFC DEGHOST] ... reason=SAME_ROUND_EXACT_LINEAGE|NEXT_ROUND_ALL_NEW_LOOSE_EXACT_LINEAGE ... action=IGNORE_THIS_FRAME`

## 4. User-visible status contract

The OpenOFC action pane must show why automation is or is not acting. The runtime publishes state transitions to `COpenHoldemStatusbar::SetLastAction`, and the OFC-specific status bar renders that string instead of the old static `OpenOFC` label. The pane is widened for operational text.

The log also receives `[OpenOFC STATUS]` only when the visible status changes, avoiding heartbeat spam.

## 5. Acceptance gate

v5.4.5 is not a field release until the complete frozen patch chain materializes, the UNKNOWN/full-replan/Fantasy/continuity regressions pass, Release|Win32 builds, and the artifact is produced by the PR gate. The v5.4.4 TableMap remains the intended field map for this source-only recovery/observability layer.
