from __future__ import annotations

from pathlib import Path
import re

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


def regex_once(rel: str, pattern: str, replacement: str, flags=re.S):
    path, text, eol, bom = read_source(rel)
    new, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{rel}: regex expected one target, got {count}: {pattern[:120]}")
    write_source(path, new, eol, bom)
    print(f"patched {rel}")


def patch_visual_phase_contract():
    rel = "OpenHoldem/COFCVisualObservation.h"
    replace_once(
        rel,
        '''    hero_can_prepare = false;
    hero_timer_active = false;
    confirm_visible = false;
''',
        '''    hero_can_prepare = false;
    hero_timer_active = false;
    confirm_visible = false;
    opponent_result_faceup_discards = 0;
    result_screen_visible = false;
    hero_result_fantasy = false;
    opponent_result_fantasy = false;
''')
    replace_once(
        rel,
        '''  bool confirm_visible;

  COFCVisualPlayerObservation players[kOFCMaxPlayers];
''',
        '''  bool confirm_visible;

  // OPENOFC_PHASE_MARKERS_V4: result/continuation facts are scraped before
  // normal card-state validation, so animation frames may be ignored without
  // losing the only safe end-of-match signal.
  int opponent_result_faceup_discards;
  bool result_screen_visible;
  bool hero_result_fantasy;
  bool opponent_result_fantasy;

  COFCVisualPlayerObservation players[kOFCMaxPlayers];
''')


