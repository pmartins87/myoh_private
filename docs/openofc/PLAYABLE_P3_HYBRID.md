# OpenOFC v5.9.0 P3 hybrid

This build keeps the proven v5.8.3 perception and physical executor and changes
the strategy source for complete Normal/Normal heads-up hands:

- Normal/Normal from the first round: trained P3 B0/B1 policy;
- Fantasy15: existing operational Fantasy policy;
- Normal versus Fantasy, mid-hand attachment, or unavailable P3 files: existing
  operational baseline for the rest of that hand.

The fallback is deliberate. A P3 history mismatch must not freeze a valid table,
and the P3 policy must never invent public actions that were not observed.

## Files

Keep these files together in the same directory:

- `OpenHoldem.exe` and its DLLs;
- `playable_p3_native_manifest.json`;
- `playable_p3_b0_weights.f64le`;
- `playable_p3_b1_weights.f64le`.

Use `KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm` as the TableMap.

## Useful log markers

- `[OpenOFC P3 POLICY] load=PASS`: weights loaded;
- `[DeepOFC PLAN] source=P3`: trained policy selected the action;
- `[OpenOFC P3 FALLBACK]`: this hand reverted to the operational baseline;
- `[DeepOFC CONFIRM]`: the verified arrangement reached Confirm.

For the first real test, attach before a new Normal/Normal hand begins and keep
the table at the same 450x830 geometry used by the v5.5.2 TableMap.
