# OpenOFC v5.4.3H — run 32542305344 failure audit

Authoritative failed run: `32542305344`, job `96954520530`.

The complete frozen v5.3 -> v5.4 -> v5.4.2B -> v5.4.2C -> v5.4.3 -> v5.4.3G materialization chain passed. v5.4.3H failed closed while applying the H patch with:

`RuntimeError: HandlePostConfirm unchanged-state block shape changed`

Root cause: the H patch was written against an older post-Confirm controller shape. The materialized v4 phase engine owns Fantasy/final-round post-Confirm waiting directly inside the `phase_ == kConfirmSent` branch of `COFCRuntimeController::Tick()`. `HandlePostConfirm()` is the normal-round continuation path and is not the authoritative Fantasy acknowledgement path.

Repair rule: patch and dynamically exercise the actual `Tick()` Fantasy `kConfirmSent` branch. Do not weaken the source contract and do not declare `FANTASY_CONFIRM_GATE=PASS` until the corrected Windows workflow runs through the dynamic controller regression and Release|Win32 successfully.

`FIELD_PACKAGE_AUTHORIZED=0`.
