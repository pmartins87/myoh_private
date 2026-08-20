# OpenOFC card-recognition contract

## Scope

This document freezes the perception contract for KKPoker OFC Joker Ultimate in OpenOFC.

The normal OFC table is recognized from TableMap transforms. Standard-card rank and suit recognition must not depend on AutoOCR, template-area detection, PokerTracker, Hold'em hole-card semantics, or community-card semantics.

## Standard OFC cards

For every normal OFC physical slot, the canonical contract is:

- `<slot>empty`: colour/boolean transform that says the slot is empty;
- `<slot>back`: colour/boolean transform for a card back when that state is legal;
- `<slot>joker1` / `<slot>joker2`: persistent physical-Joker identity gates;
- `<slot>rank`: TableMap text transform;
- `<slot>suit`: TableMap text transform.

Recognition order is fail-closed:

1. EMPTY;
2. BACK when legal;
3. JK1 / JK2 physical identity;
4. standard rank + suit from TableMap text transforms;
5. optional explicitly certified Joker/native fallback;
6. UNKNOWN / reject the observation.

A non-empty slot that cannot be classified unambiguously must invalidate the current OFC observation. It must never be silently converted to an empty slot or guessed card.

## KKPoker_Fantasy15_v5 audit

The supplied `KKPoker_Fantasy15_v5.tm` is 450x830 and declares `ofc_variant = joker_ultimate`, two players, Hero chair 1, calibrated drag targets/executor, measured Fantasy15 geometry, Fantasy recognizer authority and Joker-detector authority.

Its normal OFC rank/suit regions use TableMap text transforms, specifically T1/T2/T3/T4/T5 depending on card scale and location. Examples include:

- Hero loose cards: T3;
- Hero discard tracker: T2;
- opponent/upper board geometry: T4/T5;
- Hero board geometry: T1.

The OFC-specific normal card path contains no A/AutoOCR transform. Legacy OpenHoldem fields still present in the TableMap can contain A0 or other Hold'em transforms; OpenOFC mode must keep those fields outside the OFC execution graph.

## Fantasy

Fantasy is a distinct perception route because the fan is curved and its geometry changes while cards are arranged.

The preferred direction remains TableMap/text-transform recognition wherever a stable per-card geometry can be defined. A native pixel recognizer or OCR may be used only for Fantasy-specific geometry when text transforms cannot provide a stable unambiguous mapping. Such a route must be separately certified and must never become an implicit fallback for normal OFC cards.

## Runtime invariants

- OpenOFC standard OFC scraper code may not call `p_auto_ocr`, `GetDetectTemplateResult`, `GetDetectTemplatesResult`, or `get_ocr_result`.
- Rank/suit reads must pass through `EvaluateRegion`, so the transform encoded in the TableMap remains the source of truth.
- Identical captured bitmaps reuse the previous perception result instead of repeatedly executing the same text transforms.
- After a drag, verification requires a changed/fresh capture and a newly reconstructed canonical state before the next drag or Confirm.
- Hold'em symbol engines, validator, handrank/PrWin logic and Hold'em action semantics remain bypassed in OpenOFC mode.

## Next implementation step

Consolidate the duplicated rank/suit parsing in `COFCScraper.cpp` behind one physical-card primitive that still reads the same TableMap text transforms and preserves the diagnostic rank/suit strings. This is a code-sharing refactor, not a switch to AutoOCR.
