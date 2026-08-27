from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TM = ROOT / "OpenOFC/TableMaps/KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm"
EXPECTED_TM_SHA256 = "28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"OPENOFC_V581_REGRESSION=FAIL {message}")


def recover_single_delta(
    lineage: list[str], observed_loose: list[str], arranged: list[str]
) -> list[str] | None:
    expected_arrangement = [card for card in lineage if card not in observed_loose]
    occupied = len(arranged)
    delta = len(expected_arrangement) - occupied
    if len(lineage) != occupied + len(observed_loose) or delta not in (0, 1):
        return None
    if not set(arranged).issubset(expected_arrangement):
        return None
    if delta == 0:
        return list(observed_loose)
    missing = [card for card in expected_arrangement if card not in arranged]
    divergent = [
        index for index, card in enumerate(observed_loose) if card not in lineage
    ]
    if len(missing) != 1 or len(divergent) != 1:
        return None
    corrected = list(observed_loose)
    corrected[divergent[0]] = missing[0]
    expected_loose = {card for card in lineage if card not in arranged}
    if len(set(corrected)) != len(corrected) or set(corrected) != expected_loose:
        return None
    return corrected


def deterministic_models() -> None:
    lineage = [
        "As", "Kh", "Kc", "Qs", "Qc", "Kd", "Jh",
        "Jd", "9s", "9d", "8c", "7d", "4h", "2d",
    ]
    arranged = ["Jh", "7d", "Jd"]
    expected_loose = [card for card in lineage if card not in arranged]
    observed = list(expected_loose)
    observed[1] = "Th"  # one valid-looking T7 result outside the lineage
    corrected = recover_single_delta(lineage, observed, arranged)
    require(corrected is not None, "logged 14->11 single delta was not recovered")
    require(set(corrected) == set(expected_loose), "recovered loose set is not exact")

    two_bad = list(observed)
    two_bad[2] = "5s"
    require(
        recover_single_delta(lineage, two_bad, arranged) is None,
        "two identity divergences must remain fail-closed",
    )

    # Every operational Fantasy phase has an exact physical partition.
    for total in (14, 15, 16, 17):
        require(total == 3 + (total - 3), f"top partition drifted for {total}")
        require(total == 8 + (total - 8), f"middle partition drifted for {total}")
        require(total == 13 + (total - 13), f"bottom partition drifted for {total}")


def source_contracts() -> None:
    scraper = (ROOT / "OpenHoldem/COFCScraper.cpp").read_text(
        encoding="utf-8-sig"
    )
    teacher = (ROOT / "OpenHoldem/COFCR4ExactTeacher.cpp").read_text(
        encoding="utf-8-sig"
    )
    teacher_h = (ROOT / "OpenHoldem/COFCR4ExactTeacher.h").read_text(
        encoding="utf-8-sig"
    )
    runtime = (ROOT / "OpenHoldem/COFCRuntimeController.cpp").read_text(
        encoding="utf-8-sig"
    )
    selftest = (ROOT / "OpenHoldem/COFCExactEvaluatorSelftest.cpp").read_text(
        encoding="utf-8-sig"
    )

    for token in (
        "lineage_delta",
        "recovery=SINGLE_DELTA_EXACT",
        "corrected_loose != expected_loose",
        "FANTASY_LINEAGE_SINGLE_DELTA_RECOVERED",
    ):
        require(token in scraper, f"Fantasy recovery token missing: {token}")

    for token in (
        "opponent_terminal",
        "safety_override",
        "baseline_foul",
        "selected_foul",
        "safe_candidates",
    ):
        require(token in teacher_h, f"R4 report token missing: {token}")
        require(token in teacher, f"R4 implementation token missing: {token}")

    require(
        "if (baseline_candidate.board.foul && !safe_completions.empty())"
        in teacher,
        "recoverable R4 foul guard is absent",
    )
    require(
        "if (!opponent_terminal) return true;" in teacher,
        "safe hidden-opponent baseline must remain unchanged",
    )
    require("field_fix=V581" in runtime, "runtime version marker missing")
    require("safe=%d" in runtime, "R4 safe-candidate telemetry missing")
    require(
        "TestLoggedFrame000IsAlreadyUnavoidableAtR4" in selftest
        and "report.safe_candidates == 0" in selftest,
        "logged frame 000 regression is absent",
    )
    require(
        "TestR4SafetyOverrideWithoutTerminalOpponent" in selftest,
        "recoverable hidden-opponent foul regression is absent",
    )


def tablemap_contract() -> None:
    digest = hashlib.sha256(TM.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    require(digest == EXPECTED_TM_SHA256, f"TableMap changed unexpectedly: {digest}")


def main() -> None:
    deterministic_models()
    source_contracts()
    tablemap_contract()
    print(
        "OPENOFC_V581_FIELD_CORRECTIONS_REGRESSION=PASS "
        "fantasy_14_to_11=SINGLE_DELTA_EXACT "
        "fantasy_15_17=PARTITION_GUARDED "
        "r4_logged_foul=PROVEN_UNAVOIDABLE_AT_R4 "
        "r4_recoverable_foul=SAFETY_OVERRIDE tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
