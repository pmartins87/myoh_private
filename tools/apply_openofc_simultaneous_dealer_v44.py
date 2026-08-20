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
        raise RuntimeError(
            f"{rel}: regex expected one target, got {count}: {pattern[:120]}"
        )
    write_source(path, new, eol, bom)
    print(f"patched {rel}")


def patch_turn_semantics_out_of_normal_authority():
    rel = "OpenHoldem/COFCScraper.cpp"

    # This is the exact block emitted earlier by apply_openofc_log248_repair.py.
    # Replace only this block. Do not span forward to another semantic marker,
    # because later phase/round code must remain byte-for-byte intact.
    old = '''  int turn_flag_count = 0;
  int turn_flag_chair = -1;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool value = false;
    region.Format("ofc_p%d_turn", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) {
      turn_flag_chair = p;
      ++turn_flag_count;
    }
  }

  if (obs->confirm_visible) {
    // The visible Hero Confirm is the strongest available proof that the Hero
    // may arrange/submit this OFC decision, regardless of opponent timer UI.
    obs->acting_chair = hero_chair;
    write_log(true,
      "[OpenOFC AUTHORITY] hero_actionable=1 source=CONFIRM_VISIBLE raw_turn_flags=%d raw_turn_chair=%d\\n",
      turn_flag_count, turn_flag_chair);
  } else if (turn_flag_count == 1) {
    obs->acting_chair = turn_flag_chair;
  } else if (player_count == 2 && turn_flag_count == 0) {
    // HU wait-state fallback: when Hero has no Confirm and no calibrated turn
    // marker is lit, the only safe canonical actor is the other chair. This
    // keeps post-Confirm handoff observable without authorizing Hero input.
    obs->acting_chair = 1 - hero_chair;
    write_log(true,
      "[OpenOFC AUTHORITY] hero_actionable=0 source=HU_WAIT_INFERENCE raw_turn_flags=0\\n");
  } else {
    write_log(k_always_log_errors,
      "[DeepOFC] Ambiguous normal OFC action authority: confirm=%d turn_flags=%d\\n",
      obs->confirm_visible ? 1 : 0, turn_flag_count);
    return false;
  }
'''
    new = '''  // OPENOFC_TURN_SEMANTICS_DISABLED_V44: normal OFC does not have an
  // exclusive per-player action turn for card arrangement. If Hero has current
  // cards, Hero may arrange immediately, including while the opponent/dealer
  // sequencing UI is still running. Keep actor=Hero only as a compatibility
  // placeholder for old state/debug fields; it has no authority semantics.
  obs->acting_chair = hero_chair;
  write_log(true,
    "[OpenOFC AUTHORITY] prepare_source=CARDS_AVAILABLE turn_semantics=IGNORED confirm_visible=%d\\n",
    obs->confirm_visible ? 1 : 0);
'''
    replace_once(rel, old, new)


