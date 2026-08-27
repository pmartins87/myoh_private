# OpenOFC v5.8.3 — truthful runtime version and status

## Field finding

The v5.8.x executable was still presenting old v5.5.x UI language inherited from the paired-TableMap milestone. This mixed two independent version domains: the OpenOFC composed runtime and the TableMap asset. The status lifecycle also allowed a prior `CALCULANDO JOGADA` message to remain visible after the controller had entered a fail-closed or non-actionable state.

## Version contract

v5.8.3 introduces one centralized product identity in `OpenHoldem/COFCBuildInfo.h`:

- OpenOFC product/runtime: **5.8.3**;
- paired TableMap asset: **5.5.2**;
- TableMap protocol contract: **5**.

These values are deliberately distinct. A TableMap contract number or asset filename must never be rendered as the OpenOFC runtime version. The paired `KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm` remains bit-identical because this field fix does not recalibrate perception.

## Status contract

The runtime now treats the visible status as part of the safety contract:

- `CALCULANDO JOGADA` is emitted only while `StartDecision` is actually computing a decision;
- `EXECUTANDO JOGADA` is emitted while arrangement execution is active;
- `AGUARDANDO RESULTADO` is emitted after Confirm;
- `AGUARDANDO VEZ / TRANSICAO` is emitted when Hero cannot act;
- an invalid scrape emits `LEITURA INVALIDA - aguardando nova leitura; sem agir` rather than leaving a stale calculation message;
- terminal `Block(reason)` stores the exact reason and immediately emits `TRAVADO - <reason>`;
- every heartbeat in `kBlocked` reasserts the same durable reason until a semantic new-hand reset.

A transient invalid perception remains recoverable and therefore is not mislabeled as a permanent terminal block.

## Two-track development model

This release formalizes the project as two parallel tracks:

1. **Field Reliability** — perception, execution, liveness, UI truthfulness, diagnostics, replay evidence and field-test binaries. v5.8.3 belongs to this track.
2. **Strategic Intelligence** — exact evaluators, Fantasy search, R4/R3 information-set teachers, CFR/scaling/convergence and later certified policy promotion.

A Field Reliability patch must not silently change strategy. The v5.8.3 materializer hashes the five principal intelligence sources immediately before and after the field-only patch and fails if any hash changes.

## Gate

The authoritative Windows gate materializes v5.3 through v5.8.3, re-runs the v5.8.2 field regressions, runs the v5.8.3 UI/status contract test, verifies the paired TableMap SHA-256, proves intelligence-source hashes are unchanged, builds Release Win32 and publishes `OpenOFC_v583_FIELD_OBSERVABILITY_TEST`.
