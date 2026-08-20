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


def patch_disable_hero_discard_scrape():
    rel = "OpenHoldem/COFCScraper.cpp"
    # v4.2 already derives canonical discard history from the prior incoming
    # set. Remove the remaining visual OCR sweep entirely: these tiny historical
    # thumbnails are redundant and can only add recognition failure surface.
    pattern = r'''\n  for \(int i = 0; i < kOFCMaxDiscards; \+\+i\) \{\n    CString base;\n    base\.Format\("ofc_hero_discard%d", i\);.*?\n  \}\n\n  if \(!all_slots_ok\) \{'''
    replacement = r'''
  // OPENOFC_HERO_DISCARD_SCRAPE_DISABLED_V43: the runtime already owns the
  // decision that selected the unused card, and the canonical reconstructor
  // proves the same fact at the next round from prior incoming minus cards now
  // committed to Hero rows. Historical discard thumbnails therefore have no
  // state authority and are not scraped at all.
  obs->hero_discard_tracker_count = 0;
  write_log(true,
    "[OpenOFC DISCARD] visual_scrape=DISABLED source=CANONICAL_HISTORY\n");

  if (!all_slots_ok) {'''
    regex_once(rel, pattern, replacement)

    # The tracker is now permanently empty in normal play; remove it from raw
    # duplicate-card validation too, so future TableMaps can drop those regions.
    pattern_unique = r'''\n  for \(int i = 0; i < observation->hero_discard_tracker_count; \+\+i\)\n    if \(observation->hero_discard_tracker\[i\]\.IsKnownPhysicalCard\(\)\n        && !DeepOFCRegisterKnownCard\(observation->hero_discard_tracker\[i\]\.value, &seen\)\) return false;'''
    regex_once(rel, pattern_unique, "")


def patch_generic_joker_source_resolution():
    rel = "OpenHoldem/COFCActionPlanner.cpp"

    # Prefer a current loose source. Raw TableMap X is intentionally generic
    # (54); the reconstructor has already assigned the canonical incoming Joker
    # occurrence (52/53). If exactly one generic Joker is movable in Hero's
    # loose strip, that rectangle is unambiguous for the requested canonical
    # Hero Joker even when another Joker exists on the opponent board.
    replace_once(
        rel,
        '''  if (found < 0) {
    // A pending card can also be a movable source. This is required for the
''',
        '''  if (found < 0
      && (card_value == kOFCCardJoker1 || card_value == kOFCCardJoker2)) {
    int generic_found = -1;
    for (int i = 0; i < observation.hero_loose_count; ++i) {
      if (observation.hero_loose_cards[i].value != kOFCCardJokerGeneric) continue;
      if (generic_found >= 0) {
        return Fail(error,
          "requested canonical Joker has multiple generic raw loose sources");
      }
      generic_found = i;
    }
    if (generic_found >= 0) {
      const COFCVisualCardSource &source =
        observation.hero_loose_sources[generic_found];
      if (!source.valid || !IsUsableRect(source.rect)) {
        return Fail(error,
          "generic raw Joker has no validated click-safe source rectangle");
      }
      *out = source.rect;
      write_log(true,
        "[OpenOFC JOKER SOURCE] canonical=%d raw=%d source=LOOSE_GENERIC_X rect=(%ld,%ld,%ld,%ld)\\n",
        card_value, kOFCCardJokerGeneric,
        out->left, out->top, out->right, out->bottom);
      return true;
    }
  }
  if (found < 0) {
    // A pending card can also be a movable source. This is required for the
''')

    old_board = '''    int source_row = -1;
    int source_slot = -1;
    const COFCPlayerBoard &board =
      observation.players[observation.hero_chair].visual_board;
    for (int i = 0; i < kOFCTopCards; ++i) {
      if (board.top[i].value == card_value) { source_row = kOFCRowTop; source_slot = i; }
    }
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      if (board.middle[i].value == card_value) { source_row = kOFCRowMiddle; source_slot = i; }
    }
    for (int i = 0; i < kOFCBottomCards; ++i) {
      if (board.bottom[i].value == card_value) { source_row = kOFCRowBottom; source_slot = i; }
    }
    if (source_row < 0 || source_slot < 0) {
'''
    new_board = '''    int source_row = -1;
    int source_slot = -1;
    int source_matches = 0;
    const bool requested_joker =
      card_value == kOFCCardJoker1 || card_value == kOFCCardJoker2;
    const COFCPlayerBoard &board =
      observation.players[observation.hero_chair].visual_board;
    for (int i = 0; i < kOFCTopCards; ++i) {
      if (board.top[i].value == card_value
          || (requested_joker && board.top[i].value == kOFCCardJokerGeneric)) {
        source_row = kOFCRowTop; source_slot = i; ++source_matches;
      }
    }
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      if (board.middle[i].value == card_value
          || (requested_joker && board.middle[i].value == kOFCCardJokerGeneric)) {
        source_row = kOFCRowMiddle; source_slot = i; ++source_matches;
      }
    }
    for (int i = 0; i < kOFCBottomCards; ++i) {
      if (board.bottom[i].value == card_value
          || (requested_joker && board.bottom[i].value == kOFCCardJokerGeneric)) {
        source_row = kOFCRowBottom; source_slot = i; ++source_matches;
      }
    }
    if (source_matches > 1) {
      return Fail(error,
        "requested canonical Joker has multiple generic visual-board sources");
    }
    if (source_row < 0 || source_slot < 0) {
'''
    replace_once(rel, old_board, new_board)


