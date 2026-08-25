from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TM = ROOT / "OpenOFC/TableMaps/KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm"
EXPECTED_TM_SHA256 = "28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6"


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"OPENOFC_V580_REGRESSION=FAIL {message}")


def main() -> None:
    observation = text("OpenHoldem/COFCVisualObservation.h")
    scraper = text("OpenHoldem/COFCScraper.cpp")
    runtime_h = text("OpenHoldem/COFCRuntimeController.h")
    runtime = text("OpenHoldem/COFCRuntimeController.cpp")
    replay_h = text("OpenHoldem/CSymbolEngineReplayFrameController.h")
    replay = text("OpenHoldem/CSymbolEngineReplayFrameController.cpp")
    project = text("OpenHoldem/OpenHoldem.vcxproj")

    for token in (
        "COFCIdentityProbeEvidence",
        "candidate_available",
        "candidate_source",
        "known_values",
        "staging_row",
    ):
        require(token in observation, f"missing observation token {token}")

    require("invalid_count == 1 && !duplicate_identity" in scraper,
            "Fantasy single-anomaly guard missing")
    require("duplicate_identity" in scraper and "FAIL_CLOSED" in scraper,
            "Fantasy duplicate ambiguity must stay fail-closed")
    require("CompleteOneUnknown" in scraper
            and "PROBED_IDENTITY_PLUS_LINEAGE" in scraper,
            "probed Fantasy identity cache/lineage route missing")

    require("kIdentityProbe" in runtime_h
            and "COFCUnknownCardProbe identity_probe_" in runtime_h,
            "runtime probe transaction state missing")
    for token in (
        "NORMAL_IDENTITY_PROBE_BEFORE_INPUT",
        "FANTASY_IDENTITY_PROBE_BEFORE_INPUT",
        "IDENTITY_PROBE_RESOLVED_ON_BOARD",
        "FANTASY_IDENTITY_PROBE_COMPLETE",
        "DragRectToRect",
        "ClickRectsBoundedOFC",
        "ClickRectBoundedOFC",
        "EvaluateOFCRecoveryLiveness",
        "BOUNDED_REACQUIRE_RELEASE",
        "EXACT_FANTASY_R4_IDREC_V580",
    ):
        require(token in runtime, f"missing runtime token {token}")

    require("RequestOpenOFCReplayFrame" in replay_h
            and "ShootReplayFrameIfNotYetDone" in replay,
            "BMP+HTML replay capture hook missing")
    require("COFCIdentityRecoveryCache.cpp" in project
            and "COFCUnknownCardProbe.cpp" in project,
            "new recovery sources absent from Release project")

    duplicate_arm = (
        'ArmDecisionStabilization(state, "NEW_HAND_EDGE");\n'
        '        ArmDecisionStabilization(state, "NEW_HAND_EDGE");'
    )
    require(duplicate_arm not in runtime,
            "adjacent duplicate new-hand stabilization arm returned")
    require("if (phase_ == kReacquire) {\n    if (!state.valid" not in runtime,
            "absorbing/empty reacquire block returned")

    # Git for Windows may check text TableMaps out with CRLF. Hash the canonical
    # content, exactly like the v5.7 gate, so EOL conversion is not misreported
    # as a semantic TableMap edit.
    tm_hash = hashlib.sha256(TM.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    require(tm_hash == EXPECTED_TM_SHA256,
            f"paired TableMap changed unexpectedly: {tm_hash}")
    print(
        "OPENOFC_V580_ACTIVE_IDENTITY_RECOVERY_REGRESSION=PASS "
        "normal=ONE_UNKNOWN_BOARD_DELTA fantasy=ONE_SOURCE_REVERSIBLE "
        "multi_unknown=FAIL_CLOSED replay=BMP_HTML "
        "reacquire=BOUNDED_NONABSORBING "
        f"tablemap_sha256={tm_hash}"
    )


if __name__ == "__main__":
    main()
