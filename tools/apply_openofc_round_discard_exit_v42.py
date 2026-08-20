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


def patch_round_inference():
    rel = "OpenHoldem/COFCScraper.cpp"
    pattern = r'''  const int total_dealt = obs->players\[hero_chair\]\.visual_board\.CountKnownCards\(\)\n    \+ obs->hero_loose_count \+ obs->hero_discard_tracker_count;\n  switch \(total_dealt\) \{.*?\n  \}\n'''
    replacement = r'''  // OPENOFC_ROUND_FROM_BOARD_AND_CURRENT_V42: historical discard OCR is
  // diagnostic only. A single old discard glyph must never prevent a future
  // round from becoming actionable. During a normal OFC placement, moving a
  // current card from the loose strip into a row preserves board+loose total:
  //   R0=5, R1=8, R2=10, R3=12, R4=14.
  const int hero_board_known =
    obs->players[hero_chair].visual_board.CountKnownCards();
  const int board_plus_current = hero_board_known + obs->hero_loose_count;
  switch (board_plus_current) {
    case 5: obs->round_index = 0; break;
    case 8: obs->round_index = 1; break;
    case 10: obs->round_index = 2; break;
    case 12: obs->round_index = 3; break;
    case 14: obs->round_index = 4; break;
    default:
      write_log(true,
        "[OpenOFC ROUND] state=TRANSITION board=%d loose=%d tracker=%d sum=%d action=WAIT\n",
        hero_board_known, obs->hero_loose_count,
        obs->hero_discard_tracker_count, board_plus_current);
      return false;
  }
  write_log(true,
    "[OpenOFC ROUND] source=BOARD_PLUS_CURRENT board=%d loose=%d tracker=%d round=%d\n",
    hero_board_known, obs->hero_loose_count,
    obs->hero_discard_tracker_count, obs->round_index);
'''
    regex_once(rel, pattern, replacement)


def patch_derived_discard_history():
    rel = "OpenHoldem/COFCReconstructor.cpp"

    replace_once(
        rel,
        '''  COFCPlayerBoard hero_committed;
  hero_committed.Reset();

  if (previous == NULL || !previous->valid) {
''',
        '''  COFCPlayerBoard hero_committed;
  hero_committed.Reset();

  // OPENOFC_DERIVED_DISCARD_HISTORY_V42: canonical dead-card history is owned
  // by the state machine, not by repeated OCR of tiny historical discard
  // thumbnails. The tracker may corroborate history, but missing tracker glyphs
  // can never block a new round.
  set<int> canonical_discards;
  if (previous != NULL && previous->valid) {
    canonical_discards = CardArraySet(
      previous->hero_discards, previous->hero_discard_count);
  }

  if (previous == NULL || !previous->valid) {
''')

    pattern = r'''      set<int> old_discards = CardArraySet\(previous->hero_discards, previous->hero_discard_count\);\n      set<int> new_tracker = CardArraySet\(\n        observation.hero_discard_tracker, observation.hero_discard_tracker_count\);\n      if \(!IsSubset\(old_discards, new_tracker\)\) \{.*?\n      if \(static_cast<int>\(committed_from_prior\.size\(\)\) != expected_commit_count\) \{.*?\n      \}\n'''
    replacement = r'''      set<int> prior_incoming =
        CardArraySet(previous->hero_incoming, previous->hero_incoming_count);
      if (prior_incoming.empty()) {
        return Fail(out, error, "cannot advance round without previous Hero incoming cards");
      }

      // The game itself proves which previous incoming cards were committed:
      // committed cards are now visible in Hero rows; the one absent card from
      // R1..R4 is the discard. This is stronger than re-reading discard OCR.
      set<int> committed_from_prior;
      for (set<int>::const_iterator it = prior_incoming.begin();
           it != prior_incoming.end(); ++it) {
        EOFCRow visible_row = kOFCRowUndefined;
        if (FindUniqueVisualRow(hero_visual, *it, &visible_row)) {
          committed_from_prior.insert(*it);
        }
      }
      set<int> discard_delta = Difference(prior_incoming, committed_from_prior);
      const int expected_commit_count = previous->round_index == 0 ? 5 : 2;
      const int expected_discard_count = previous->round_index == 0 ? 0 : 1;
      if (static_cast<int>(committed_from_prior.size()) != expected_commit_count
          || static_cast<int>(discard_delta.size()) != expected_discard_count) {
        ostringstream oss;
        oss << "round transition visibility proof failed: previous_round="
            << previous->round_index
            << " committed=" << committed_from_prior.size()
            << "/" << expected_commit_count
            << " discarded=" << discard_delta.size()
            << "/" << expected_discard_count;
        return Fail(out, error, oss.str());
      }
      canonical_discards.insert(discard_delta.begin(), discard_delta.end());

      // Tracker identities are optional corroboration only. Log missing or
      // extra recognition for calibration work, but never let it gate play.
      const set<int> tracker_seen = CardArraySet(
        observation.hero_discard_tracker, observation.hero_discard_tracker_count);
      int tracker_extra = 0;
      for (set<int>::const_iterator it = tracker_seen.begin();
           it != tracker_seen.end(); ++it) {
        if (canonical_discards.find(*it) == canonical_discards.end()) ++tracker_extra;
      }
#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
      const int derived_value = discard_delta.empty() ? -1 : *discard_delta.begin();
      write_log(true,
        "[OpenOFC DISCARD] source=DERIVED_FROM_PRIOR_INCOMING previous_round=%d derived=%d tracker_seen=%d tracker_extra=%d canonical=%d\n",
        previous->round_index, derived_value,
        static_cast<int>(tracker_seen.size()), tracker_extra,
        static_cast<int>(canonical_discards.size()));
#endif
'''
    regex_once(rel, pattern, replacement)

    replace_once(
        rel,
        '''  set<int> discards = CardArraySet(
    observation.hero_discard_tracker, observation.hero_discard_tracker_count);
  if (static_cast<int>(discards.size()) > kOFCMaxDiscards) {
''',
        '''  // Canonical discard history was derived at round boundaries above.
  // The visual tracker is intentionally not copied into state authority.
  set<int> discards = canonical_discards;
  if (static_cast<int>(discards.size()) > kOFCMaxDiscards) {
''')