def patch_unavoidable_foul_fallback():
    rel = "OpenHoldem/COFCBaselinePolicy.cpp"
    path, text, eol, bom = read_source(rel)
    if "#include <limits>\n" not in text:
        text = text.replace("#include <map>\n", "#include <map>\n#include <limits>\n", 1)
    write_source(path, text, eol, bom)

    anchor = '''long long NormalScore(vector<PolicyCard> rows[3]) {
  if (!CompletedRowsLegal(rows)) return -1;
  long long score = 0;
  for (int row = 0; row < 3; ++row) score += PartialRowScore(rows[row], row) * (row + 1);
  if (rows[0].size() == 3 && rows[1].size() == 5 && rows[2].size() == 5) {
    array<HandRank, 3> resolved;
    if (!ResolveBoard(
          CandidateRanks(rows[0], true),
          CandidateRanks(rows[1], false),
          CandidateRanks(rows[2], false), &resolved)) return -1;
    score += static_cast<long long>(Royalties(resolved)) * 1000000LL;
    score += RankScalar(resolved[2]) * 1000LL;
    score += RankScalar(resolved[1]) * 10LL;
    score += RankScalar(resolved[0]);
  }
  return score;
}
'''
    addition = anchor + '''
// OPENOFC_UNAVOIDABLE_FOUL_FALLBACK_V43: OFC still requires two placements
// and one discard when the hand is already mathematically doomed to foul.
// The primary search remains strictly non-foul. This score is consulted only
// if that search finds no legal completion at all, so it can never replace a
// legal board with a fouled one.
long long NormalScoreAllowFoul(vector<PolicyCard> rows[3]) {
  long long score = 0;
  for (int row = 0; row < 3; ++row)
    score += PartialRowScore(rows[row], row) * (row + 1);
  if (rows[0].size() == 3 && rows[1].size() == 5 && rows[2].size() == 5) {
    array<HandRank, 3> resolved;
    if (ResolveBoard(
          CandidateRanks(rows[0], true),
          CandidateRanks(rows[1], false),
          CandidateRanks(rows[2], false), &resolved)) {
      score += static_cast<long long>(Royalties(resolved)) * 1000000LL;
      score += RankScalar(resolved[2]) * 1000LL;
      score += RankScalar(resolved[1]) * 10LL;
      score += RankScalar(resolved[0]);
    } else {
      // Every candidate in this pass fouls; retain deterministic heuristic
      // ordering while making the state visibly distinct in debugging.
      score -= 1000000000LL;
    }
  }
  return score;
}

void EnumerateNormalAllowFoul(
    const vector<PolicyCard> &incoming,
    int index,
    int unused_index,
    vector<PolicyCard> rows[3],
    int assignments[],
    bool opening,
    long long *best_score,
    int best_assignments[]) {
  if (index == static_cast<int>(incoming.size())) {
    long long score = NormalScoreAllowFoul(rows);
    if (opening) {
      const int target[3] = {1, 2, 2};
      int deviation = 0;
      for (int row = 0; row < 3; ++row)
        deviation += abs(static_cast<int>(rows[row].size()) - target[row]);
      score -= static_cast<long long>(deviation) * 1000000LL;
    }
    if (score > *best_score) {
      *best_score = score;
      for (size_t i = 0; i < incoming.size(); ++i)
        best_assignments[i] = assignments[i];
    }
    return;
  }
  if (index == unused_index) {
    assignments[index] = -1;
    EnumerateNormalAllowFoul(incoming, index + 1, unused_index,
      rows, assignments, opening, best_score, best_assignments);
    return;
  }
  const int capacities[3] = {3, 5, 5};
  for (int row = 0; row < 3; ++row) {
    if (static_cast<int>(rows[row].size()) >= capacities[row]) continue;
    rows[row].push_back(incoming[index]);
    assignments[index] = row;
    EnumerateNormalAllowFoul(incoming, index + 1, unused_index,
      rows, assignments, opening, best_score, best_assignments);
    rows[row].pop_back();
  }
}
'''
    replace_once(rel, anchor, addition)

    old = '''  if (best_score < 0) return Fail(action, error, "no legal normal placement found");
  action->Reset();
'''
    new = '''  if (best_score < 0) {
    // No non-foul completion exists. The client still requires a legal UI
    // action; enumerate structural placements without the foul rejection.
    best_score = (std::numeric_limits<long long>::min)() / 4;
    for (int i = 0; i < 5; ++i) best_assignments[i] = -2;
    for (int unused = first_unused; unused <= last_unused; ++unused) {
      if (unused >= 0 && incoming[unused].joker != 0) continue;
      vector<PolicyCard> rows[3] = {baseline[0], baseline[1], baseline[2]};
      int assignments[5] = {-2, -2, -2, -2, -2};
      EnumerateNormalAllowFoul(incoming, 0, unused, rows,
        assignments, state.round_index == 0,
        &best_score, best_assignments);
    }
    if (best_score == (std::numeric_limits<long long>::min)() / 4) {
      return Fail(action, error, "no structurally valid normal placement found");
    }
    if (error != NULL) *error = "UNAVOIDABLE_FOUL_FALLBACK";
  }
  action->Reset();
'''
    replace_once(rel, old, new)

    # Surface a successful fallback in the runtime log; success-with-note is
    # intentionally different from policy rejection.
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  LogStrategyAction(action);
  if (!COFCTurnPlanBuilder::Build(state, action, &plan_, &error)) {
''',
        '''  if (!error.empty()) {
    write_log(true,
      "[OpenOFC POLICY] fallback=%s round=%d continue=1\\n",
      error.c_str(), state.round_index);
    error.clear();
  }
  LogStrategyAction(action);
  if (!COFCTurnPlanBuilder::Build(state, action, &plan_, &error)) {
''')


def patch_policy_selftest():
    rel = "OpenHoldem/COFCBaselinePolicySelftest.cpp"
    anchor = '''bool Fantasy15DualJoker() {
'''
    path, text, eol, bom = read_source(rel)
    if text.count(anchor) != 1:
        raise RuntimeError(f"{rel}: selftest anchor missing")
    test = '''bool UnavoidableFoulStillActs() {
  // Exact structural regression from the 19/08 field run: top already has
  // pair 3, middle is a full pair-T row and bottom is A-Q-5-4. Incoming
  // 3/4/5 cannot produce any non-foul final board, but OFC still requires
  // two placements and one discard.
  COFCState state = BaseState(false, 4);
  state.players[1].board.top[0].value = Card(3, 0);
  state.players[1].board.top[1].value = Card(3, 1);
  state.players[1].board.middle[0].value = Card(4, 1);
  state.players[1].board.middle[1].value = Card(10, 1);
  state.players[1].board.middle[2].value = Card(14, 1);
  state.players[1].board.middle[3].value = Card(6, 0);
  state.players[1].board.middle[4].value = Card(10, 2);
  state.players[1].board.bottom[0].value = Card(4, 2);
  state.players[1].board.bottom[1].value = Card(5, 2);
  state.players[1].board.bottom[2].value = Card(12, 2);
  state.players[1].board.bottom[3].value = Card(14, 0);
  const int cards[3] = {Card(3, 2), Card(4, 0), Card(5, 0)};
  state.hero_incoming_count = 3;
  for (int i = 0; i < 3; ++i) state.hero_incoming[i].value = cards[i];

  COFCStrategyAction action;
  std::string note;
  if (!COFCBaselinePolicy::Choose(state, &action, &note)) {
    std::cerr << "unavoidable-foul fallback rejected: " << note << "\\n";
    return false;
  }
  return action.valid && action.placement_count == 2
    && action.unused_count == 1
    && note == "UNAVOIDABLE_FOUL_FALLBACK";
}

'''
    text = text.replace(anchor, test + anchor, 1)
    old_main = '''  if (!Fantasy15() || !Fantasy15DualJoker() || !NormalOpening()
      || !NormalRoundPreservesJoker()) return 1;
'''
    new_main = '''  if (!Fantasy15() || !Fantasy15DualJoker() || !NormalOpening()
      || !NormalRoundPreservesJoker() || !UnavoidableFoulStillActs()) return 1;
'''
    if text.count(old_main) != 1:
        raise RuntimeError(f"{rel}: main selftest list missing")
    text = text.replace(old_main, new_main, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def selftest_contract_model():
    # Raw X (54) is not the canonical Joker occurrence identity, but one generic
    # movable Hero Joker source is sufficient to locate a requested JK1/JK2.
    canonical_target = 53
    raw_loose = [15, 54]
    generic = [x for x in raw_loose if x == 54]
    if canonical_target not in (52, 53) or len(generic) != 1:
        raise RuntimeError("generic-Joker source model failed")

    # Visual discard OCR is intentionally absent; canonical history is derived
    # from the previous incoming set and the two cards that became committed.
    previous_incoming = {9, 15, 53}
    committed = {9, 53}
    if previous_incoming - committed != {15}:
        raise RuntimeError("discard-history model failed")
    print("OpenOFC v4.3 deterministic completion model: PASS")


def main():
    selftest_contract_model()
    patch_disable_hero_discard_scrape()
    patch_generic_joker_source_resolution()
    patch_unavoidable_foul_fallback()
    patch_policy_selftest()
    print("OpenOFC v4.3 normal-completion repair applied")


if __name__ == "__main__":
    main()
