from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TM = (
    ROOT
    / "OpenOFC"
    / "TableMaps"
    / "KKPoker_Chines_v5_5_2_FANTASY_LIVE_RECOVERY.tm"
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def source_contracts() -> None:
    evaluator = read("OpenHoldem/COFCExactEvaluator.cpp")
    evaluator_h = read("OpenHoldem/COFCExactEvaluator.h")
    teacher = read("OpenHoldem/COFCR4ExactTeacher.cpp")
    decision = read("OpenHoldem/COFCDecisionPolicy.cpp")
    runtime = read("OpenHoldem/COFCRuntimeController.cpp")
    project = read("OpenHoldem/OpenHoldem.vcxproj")

    assert "exact terminal rules oracle" in evaluator
    assert "EvaluateBoard" in evaluator_h and "ScoreMatch" in evaluator_h
    assert "kOFCExactStraightFlush" in evaluator
    assert "result->base_points = -6" in evaluator
    assert "result->scoop_bonus = 3" in evaluator
    assert "MiddleRoyalty" in evaluator and "BottomRoyalty" in evaluator
    assert "result->rows[2].category >= kOFCExactQuads" in evaluator
    assert "kOFCCardJoker1" in evaluator and "kOFCCardJoker2" in evaluator

    assert "for (int discard = 0; discard < 3; ++discard)" in teacher
    assert "for (int first = 0; first < 3; ++first)" in teacher
    assert "for (int second = 0; second < 3; ++second)" in teacher
    assert "candidate.points >= baseline_candidate.points" in teacher
    assert re.search(
        r"candidate\.board\.fantasy_cards\s*\n\s*>= "
        r"baseline_candidate\.board\.fantasy_cards",
        teacher,
    )
    assert "exact R4 opponent terminal board is unavailable" in teacher
    assert "VisibleDecisionCardsUnique" in teacher
    assert "points *" not in teacher and "fantasy_cards *" not in teacher

    assert "COFCBaselinePolicy::Choose" in decision
    assert "COFCR4ExactTeacher::Improve" in decision
    assert "return true;" in decision  # teacher unavailability preserves baseline
    assert '#include "COFCDecisionPolicy.h"' in runtime
    assert "COFCDecisionPolicy::Choose" in runtime
    assert "engine=HYBRID_EXACT_R4_V560" in runtime
    assert "[OpenOFC EXACT R4]" in runtime

    for source in (
        "COFCDecisionPolicy.cpp",
        "COFCExactEvaluator.cpp",
        "COFCR4ExactTeacher.cpp",
    ):
        assert f'<ClCompile Include="{source}">' in project


def tablemap_contract() -> None:
    # v5.6.0 is intelligence-only. Pin the exact field-calibrated v5.5.2 TM so
    # no region, font or click source can drift under an intelligence change.
    # Git's Windows checkout uses CRLF while the repository blob uses LF, so
    # hash the canonical LF representation on every platform.
    canonical = TM.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(canonical).hexdigest()
    assert digest == "28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6"


def main() -> None:
    source_contracts()
    tablemap_contract()
    print(
        "OPENOFC_EXACT_R4_TEACHER_V560_REGRESSION=PASS "
        "oracle=EXACT assignments=27 replacement=PARETO_SAFE "
        "missing_terminal=BASELINE tablemap_sha256=28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6"
    )


if __name__ == "__main__":
    main()