def patch_leave_next_hand_schedule():
    rel = "OpenHoldem/COFCRuntimeController.cpp"

    replace_once(
        rel,
        '''bool g_openofc_close_sent = false;
time_t g_openofc_stop_deadline = 0;
''',
        '''bool g_openofc_close_sent = false;
bool g_openofc_leave_next_hand_sent = false;
time_t g_openofc_stop_deadline = 0;
''')

    # Treat -1 as the clean TableMap sentinel meaning "no scheduled exit".
    replace_once(
        rel,
        '''  const int hhmm = p_tablemap->GetTMSymbol("openofc_stop_local_hhmm", -1);
  const int hh = hhmm / 100;
  const int mm = hhmm % 100;
  if (hhmm < 0 || hh < 0 || hh > 23 || mm < 0 || mm > 59) {
''',
        '''  const int hhmm = p_tablemap->GetTMSymbol("openofc_stop_local_hhmm", -1);
  if (hhmm < 0) {
    write_log(true, "[OpenOFC SESSION] stop_schedule=DISABLED hhmm=%d\\n", hhmm);
    return;
  }
  const int hh = hhmm / 100;
  const int mm = hhmm % 100;
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) {
''')

    replace_once(
        rel,
        '''    write_log(true,
      "[OpenOFC SESSION] stop_requested=1 policy=FINISH_MATCH_CHAIN\\n");
  }
}

bool OpenOFCObserveResultAndMaybeClose(
''',
        '''    write_log(true,
      "[OpenOFC SESSION] stop_requested=1 policy=LEAVE_NEXT_HAND\\n");
  }
}

bool OpenOFCRequestLeaveNextHand() {
  if (g_openofc_leave_next_hand_sent) return true;
  if (p_casino_interface == NULL || p_tablemap == NULL) return false;
  RECT menu_rect, leave_rect;
  if (!ReadRegion("ofc_menu_button", &menu_rect)
      || !ReadRegion("ofc_leave_next_hand_menu_item", &leave_rect)) {
    write_log(k_always_log_errors,
      "[OpenOFC SESSION] leave_next_hand=0 reason=MISSING_TABLEMAP_REGIONS\\n");
    return false;
  }
  if (!p_casino_interface->ClickRectSafely(menu_rect)) {
    write_log(k_always_log_errors,
      "[OpenOFC SESSION] leave_next_hand=0 stage=OPEN_MENU result=FAILED\\n");
    return false;
  }
  Sleep(220);
  if (!p_casino_interface->ClickRectSafely(leave_rect)) {
    write_log(k_always_log_errors,
      "[OpenOFC SESSION] leave_next_hand=0 stage=SELECT_ITEM result=FAILED\\n");
    return false;
  }
  g_openofc_leave_next_hand_sent = true;
  write_log(true,
    "[OpenOFC SESSION] leave_next_hand_requested=1 mode=KKPOKER_MENU_ONE_SHOT\\n");
  return true;
}

bool OpenOFCObserveResultAndMaybeClose(
''')

    # The client now owns the actual end-of-hand departure after Leave Next Hand.
    pattern = r'''  if \(g_openofc_stop_requested && !g_openofc_close_sent\) \{.*?\n  \}\n  return true;\n}\n\nvoid OpenOFCOnConfirmSent'''
    replacement = r'''  if (g_openofc_stop_requested) {
    write_log(true,
      "[OpenOFC SESSION] result_observed_after_leave_next_hand=%d client_exit_owned=1\n",
      g_openofc_leave_next_hand_sent ? 1 : 0);
  }
  return true;
}

void OpenOFCOnConfirmSent'''
    regex_once(rel, pattern, replacement)

    # Arm the client-side leave request only when no drag transaction is active.
    replace_once(
        rel,
        '''  OpenOFCUpdateStopRequest();

  write_log(true,
''',
        '''  OpenOFCUpdateStopRequest();
  if (g_openofc_stop_requested && !g_openofc_leave_next_hand_sent
      && phase_ != kArranging) {
    if (!OpenOFCRequestLeaveNextHand()) {
      write_log(true,
        "[OpenOFC SESSION] leave_next_hand_retry=1 phase=%d\\n",
        static_cast<int>(phase_));
    }
  }

  write_log(true,
''')


