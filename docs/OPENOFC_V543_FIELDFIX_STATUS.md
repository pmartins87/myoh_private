# OpenOFC v5.4.3 field-fix status

The first certified field package was revoked after the live log proved a runtime/TableMap contract mismatch (`runtime=5`, packaged TableMap `contract=3`).

The repair branch is intentionally validated with the repair PR temporarily closed so unrelated historical `pull_request` workflows do not consume runner capacity while the exact-workspace package gate is iterated.

Current repair requirements:

- derive the package TableMap from the clean v5.2 lineage;
- require `openofc_contract=5` and zero legacy Hold'em gameplay regions;
- require runtime/TableMap contract equality before build/package;
- materialize G/H and E/F in the same workspace from which `OpenHoldem.exe` is built;
- rerun generic continuity, real-pixel, real-Joker, Confirm and physical-executor regressions before packaging;
- keep `FIELD_PACKAGE_AUTHORIZED=0` until a new controlled field retest proves real actions.
