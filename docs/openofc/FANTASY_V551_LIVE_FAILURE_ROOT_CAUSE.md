# OpenOFC v5.5.1 — live failure root cause and paired bundle

The 2026-08-24 live log did not execute the v5.5 counted-text TableMap. It
loaded `KKPoker_Chines_v5_4_4_FANTASY_TEXT_TEST.tm`.

The runtime detected the 15-card fan repeatedly, then rejected every attempt:

```text
[OpenOFC FANTASY ENTRY] dynamic=1 dynamic_count=15 route=TRY_FANTASY
[OpenOFC FANTASY V550] counted-text TableMap opt-in missing terminal=0
[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION
```

Observed totals in the supplied log:

- 78 stable detections of count 15;
- one transitional detection of count 14;
- 79 explicit rejections for missing counted-text opt-in;
- 120 ticks suppressed as invalid perception;
- zero policy, plan or executor attempts.

The loaded v5.4.4 TableMap had only the count-15 rank/suit family and omitted
`openofc_fantasy_tablemap_text_by_count=1`. It could not support the stable
post-TOP and post-MIDDLE counts even if the opt-in were added manually.

A second independent defect existed in the UI: the status bar still treated
contract 1 as valid while the current OpenOFC runtime contract is 5. This made
the visible `TM BLOCKED` label disagree with the runtime's own contract gate.

v5.5.1 closes the packaging and observability gap:

1. patches the status bar to require contract 5;
2. displays whether the exact counted-text opt-in is present;
3. shows the paired-TableMap status in the main OpenOFC view;
4. stores the tested TableMap in the repository;
5. copies that exact TableMap into the CI artifact;
6. validates all 256 counted rank/suit regions before compilation.

The supplied `frame000060.bmp` is byte-identical to the calibrated stable
replay frame and decodes with the paired TableMap as:

```text
Ac Ad Qd Tc 8c 7h 7c 6d 5c 4h 4d 3s 3c 3d 2s
```

Count 17 remains fail-closed until a real frame is available.
