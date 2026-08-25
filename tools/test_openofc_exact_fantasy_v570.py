from __future__ import annotations

import hashlib
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
    solver = read("OpenHoldem/COFCFantasyExactSolver.cpp")
    solver_h = read("OpenHoldem/COFCFantasyExactSolver.h")
    evaluator = read("OpenHoldem/COFCExactEvaluator.cpp")
    evaluator_h = read("OpenHoldem/COFCExactEvaluator.h")
    decision = read("OpenHoldem/COFCDecisionPolicy.cpp")
    runtime = read("OpenHoldem/COFCRuntimeController.cpp")
    project = read("OpenHoldem/OpenHoldem.vcxproj")
    python_engine = read("tools/openofc_solver/engine.py")
    parity_probe = read("tools/openofc_solver/cpp_exact_parity_probe.cpp")

    assert "ImproveUniversally" in solver_h and "14..17" in solver_h
    assert "for (size_t b = 0; b < masks5.size(); ++b)" in solver
    assert "for (size_t m = 0; m < masks5.size(); ++m)" in solver
    assert "top_frontier" in solver and "Dominates" in solver
    assert "left.royalties < right.royalties" in solver
    assert "!left.refantasy && right.refantasy" in solver
    assert "CompareHands" in solver
    assert "EvaluateRowCandidates" in evaluator_h
    assert "ResolveBoardCandidates" in evaluator_h
    assert "CandidateRanks" in evaluator
    assert "value % 13 + 2" in evaluator and "value / 13" in evaluator
    assert "SameNominalCard" in evaluator and "ContainsNominalCard" in evaluator
    assert "COFCFantasyExactSolver::ImproveUniversally" in decision
    assert "engine=EXACT_FANTASY_R4_V570" in runtime
    assert "[OpenOFC EXACT FANTASY]" in runtime
    assert '<ClCompile Include="COFCFantasyExactSolver.cpp">' in project
    assert "KKPoker row-local semantics" in python_engine
    assert "COFCExactEvaluator::EvaluateBoard" in parity_probe
    assert "COFCExactEvaluator::EvaluateRowCandidates" in parity_probe


def tablemap_contract() -> None:
    canonical = TM.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(canonical).hexdigest()
    assert digest == "28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6"


def main() -> None:
    source_contracts()
    tablemap_contract()
    print(
        "OPENOFC_EXACT_FANTASY_V570_REGRESSION=PASS "
        "counts=14,15,16,17 jokers=JK1,JK2 "
        "authority=UNIVERSAL_DOMINANCE "
        "tablemap_sha256=28587f10d3f8436880e6ef98280b5f86d85e26b674f15cfe61f5a03bc5751ee6"
    )


if __name__ == "__main__":
    main()
