# OpenOFC legacy red-check audit

Date: 2026-08-21
Branch context: `openofc-v543-hbitmap-v2`, descendant of `eb4dcab55674bdac4c00c2282924c817ea371ef0`.

This note records why three older red checks on PR #6 must not be interpreted as evidence that the current v5.4.3 Generic Fantasy / real-pixel path regressed.

## Run 32460647646 — Fantasy v5 row-batch build

Failure occurs while re-applying the historical v5 patch to a tree that already contains later repairs. `tools/apply_openofc_fantasy_v5.py` expects exactly one occurrence of:

```
  orchestrator_.ResetForKnownNewHand();
  plan_.Reset();
```

but the later merged source contains two occurrences, so the historical patcher aborts with `expected one target, got 2`. No compilation or runtime assertion is reached. This is a stale/non-idempotent historical patch workflow against a newer source tree, not a v5.4.3 runtime failure.

## Run 32460647619 — Fantasy v5b field build

The v5 source repair and source-contract checks both pass. The TableMap validator itself also reports PASS. The subsequent PowerShell verification fails with `missing Fantasy row action top` after appending the row-action regions. This is a historical materialization/verification mismatch in the old v5 workflow. It does not exercise the current v5.4.3 HBITMAP recognizer or Generic Fantasy reconstructor.

## Run 32460647638 — v5.3 smart baseline + opponent history

The full repair chain through v5.3 applies, source-contract assertions pass, the history-aware TableMap materializes, and the standalone C++ policy selftest compiles successfully. The executable then returns exit code 1, but this historical workflow does not emit the failing assertion text. Later v5.4.x gates on the same PR head pass. This check remains useful as historical evidence, but its red status cannot by itself be treated as a current v5.4.3 regression without reproducing the specific v5.3 policy assertion under the current contract.

## Policy

Do not hide or falsify these failures. Preserve them as historical diagnostics. Release authorization must be based on the current-version gates that actually exercise the current source contract. If an older workflow is retained on a branch containing later patches, it should either be made idempotent/version-scoped or clearly marked historical so that re-applying an old patcher to a new tree does not create misleading red checks.

`FIELD_PACKAGE_AUTHORIZED=0`
