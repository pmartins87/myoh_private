# OpenOFC development tracks

OpenOFC is developed on two parallel but explicitly separated tracks.

## Track F — Field Reliability

Scope: screen perception, physical-card lineage, input execution, confirmation/liveness, recovery, replay diagnostics, operator-visible status, build identity and field artifacts.

Current field milestone: **v5.8.3**.

Promotion rule: a field patch may make the runtime safer or more observable without silently changing strategic choices. Its materializer must prove the principal strategy/intelligence files are unchanged unless the release explicitly declares a strategic promotion.

## Track I — Strategic Intelligence

Scope: exact terminal evaluation, Joker semantics, Fantasy 14–17 search, R4 and earlier-round information-set teachers, hidden-world integration, MCCFR/CFR, suit symmetry, scaling, convergence and policy distillation.

Current work remains independently gated. Offline teacher or CFR progress does not become field authority merely because its workflow passes; promotion to the live policy requires its own explicit integration milestone and parity/regression evidence.

## Version ownership

Three numbers have different meanings and must not be conflated:

- **OpenOFC product/runtime version** — current composed executable, now 5.8.3;
- **TableMap asset version** — current paired screen map, 5.5.2;
- **TableMap protocol contract** — current contract integer, 5.

The operator UI must show the runtime version prominently and label the TableMap version as an asset. Future release layers update the centralized `COFCBuildInfo.h` instead of leaving old UI literals distributed through the codebase.
