from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel: str, old: str, new: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_result_scope():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    replace_once(
        rel,
        '''  // Result/Fantasy markers are deliberately processed before raw/canonical
  // validity. Scoring animations routinely make card slots unreadable.
  if (OpenOFCObserveResultAndMaybeClose(observation)) {
    if (observation.result_screen_visible) return;
  }
''',
        '''  // OPENOFC_RESULT_PHASE_SCOPE_V41: a visual result candidate has zero
  // authority during R0..R4. The previous v4 implementation evaluated the
  // opponent-discard probes on every heartbeat; those probes overlap normal
  // table pixels in this KKPoker layout and therefore produced a permanent
  // false RESULT that returned before StartDecision(). Only a runtime that has
  // already committed R4/Fantasy may consult result markers.
  if (g_openofc_flow_phase == kOpenOFCFlowWaitResult
      || g_openofc_flow_phase == kOpenOFCFlowFantasyContinuation) {
    const bool marker_calibrated = p_tablemap != NULL
      && p_tablemap->GetTMSymbol("openofc_result_marker_calibrated", 0) == 1;
    if (marker_calibrated) {
      if (OpenOFCObserveResultAndMaybeClose(observation)) {
        if (observation.result_screen_visible) return;
      }
    } else {
      g_openofc_result_stable = 0;
      if (observation.result_screen_visible
          || observation.hero_result_fantasy
          || observation.opponent_result_fantasy) {
        write_log(true,
          "[OpenOFC FLOW] result_candidate_ignored=1 reason=UNCALIBRATED phase=%s\\n",
          OpenOFCFlowName(g_openofc_flow_phase));
      }
    }
  } else {
    g_openofc_result_stable = 0;
  }
''')


def patch_scraper_result_calibration():
    rel = "OpenHoldem/COFCScraper.cpp"
    replace_once(
        rel,
        '''    obs->opponent_result_faceup_discards = faceup;
    obs->result_screen_visible = faceup >= 2;
''',
        '''    obs->opponent_result_faceup_discards = faceup;
    // OPENOFC_RESULT_MARKER_CALIBRATION_V41: these three legacy discard
    // rectangles are only candidates until a result-specific geometry is
    // calibrated from dedicated result frames. They must never authorize a
    // phase transition merely because ordinary board/logo pixels look face-up.
    const bool marker_calibrated = p_tablemap != NULL
      && p_tablemap->GetTMSymbol("openofc_result_marker_calibrated", 0) == 1;
    obs->result_screen_visible = marker_calibrated && faceup >= 2;
    if (!marker_calibrated && faceup >= 2) {
      write_log(true,
        "[OpenOFC PHASE] result_candidate=%d ignored=1 reason=UNCALIBRATED_RESULT_GEOMETRY\\n",
        faceup);
    }
''')


def patch_joker_presentation():
    rel = "OpenHoldem/COFCInspectorSnapshot.h"
    replace_once(
        rel,
        '''    if (value == kOFCCardJoker1) return "JK1";
    if (value == kOFCCardJoker2) return "JK2";
    if (value < 0 || value > 51) return "INVALID";
''',
        '''    if (value == kOFCCardJoker1) return "JK1";
    if (value == kOFCCardJoker2) return "JK2";
    // OPENOFC_JOKER_PRESENTATION_V41: raw rank token X is a valid generic
    // Joker occurrence before the reconstructor assigns JK1/JK2 identity.
    if (value == kOFCCardJokerGeneric) return "JK";
    if (value < 0 || value > 51) return "INVALID";
''')

    replace_once(
        rel,
        '''    out.Format("TMv%d | READ=%s STATE=%s | P%d H%d A%d D%d R%d | IN%d DISC%d",
      contract, raw_text, state_text, state->player_count, state->hero_chair,
      state->acting_chair, state->dealer_chair, state->round_index,
      state->hero_incoming_count, state->hero_discard_count);
''',
        '''    const CString incoming = CardsText(
      state->hero_incoming, state->hero_incoming_count);
    out.Format("TMv%d | READ=%s STATE=%s | P%d H%d A%d D%d R%d | IN=%s DISC%d",
      contract, raw_text, state_text, state->player_count, state->hero_chair,
      state->acting_chair, state->dealer_chair, state->round_index,
      incoming.GetString(), state->hero_discard_count);
''')


def patch_statusbar_contract():
    replace_once(
        "OpenHoldem/COpenHoldemStatusbar.cpp",
        '    const bool contract_ok = contract == 1;\n',
        '''    // OPENOFC_STATUSBAR_CONTRACT_V41: the visible interface must use the
    // same contract generation as the active runtime. v4 previously kept the
    // old v1 UI gate and displayed a blocked/stale interface while contract 4
    // automation was actually active.
    const bool contract_ok = contract == 4;
''')


def main():
    patch_result_scope()
    patch_scraper_result_calibration()
    patch_joker_presentation()
    patch_statusbar_contract()
    print("OpenOFC phase-flow v4.1 field-regression repair applied")


if __name__ == "__main__":
    main()
