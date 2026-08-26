# OpenOFC v5.8.2 — Fantasy bootstrap and cross-hand liveness

## Field failure

The `OpenOFC_v581_FANTASY_LINEAGE_R4_SAFETY_FIELD_TEST` binary reached a real FANTASY 15 hand but did not act. The 2026-08-25 field log exposed two independent blockers before any strategic action could be dispatched.

First, the loose-card count detector found fourteen rank anchors in a visually complete FANTASY 15 fan. The v5.5 count selector only tolerated extra observed anchors; `observed < expected_count` was impossible by construction. It therefore rejected the frame forever as `Fantasy loose-count geometry ambiguous observed=14`.

Second, a fresh Fantasy bootstrap with an empty 3/5/5 board still ran strict upright rank recognition on every arrangement slot. Animation/background ink in visually empty slots could therefore produce `Fantasy arrangement slot ... failed closed` and suppress the whole hand.

A previous-hand trace also showed a stale runtime transaction surviving into Fantasy with `action_required=1` and thirteen pending placements. The runtime new-hand gate required `PendingCount==0`, so a reconstructed fresh Fantasy state could not release the stale transaction.

## v5.8.2 correction

### 1. Bounded count alignment

The measured 6..17 templates and the existing acceptance thresholds are preserved. Template correspondence is now solved by an order-preserving dynamic program that permits at most:

- one missed expected rank anchor;
- two spurious observed anchors.

A missed anchor costs 2.5 score units and an extra anchor costs 6.0. Card identity is still read independently through the count-specific TableMap T7 regions. No card rank/suit is inferred from the missing geometry anchor.

The regression exhaustively removes each of the fifteen F15 template anchors. Every one-anchor omission remains below the unchanged score threshold and separated from the exact F14 template by the unchanged margin threshold. Exact F14 remains exact F14.

### 2. Empty-board bootstrap uses occupancy first

When no prior Fantasy lineage exists, the scraper now reads arrangement occupancy before attempting card identity. If all 13 Hero arrangement slots are empty, strict rank/suit recognition is skipped and the loose fan is read directly. If any arrangement slot is occupied without lineage, strict fail-closed identity is retained.

This correction is deliberately narrow: it does not make ambiguous non-empty boards permissive.

### 3. Fresh Fantasy releases stale runtime state

A fresh Fantasy hand is now identified by:

- valid Hero Fantasy state;
- `round_index == -1`;
- empty Hero board;
- 14..17 incoming Fantasy cards;
- changed incoming-hand signature.

`PendingCount==0` is no longer required. Thirteen pending target placements are legitimate immediately after reconstruction and cannot make an old blocked/result transaction absorb the next hand.

## Preserved contracts

The v5.8.1 single-delta physical-lineage recovery and R4 non-foul safety remain unchanged. Exact Fantasy/R4 evaluator logic remains unchanged. The paired `KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm` remains byte-identical with SHA-256 `28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6`.

## Authority

This patch repairs perception and runtime liveness only. It does not promote the strategic policy to solved-game authority and does not relax duplicate-card, ambiguous-card, or non-empty no-lineage safety gates.
