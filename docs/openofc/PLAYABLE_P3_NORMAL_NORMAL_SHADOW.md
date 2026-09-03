# OpenOFC PLAYABLE P3 Normal/Normal shadow checkpoint

Date: 2026-09-02
Status: **implementation checkpoint; recorded-pixel shadow still pending**

## Scope and authority

This checkpoint imports the immutable DeepOFC PLAYABLE P2 Normal/Normal B0/B1
candidate into the native OpenHoldem runtime. It is intentionally inert:

- authority: `SHADOW_ONLY_NO_PHYSICAL_EXECUTION_AUTHORITY`;
- `physical_execution_authorized=0` in the build identity, runtime receipt and
  package provenance;
- the paired v5.5.3 TableMap sets `s$ofc_executor_enabled 0` and
  `s$openofc_p3_shadow_only 1`;
- `COFCRuntimeController` contains no casino-interface, drag, click or
  orchestrator-start call in this checkpoint;
- selected actions are converted to `COFCStrategyAction` and independently
  checked by `COFCTurnPlanBuilder`, but the resulting plan is logged only.

This is not PLAYABLE DONE, a live-use build, a formal strategy certificate or
an authorization to click a poker client.

## Frozen inputs

| Input | Identity |
|---|---|
| Runtime base | `924f55e60df2812f6cbe2957d3ced93a8d4e8f94` |
| P2 source | `3d04fe96fa41e2eb2709b01dc7f8c02e709eb163` |
| P2 manifest | `f10c079a61ba08832cfc334afb9c055e023dfc9c23a24140d02b2f7bd8413898` |
| P3 native manifest | `ff880a76bce9885f19b7297952a9d182d0ba2c54e10681baa74937f66b4691bc` |
| B0 native weights file | `52be780cda5b0e36da645e6ea36fc07dd445fcc6785281a769a91d8fce0d699c` |
| B1 native weights file | `08e3b9d2523f092aee45fddc1170e9ffb7486595ea2f36f8c6db7296df27a0d3` |
| Synthetic replay | `7cd5878f4628c3d5d8ec0fd43663104c83e7d5baa2ce4a8a4005ee248394254b` |
| P3 shadow TableMap | `e90dfc47c6449d9092c28c5c8ae5221d863599a64534150d67878828aeffeb2d` |

The native files contain only prediction weights. Optimizer state remains in
the strategic repository and is not imported into the runtime.

## Runtime decision contract

1. Preserve chairs `0/1` as persistent P0/P1 identities for the hand.
2. Map the non-dealer to role 0 and dealer/button to role 1.
3. Reconstruct every confirmed public action from monotone row-membership
   deltas in exact non-dealer/dealer order.
4. Require the complete public prefix from hand start; do not infer a mid-hand
   history from board totals alone.
5. Construct the exact visible-only suit-24 information key and complete legal
   action set used by DeepOFC training.
6. Select B0/B1 by persistent button identity and reproduce the P2 positive
   advantage normalization and lexical tie-break.
7. Convert the selected canonical action back to physical card identities,
   validate a semantic turn plan, emit immutable provenance and stop.

Opponent packets, opponent discard identities and future cards are absent from
the native policy API. Only their consistency counts enter the fail-closed
runtime gate.

## Evidence completed here

- native policy files reload only after exact SHA/header/model/snapshot/route
  checks;
- a modified weight byte is rejected;
- portable C++ compilation passes with warnings treated as errors;
- two deterministic complete synthetic hands cover B0 and B1;
- 20 sequential states reconstruct the ordered public history;
- all 10 Hero decisions match Python for canonical-key SHA, canonical action,
  selected probability and physical placement/discard action;
- incomplete history and contradictory hidden-card counts fail closed;
- the runtime project copies the exact policy inputs beside the executable;
- the dedicated Windows workflow builds the standalone parity executable and
  the full Release Win32 runtime, then emits package-wide SHA-256 provenance.

## Gates still open

1. Publish the runtime checkpoint and obtain a green Windows workflow run.
2. Bind the resulting runtime commit and `OpenHoldem.exe` SHA in the produced
   package provenance.
3. Run recorded pixel/frame replays through scraper -> reconstructor -> public
   history -> policy -> turn plan, with zero input dispatch.
4. Resolve any recognizer/history mismatch without weakening the fail-closed
   boundary.
5. Accumulate controlled shadow evidence before proposing a separate physical
   execution gate.

Until all of those gates are deliberately reviewed, `runtime_binding_complete`
and `recorded_pixel_shadow_complete` remain `0`.
