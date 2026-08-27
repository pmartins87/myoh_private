# OpenOFC v5.4.5 CI retry

The first v5.4.5 materialization run proved that the legacy main-Tick `INVALID_PERCEPTION` guard had a generated shape different from the observability patch's exact text anchor. `normalize_openofc_observability_input_v545pre.py` now canonicalizes only that final Tick guard before the v5.4.5 observability layer is applied. The authoritative PR gate also runs the post-layer empty-sentinel normalization before compilation.
