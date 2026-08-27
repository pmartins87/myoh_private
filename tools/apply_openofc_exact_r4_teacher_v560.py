from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_source(relative: str):
    path = ROOT / relative
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool) -> None:
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path, text, eol, bom = read_source(relative)
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{relative}: {label} expected exactly one target, got {count}"
        )
    write_source(path, text.replace(old, new, 1), eol, bom)
    print(f"patched {relative}: {label}", flush=True)


def main() -> None:
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '#include "COFCBaselinePolicy.h"\n',
        '#include "COFCDecisionPolicy.h"\n',
        "route live decisions through hybrid exact policy",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  COFCStrategyAction action;
  string error;
  write_log(true,
    "[OpenOFC POLICY] engine=SMART_BASELINE_V53 round=%d fantasy=%d incoming=%d\\n",
    state.round_index,
    state.players[state.hero_chair].fantasy ? 1 : 0,
    state.hero_incoming_count);
  OpenOFCSetUserStatus("CALCULANDO JOGADA");
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    write_log(k_always_log_errors,
      "[DeepOFC POLICY] result=REJECTED reason=\\\"%s\\\"\\n", error.c_str());
    Recover("policy refused state: " + error);
    return false;
  }
''',
        '''  COFCStrategyAction action;
  COFCDecisionPolicyReport policy_report;
  string error;
  write_log(true,
    "[OpenOFC POLICY] engine=HYBRID_EXACT_R4_V560 round=%d fantasy=%d incoming=%d\\n",
    state.round_index,
    state.players[state.hero_chair].fantasy ? 1 : 0,
    state.hero_incoming_count);
  OpenOFCSetUserStatus("CALCULANDO JOGADA");
  if (!COFCDecisionPolicy::Choose(
        state, &action, &policy_report, &error)) {
    write_log(k_always_log_errors,
      "[DeepOFC POLICY] result=REJECTED reason=\\\"%s\\\"\\n", error.c_str());
    Recover("policy refused state: " + error);
    return false;
  }
  if (policy_report.exact_r4_attempted) {
    write_log(true,
      "[OpenOFC EXACT R4] available=%d applied=%d candidates=%d legal=%d "
      "baseline_points=%d selected_points=%d baseline_fantasy=%d "
      "selected_fantasy=%d reason=\\\"%s\\\"\\n",
      policy_report.exact_r4.exact_available ? 1 : 0,
      policy_report.exact_r4.applied ? 1 : 0,
      policy_report.exact_r4.candidates,
      policy_report.exact_r4.legal_candidates,
      policy_report.exact_r4.baseline_points,
      policy_report.exact_r4.selected_points,
      policy_report.exact_r4.baseline_fantasy_cards,
      policy_report.exact_r4.selected_fantasy_cards,
      policy_report.exact_r4_reason.c_str());
  }
''',
        "compose smart fallback with exact R4 teacher and telemetry",
    )
    print(
        "OPENOFC_EXACT_R4_TEACHER_V560_APPLY=PASS "
        "engine=HYBRID_EXACT_R4_V560 tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