def patch_scraper_phase_markers():
    rel = "OpenHoldem/COFCScraper.cpp"
    helper = r'''
static bool OpenOFCReadOptionalBoolean(
    CScraper *scraper, const CString &region, bool *value) {
  if (scraper == NULL || value == NULL) return false;
  *value = false;
  if (!DeepOFCRegionExists(region)) return false;
  scraper->EvaluateTrueFalseRegion(value, region);
  return true;
}

static void OpenOFCScrapePhaseMarkers(
    CScraper *scraper,
    COFCVisualObservation *obs,
    int player_count,
    int hero_chair) {
  if (scraper == NULL || obs == NULL) return;

  // Terminal result marker: opponent discards are face-up only on the scoring
  // result screen. During R1..R4 they are hidden backs. Identity is irrelevant,
  // so missing T2 K/X can never suppress this end-of-hand signal.
  if (player_count == 2 && hero_chair >= 0 && hero_chair < 2) {
    const int opponent = 1 - hero_chair;
    int faceup = 0;
    for (int i = 0; i < 3; ++i) {
      CString empty_region, back_region;
      empty_region.Format("ofc_p%d_discard%dempty", opponent, i);
      back_region.Format("ofc_p%d_discard%dback", opponent, i);
      bool empty = true;
      bool back = false;
      const bool have_empty =
        OpenOFCReadOptionalBoolean(scraper, empty_region, &empty);
      const bool have_back =
        OpenOFCReadOptionalBoolean(scraper, back_region, &back);
      if (have_empty && have_back && !empty && !back) ++faceup;
    }
    obs->opponent_result_faceup_discards = faceup;
    obs->result_screen_visible = faceup >= 2;
  }

  bool per_player_fantasy[kOFCMaxPlayers] = {false, false, false};
  for (int p = 0; p < player_count; ++p) {
    int hits = 0;
    for (int i = 0; i < 3; ++i) {
      CString region;
      region.Format("ofc_p%d_result_fantasy%d", p, i);
      bool value = false;
      if (OpenOFCReadOptionalBoolean(scraper, region, &value) && value) {
        ++hits;
      }
    }
    // Two-of-three avoids a single animated score/gold pixel becoming Fantasy.
    per_player_fantasy[p] = hits >= 2;
  }
  if (hero_chair >= 0 && hero_chair < player_count) {
    obs->hero_result_fantasy = per_player_fantasy[hero_chair];
    if (player_count == 2) {
      obs->opponent_result_fantasy = per_player_fantasy[1 - hero_chair];
    }
  }

  if (obs->result_screen_visible
      || obs->hero_result_fantasy
      || obs->opponent_result_fantasy) {
    write_log(true,
      "[OpenOFC PHASE] result=%d opp_faceup_discards=%d hero_fantasy=%d opponent_fantasy=%d\n",
      obs->result_screen_visible ? 1 : 0,
      obs->opponent_result_faceup_discards,
      obs->hero_result_fantasy ? 1 : 0,
      obs->opponent_result_fantasy ? 1 : 0);
  }
}

'''
    path, text, eol, bom = read_source(rel)
    anchor = "bool CScraper::ScrapeOFCVisualObservation() {"
    if text.count(anchor) != 1:
        raise RuntimeError(f"{rel}: phase-helper anchor missing")
    text = text.replace(anchor, helper + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")

    replace_once(
        rel,
        '''  obs->player_count = player_count;
  obs->hero_chair = hero_chair;

  // Route Fantasy BEFORE touching normal Hero row/incoming geometry.
''',
        '''  obs->player_count = player_count;
  obs->hero_chair = hero_chair;

  // OPENOFC_PHASE_MARKERS_V4 runs before the normal/Fantasy routing and before
  // any card-slot rejection. Result animations must never erase a safe-exit or
  // Fantasy-continuation marker.
  OpenOFCScrapePhaseMarkers(this, obs, player_count, hero_chair);

  // Route Fantasy BEFORE touching normal Hero row/incoming geometry.
''')


def patch_runtime_phase_engine():
    rel = "OpenHoldem/COFCRuntimeController.cpp"

    path, text, eol, bom = read_source(rel)
    if "#include <ctime>\n" not in text:
        text = text.replace("#include <algorithm>\n", "#include <algorithm>\n#include <ctime>\n", 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")

    flow_helpers = r'''
enum EOpenOFCFlowPhaseV4 {
  kOpenOFCFlowWaitInitial5 = 0,
  kOpenOFCFlowRoundActive,
  kOpenOFCFlowWaitNext3,
  kOpenOFCFlowWaitResult,
  kOpenOFCFlowFantasyContinuation
};

EOpenOFCFlowPhaseV4 g_openofc_flow_phase = kOpenOFCFlowWaitInitial5;
int g_openofc_expected_round = 0;
int g_openofc_result_stable = 0;
bool g_openofc_stop_initialized = false;
bool g_openofc_stop_requested = false;
bool g_openofc_close_sent = false;
time_t g_openofc_stop_deadline = 0;

const char *OpenOFCFlowName(EOpenOFCFlowPhaseV4 phase) {
  switch (phase) {
    case kOpenOFCFlowWaitInitial5: return "WAIT_INITIAL_5";
    case kOpenOFCFlowRoundActive: return "ROUND_ACTIVE";
    case kOpenOFCFlowWaitNext3: return "WAIT_NEXT_3";
    case kOpenOFCFlowWaitResult: return "WAIT_RESULT";
    case kOpenOFCFlowFantasyContinuation: return "FANTASY_CONTINUATION";
    default: return "UNKNOWN";
  }
}

bool OpenOFCNormalDecisionReady(const COFCState &state) {
  if (!state.valid || state.hero_chair < 0
      || state.hero_chair >= state.player_count) return false;
  if (state.players[state.hero_chair].fantasy) return true;
  if (state.round_index < 0 || state.round_index > 4) return false;
  const int expected_incoming = state.round_index == 0 ? 5 : 3;
  return state.hero_incoming_count == expected_incoming
    && state.action_required && state.hero_can_prepare;
}

void OpenOFCArmStopDeadlineIfNeeded() {
  if (g_openofc_stop_initialized || p_tablemap == NULL) return;
  g_openofc_stop_initialized = true;
  if (p_tablemap->GetTMSymbol("openofc_stop_enabled", 0) != 1) {
    write_log(true, "[OpenOFC SESSION] stop_schedule=DISABLED\n");
    return;
  }
  const int hhmm = p_tablemap->GetTMSymbol("openofc_stop_local_hhmm", -1);
  const int hh = hhmm / 100;
  const int mm = hhmm % 100;
  if (hhmm < 0 || hh < 0 || hh > 23 || mm < 0 || mm > 59) {
    write_log(k_always_log_errors,
      "[OpenOFC SESSION] stop_schedule=INVALID hhmm=%d; disabled\n", hhmm);
    return;
  }

  const time_t now = time(NULL);
  struct tm local_now;
  localtime_s(&local_now, &now);
  struct tm target = local_now;
  target.tm_hour = hh;
  target.tm_min = mm;
  target.tm_sec = 0;
  time_t deadline = mktime(&target);
  if (deadline <= now) {
    target = local_now;
    target.tm_mday += 1;
    target.tm_hour = hh;
    target.tm_min = mm;
    target.tm_sec = 0;
    deadline = mktime(&target);
  }
  g_openofc_stop_deadline = deadline;
  struct tm local_target;
  localtime_s(&local_target, &deadline);
  write_log(true,
    "[OpenOFC SESSION] stop_armed local=%04d-%02d-%02d %02d:%02d\n",
    local_target.tm_year + 1900, local_target.tm_mon + 1,
    local_target.tm_mday, local_target.tm_hour, local_target.tm_min);
}

void OpenOFCUpdateStopRequest() {
  OpenOFCArmStopDeadlineIfNeeded();
  if (g_openofc_stop_requested || g_openofc_stop_deadline == 0) return;
  const time_t now = time(NULL);
  if (now >= g_openofc_stop_deadline) {
    g_openofc_stop_requested = true;
    write_log(true,
      "[OpenOFC SESSION] stop_requested=1 policy=FINISH_MATCH_CHAIN\n");
  }
}

bool OpenOFCObserveResultAndMaybeClose(
    const COFCVisualObservation &observation) {
  if (!observation.result_screen_visible) {
    g_openofc_result_stable = 0;
    return false;
  }

  const int required = p_tablemap == NULL ? 2
    : max(2, p_tablemap->GetTMSymbol("openofc_result_debounce_frames", 2));
  ++g_openofc_result_stable;
  const bool fantasy = observation.hero_result_fantasy
    || observation.opponent_result_fantasy;
  write_log(true,
    "[OpenOFC FLOW] marker=RESULT stable=%d/%d fantasy=%d hero_fantasy=%d opponent_fantasy=%d\n",
    g_openofc_result_stable, required, fantasy ? 1 : 0,
    observation.hero_result_fantasy ? 1 : 0,
    observation.opponent_result_fantasy ? 1 : 0);

  if (fantasy) {
    g_openofc_flow_phase = kOpenOFCFlowFantasyContinuation;
    if (g_openofc_result_stable >= required) {
      write_log(true,
        "[OpenOFC SESSION] safe_end=0 reason=FANTASY_CONTINUATION stop_requested=%d\n",
        g_openofc_stop_requested ? 1 : 0);
    }
    return true;
  }

  if (g_openofc_result_stable < required) return true;

  write_log(true,
    "[OpenOFC SESSION] safe_end=1 stop_requested=%d\n",
    g_openofc_stop_requested ? 1 : 0);
  g_openofc_flow_phase = kOpenOFCFlowWaitInitial5;
  g_openofc_expected_round = 0;

  if (g_openofc_stop_requested && !g_openofc_close_sent) {
    if (p_tablemap == NULL
        || p_tablemap->GetTMSymbol("openofc_safe_exit_calibrated", 0) != 1) {
      write_log(k_always_log_errors,
        "[OpenOFC SESSION] close_suppressed=1 reason=SAFE_EXIT_NOT_CALIBRATED\n");
      return true;
    }
    if (p_casino_interface != NULL && p_casino_interface->CloseWindow()) {
      g_openofc_close_sent = true;
      write_log(true,
        "[OpenOFC SESSION] closing_table=1 reason=SCHEDULED_SAFE_END\n");
    } else {
      write_log(k_always_log_errors,
        "[OpenOFC SESSION] closing_table=0 reason=CLOSE_WINDOW_FAILED\n");
    }
  }
  return true;
}

void OpenOFCOnConfirmSent(const COFCState &state) {
  if (state.players[state.hero_chair].fantasy || state.round_index == 4) {
    g_openofc_flow_phase = kOpenOFCFlowWaitResult;
    g_openofc_expected_round = -1;
    write_log(true,
      "[OpenOFC FLOW] marker=CONFIRM_COMMITTED round=%d next=WAIT_RESULT fantasy=%d\n",
      state.round_index,
      state.players[state.hero_chair].fantasy ? 1 : 0);
  } else {
    g_openofc_expected_round = state.round_index + 1;
    g_openofc_flow_phase = kOpenOFCFlowWaitNext3;
    write_log(true,
      "[OpenOFC FLOW] marker=CONFIRM_COMMITTED round=%d next=WAIT_NEXT_3 expected_round=%d\n",
      state.round_index, g_openofc_expected_round);
  }
}

'''
    path, text, eol, bom = read_source(rel)
    anchor = "}  // namespace\n"
    if text.count(anchor) != 1:
        raise RuntimeError(f"{rel}: namespace close anchor missing")
    text = text.replace(anchor, flow_helpers + "\n" + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")

    replace_once(
        rel,
        '''  phase_ = kConfirmSent;
  write_log(true,
    "[DeepOFC FP0] Confirm sent once; duplicate clicks prohibited\\n");
''',
        '''  phase_ = kConfirmSent;
  OpenOFCOnConfirmSent(state);
  write_log(true,
    "[DeepOFC FP0] Confirm sent once; duplicate clicks prohibited\\n");
''')

    handle = r'''bool COFCRuntimeController::HandlePostConfirm(const COFCState &state) {
  // OPENOFC_PHASE_ENGINE_V4: after Confirm, animation frames have no authority.
  // The next normal round is committed only by the semantic marker requested
  // by the game: exactly three fully recognized Hero incoming cards.
  if (confirm_before_.players[confirm_before_.hero_chair].fantasy
      || confirm_before_.round_index == 4) {
    return true;
  }

  const int expected_round = confirm_before_.round_index + 1;
  if (!state.valid) return true;
  if (state.round_index < expected_round) {
    write_log(true,
      "[OpenOFC FLOW] phase=WAIT_NEXT_3 expected_round=%d observed_round=%d incoming=%d animation_ignored=1\n",
      expected_round, state.round_index, state.hero_incoming_count);
    return true;
  }
  if (state.round_index > expected_round) {
    Block("semantic round marker skipped expected round");
    return false;
  }
  if (state.hero_incoming_count != 3
      || !state.action_required || !state.hero_can_prepare) {
    write_log(true,
      "[OpenOFC FLOW] phase=WAIT_NEXT_3 expected_round=%d observed_round=%d incoming=%d prepare=%d action_required=%d\n",
      expected_round, state.round_index, state.hero_incoming_count,
      state.hero_can_prepare ? 1 : 0, state.action_required ? 1 : 0);
    return true;
  }

  write_log(true,
    "[OpenOFC FLOW] marker=ROUND_READY round=%d incoming=3 source=SEMANTIC_EDGE\n",
    state.round_index);
  orchestrator_.ResetForKnownNewHand();
  plan_.Reset();
  confirm_before_.Reset();
  pending_before_drag_ = 0;
  pending_signature_before_drag_.clear();
  drag_wait_cycles_ = 0;
  drag_retry_count_ = 0;
  phase_ = kIdle;
  g_openofc_flow_phase = kOpenOFCFlowRoundActive;
  g_openofc_expected_round = state.round_index;
  return StartDecision(state, *p_table_state->OFCVisualObservation());
}

'''
    regex_once(
        rel,
        r'''bool COFCRuntimeController::HandlePostConfirm\(const COFCState &state\) \{.*?\n\}\n\n(?=void COFCRuntimeController::Tick)''',
        handle)

    tick = r'''void COFCRuntimeController::Tick(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  OpenOFCUpdateStopRequest();

  write_log(true,
    "[DeepOFC TICK] phase=%d flow=%s state_valid=%d raw_valid=%d actor=%d hero=%d "
    "round=%d prepare=%d confirm=%d action_required=%d pending=%d\n",
    static_cast<int>(phase_), OpenOFCFlowName(g_openofc_flow_phase),
    state.valid ? 1 : 0, observation.valid ? 1 : 0,
    state.acting_chair, state.hero_chair, state.round_index,
    state.hero_can_prepare ? 1 : 0, state.hero_can_confirm ? 1 : 0,
    state.action_required ? 1 : 0, PendingCount(state));

  // Result/Fantasy markers are deliberately processed before raw/canonical
  // validity. Scoring animations routinely make card slots unreadable.
  if (OpenOFCObserveResultAndMaybeClose(observation)) {
    if (observation.result_screen_visible) return;
  }

  if (phase_ == kReplayProbeComplete) return;

  // Confirm is a phase boundary. While waiting for the next 3-card semantic
  // marker, rejected/partial animation frames are expected and ignored.
  if (phase_ == kConfirmSent) {
    if (confirm_before_.players[confirm_before_.hero_chair].fantasy
        || confirm_before_.round_index == 4) {
      if (state.valid && observation.valid && IsKnownNewHand(state)) {
        ResetForKnownNewHand(state);
      } else {
        write_log(true,
          "[OpenOFC FLOW] phase=WAIT_RESULT animation_or_result_pending=1 raw_valid=%d state_valid=%d\n",
          observation.valid ? 1 : 0, state.valid ? 1 : 0);
        return;
      }
    } else {
      if (!state.valid || !observation.valid) {
        write_log(true,
          "[OpenOFC FLOW] phase=WAIT_NEXT_3 expected_round=%d raw_valid=%d state_valid=%d animation_ignored=1\n",
          g_openofc_expected_round, observation.valid ? 1 : 0,
          state.valid ? 1 : 0);
        return;
      }
      HandlePostConfirm(state);
      return;
    }
  }

  if (!state.valid || !observation.valid) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\n");
    return;
  }

  if (IsKnownNewHand(state)) {
    ResetForKnownNewHand(state);
    g_openofc_flow_phase = kOpenOFCFlowRoundActive;
    g_openofc_expected_round = state.round_index;
    write_log(true,
      "[OpenOFC FLOW] marker=ROUND_READY round=%d incoming=%d source=NEW_HAND_EDGE\n",
      state.round_index, state.hero_incoming_count);
  }

  if (phase_ == kBlocked) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=RUNTIME_BLOCKED\n");
    return;
  }

  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=WAITING_TURN actor=%d hero=%d prepare=%d\n",
      state.acting_chair, state.hero_chair,
      state.hero_can_prepare ? 1 : 0);
    return;
  }

  if (phase_ == kIdle) {
    if (!OpenOFCNormalDecisionReady(state)) {
      write_log(true,
        "[OpenOFC FLOW] marker=NOT_READY round=%d incoming=%d expected=%d animation_ignored=1\n",
        state.round_index, state.hero_incoming_count,
        state.round_index == 0 ? 5 : 3);
      return;
    }
    if (hand_signature_.empty()) hand_signature_ = IncomingSignature(state);
    g_openofc_flow_phase = kOpenOFCFlowRoundActive;
    g_openofc_expected_round = state.round_index;
    StartDecision(state, observation);
    return;
  }

  if (phase_ == kArranging) AdvanceArrangement(state, observation);
}
'''
    regex_once(
        rel,
        r'''void COFCRuntimeController::Tick\(\n    const COFCState &state,\n    const COFCVisualObservation &observation\) \{.*?\n\}\s*$''',
        tick)


def patch_contract_v4():
    replace_once(
        "OpenHoldem/CHeartbeatThread.cpp",
        "const int kOpenOFCContractVersion = 3;\n",
        "const int kOpenOFCContractVersion = 4;\n")


def main():
    patch_visual_phase_contract()
    patch_scraper_phase_markers()
    patch_runtime_phase_engine()
    patch_contract_v4()
    print("OpenOFC phase/session flow v4 repair applied successfully")


if __name__ == "__main__":
    main()