def patch_stale_v3_comment():
    # Keep the repository-level build patch documentation aligned with v4.2.
    rel = "tools/apply_openofc_normal_flow_v3.py"
    path, text, eol, bom = read_source(rel)
    old = "exact 5/3 incoming-card and 5/8/11/14/17\n        // total-dealt contracts"
    if old in text:
        text = text.replace(
            old,
            "exact 5/3 current-incoming-card completeness and canonical\n        // state-transition contracts",
            1,
        )
        write_source(path, text, eol, bom)
        print(f"patched {rel}")


def selftest_contract_model():
    # Deterministic model of the two field regressions fixed here.
    round_cases = {
        (5, 0): 0,
        (5, 3): 1,
        (7, 3): 2,
        (9, 3): 3,
        (11, 3): 4,
    }
    mapping = {5: 0, 8: 1, 10: 2, 12: 3, 14: 4}
    for (board, loose), expected in round_cases.items():
        got = mapping.get(board + loose)
        if got != expected:
            raise RuntimeError(
                f"round model failed board={board} loose={loose}: {got} != {expected}"
            )

    # R2 -> R3 field case: previous incoming was 3h/Qh/8c. 3h and Qh
    # are visibly committed, while 8c is the derived discard even if the tiny
    # historical tracker cannot recognize its suit.
    previous_incoming = {1, 10, 32}
    visible_committed = {1, 10}
    derived = previous_incoming - visible_committed
    if derived != {32}:
        raise RuntimeError(f"derived discard model failed: {derived}")
    print("OpenOFC v4.2 deterministic contract model: PASS")


def main():
    selftest_contract_model()
    patch_round_inference()
    patch_derived_discard_history()
    patch_leave_next_hand_schedule()
    patch_stale_v3_comment()
    print("OpenOFC phase-flow v4.2 round/discard/Leave-Next-Hand repair applied")


if __name__ == "__main__":
    main()
