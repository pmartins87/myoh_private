# OpenOFC v5.4.6 — field Fantasy recognition diagnosis

## Field evidence

The 2026-08-22/23 field session separates Fantasy-mode detection from Fantasy-card recognition.

The updated user TableMap does detect the Fantasy marker. The live log repeatedly reaches:

```text
[OpenOFC FANTASY ENTRY] static=1 ... route=TRY_FANTASY
```

The runtime then fails closed before producing a valid Fantasy observation because the native pixel recognizer cannot certify the current cards/geometries. Repeated examples include:

```text
loose:reflow loose Fantasy card rejected: Fantasy rank rejected distance=0.46875 margin=0.00369094
loose:dynamic Fantasy grid residual is too high
arrangement:Fantasy arrangement slot 3 failed closed: Fantasy rank rejected distance=0.643478 margin=0.0231884
arrangement:Fantasy arrangement slot 2 failed closed: Fantasy rank rejected distance=0.372549 margin=0.0376752
```

The resulting control path is therefore correctly suppressed:

```text
route=FANTASY_RETRY_NEXT_FRAME
state_valid=0 raw_valid=0
[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION
```

This is not a Fantasy-marker, mouse, Confirm, or normal-runtime liveness failure.

## Field fixtures

Two replay bitmaps provide direct current-client evidence:

- `frame000002(2).bmp`, SHA-256 `132c834b51b70a309ed73f451274d74c270c4884a4ce9750d9da319a07202309`: stable 14-card Fantasy fan. Standard cards observed left-to-right after the Joker are `Kd Qd Ts Td 8c 7s 7c 7d 6d 3h 3c 3d 2s`.
- `frame000020.bmp`, SHA-256 `428b8ba1056be607768b2382bb2a2f4db7a03dcfe2c98586ac50a45f50d13bba`: partially arranged 14-card Fantasy state. Upright arranged cards include `As Jh Tc Qs Qh Qd 8s`; loose/reflow standard cards are `Kc Kd 7c 7d 4d 2h` plus the already-accounted current Fantasy set.

The user TableMap used for this session has SHA-256 `51c68b2224448e24724c2949fd84f5f3a31890e4a99fcd4a43265a83ace3daa4`.

## Root causes

### 1. Single-exemplar rank banks are too narrow for current field rendering

The generic Fantasy path still delegates rank identity to the calibrated legacy pixel recognizer. The fan and upright-large banks contain one exemplar per rank. Current KKPoker rendering produces legitimate same-rank glyph variants that fall outside the old exemplar's distance/margin envelope.

The recognition core already supports multiple exemplars safely: it collapses every exemplar of a rank to that rank's minimum distance before calculating the best-vs-second-rank margin. Therefore adding same-rank field exemplars broadens intra-class coverage without turning multiple samples of the same rank into false competitors.

v5.4.6 adds current-field rank exemplars while retaining every previous exemplar and retaining all confidence thresholds unchanged.

### 2. One-pixel lower-line false anchor

In the partial Fantasy frame, a suit-sized component can pair with an unrelated one-pixel UI/card line below it. That false pair can impersonate a rank candidate and, because stronger candidates are preferred in an x-band, suppress the true rank.

v5.4.6 requires a lower paired glyph to have nontrivial area, width, and height. The new height floor rejects the observed one-pixel line while preserving actual suit glyph geometry.

### 3. Split narrow rank+suit fallback can choose a broad zero-overlap container

For narrow merged rank+suit columns, `FindComponent` previously returned the first component whose bounding rectangle contained the split rank anchor. A broad connected background/card component may geometrically contain that rectangle while contributing zero actual ink points inside the rank anchor.

v5.4.6 chooses the containing component with the greatest actual point overlap with the rank anchor, breaking ties in favor of the tighter component, and still fails closed if no component contributes ink.

## Safety properties

v5.4.6 does **not** lower the fan distance threshold, fan margin threshold, upright distance threshold, or upright margin threshold. It does not bypass physical-card uniqueness or Fantasy lineage checks. It changes the evidence bank and two deterministic geometry-selection defects only.

A deterministic regression validates:

- all original 13 fan rank exemplars remain accepted against the broadened bank;
- all original 13 upright-large rank exemplars remain accepted;
- the current field fan/reflow exemplars classify to their labelled rank under unchanged thresholds;
- the current field upright exemplars classify under unchanged thresholds;
- the one-pixel lower-line shape is rejected;
- the split-component fallback chooses positive-overlap rank lineage instead of a broad zero-overlap container.

## Separate issue: strategy quality

The normal-game execution path is now progressing through stabilization, policy, plan, drag, verification, and Confirm in the current field logs. Its move quality remains a separate strategic limitation: normal play is still driven by `SMART_BASELINE_V53`. Improving OFC placement quality should be treated as a strategy-engine milestone after Fantasy execution is live, not as a workaround inside perception or the executor.