def patch_prepare_vs_finalize_runtime():
    rel = "OpenHoldem/COFCRuntimeController.cpp"

    replace_once(
        rel,
        '''bool OpenOFCNormalDecisionReady(const COFCState &state) {
  if (!state.valid || state.hero_chair < 0
      || state.hero_chair >= state.player_count) return false;
  if (state.players[state.hero_chair].fantasy) return true;
  if (state.round_index < 0 || state.round_index > 4) return false;
  const int expected_incoming = state.round_index == 0 ? 5 : 3;
  return state.hero_incoming_count == expected_incoming
    && state.action_required && state.hero_can_prepare;
}
''',
        '''bool OpenOFCNormalDecisionReady(const COFCState &state) {
  if (!state.valid || state.hero_chair < 0
      || state.hero_chair >= state.player_count) return false;
  if (state.players[state.hero_chair].fantasy) return true;
  if (state.round_index < 0 || state.round_index > 4) return false;
  const int expected_incoming = state.round_index == 0 ? 5 : 3;
  // OPENOFC_PREPARE_ON_CARDS_V44: readiness to ARRANGE is independent of
  // readiness to CONFIRM. A dealer with timer=0 must pre-arrange immediately.
  return state.hero_incoming_count == expected_incoming
    && state.hero_can_prepare;
}
''')

    replace_once(
        rel,
        '''  if (state.hero_incoming_count != 3
      || !state.action_required || !state.hero_can_prepare) {
    write_log(true,
      "[OpenOFC FLOW] phase=WAIT_NEXT_3 expected_round=%d observed_round=%d incoming=%d prepare=%d action_required=%d\\n",
      expected_round, state.round_index, state.hero_incoming_count,
      state.hero_can_prepare ? 1 : 0, state.action_required ? 1 : 0);
    return true;
  }
''',
        '''  if (state.hero_incoming_count != 3 || !state.hero_can_prepare) {
    write_log(true,
      "[OpenOFC FLOW] phase=WAIT_NEXT_3 expected_round=%d observed_round=%d incoming=%d prepare=%d finalizable=%d timer=%d\\n",
      expected_round, state.round_index, state.hero_incoming_count,
      state.hero_can_prepare ? 1 : 0,
      state.decision_finalizable ? 1 : 0,
      state.hero_timer_active ? 1 : 0);
    return true;
  }
''')

    replace_once(
        rel,
        '''  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=WAITING_TURN actor=%d hero=%d prepare=%d\\n",
      state.acting_chair, state.hero_chair,
      state.hero_can_prepare ? 1 : 0);
    return;
  }
''',
        '''  if (!state.hero_can_prepare) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=NO_PREPARABLE_CARDS actor=%d hero=%d prepare=0\\n",
      state.acting_chair, state.hero_chair);
    return;
  }
''')

    # v4 rewrote Tick after v2 and accidentally removed v2's dealer
    # kWaitingFinalInfo branch. Restore it: pre-arranged dealer waits without
    # further drag, then re-solves once timer/final opponent information is live.
    replace_once(
        rel,
        '''  if (phase_ == kIdle) {
    if (!OpenOFCNormalDecisionReady(state)) {
''',
        '''  if (phase_ == kWaitingFinalInfo) {
    if (!state.decision_finalizable) {
      write_log(true,
        "[OpenOFC PROVISIONAL] waiting=1 dealer=%d hero=%d timer=%d confirm=HELD\\n",
        state.dealer_chair, state.hero_chair,
        state.hero_timer_active ? 1 : 0);
      return;
    }
    provisional_ = false;
    phase_ = kIdle;
    write_log(true,
      "[OpenOFC PROVISIONAL] opponent_final_info=1 reanalyze=1 timer=%d\\n",
      state.hero_timer_active ? 1 : 0);
    StartDecision(state, observation);
    return;
  }

  if (phase_ == kIdle) {
    if (!OpenOFCNormalDecisionReady(state)) {
''')


def patch_new_hand_recovery_before_wait_phase():
    rel = "OpenHoldem/COFCRuntimeController.cpp"

    # A prior round can disappear because the client timed out before our
    # finalization gate. A fully valid new R0 is stronger evidence than stale
    # WAIT_NEXT_3 bookkeeping. Process this edge before the post-Confirm wait
    # branch so one missed R4 can never poison all later matches.
    replace_once(
        rel,
        '''  if (phase_ == kReplayProbeComplete) return;

  // Confirm is a phase boundary. While waiting for the next 3-card semantic
''',
        '''  if (phase_ == kReplayProbeComplete) return;

  // OPENOFC_NEW_HAND_RECOVERY_V44: a fresh valid opening hand supersedes any
  // stale WAIT_NEXT_3/WAIT_RESULT bookkeeping from the previous match.
  if (state.valid && observation.valid && IsKnownNewHand(state)) {
    ResetForKnownNewHand(state);
    g_openofc_flow_phase = kOpenOFCFlowRoundActive;
    g_openofc_expected_round = state.round_index;
    write_log(true,
      "[OpenOFC FLOW] marker=ROUND_READY round=%d incoming=%d source=NEW_HAND_RECOVERY_EDGE\\n",
      state.round_index, state.hero_incoming_count);
  }

  // Confirm is a phase boundary. While waiting for the next 3-card semantic
''')


def main():
    patch_turn_semantics_out_of_normal_authority()
    patch_prepare_vs_finalize_runtime()
    patch_new_hand_recovery_before_wait_phase()
    print("OpenOFC simultaneous dealer v4.4 repair applied successfully")


if __name__ == "__main__":
    main()
