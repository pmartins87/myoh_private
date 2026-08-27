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
    output = text if eol == "\n" else text.replace("\n", "\r\n")
    data = output.encode("utf-8")
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


def patch_fantasy_single_delta_lineage() -> None:
    old = r'''        if (expected_arrangement.size() != static_cast<size_t>(occupied_hint)) {
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V552] lineage partition mismatch prior=%d occupied=%d loose=%d expected_arranged=%d terminal=0\n",
            static_cast<int>(original_labels.size()), occupied_hint,
            static_cast<int>(loose.size()), static_cast<int>(expected_arrangement.size()));
          return false;
        }
        if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
              _entire_window_cur, arrangement_rects, expected_arrangement,
              &occupied, &arrangement_cards, &recognition_error)) {
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V552] expected arrangement rejected count=%d error=%s terminal=0\n",
            text_count, recognition_error.c_str());
          return false;
        }
        loose_pre_recognized = true;
        write_log(true,
          "[OpenOFC FANTASY V552] count=%d score=%.3f identity=TABLEMAP_T7 occupied=%d\n",
          text_count, count_score, occupied_hint);
'''
    new = r'''        const int lineage_delta =
          static_cast<int>(expected_arrangement.size()) - occupied_hint;
        const bool exact_partition =
          original_labels.size() == loose.size() + occupied_hint;
        if (!exact_partition || lineage_delta < 0 || lineage_delta > 1) {
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V581] lineage partition rejected prior=%d occupied=%d "
            "loose=%d expected_arranged=%d delta=%d terminal=0\n",
            static_cast<int>(original_labels.size()), occupied_hint,
            static_cast<int>(loose.size()),
            static_cast<int>(expected_arrangement.size()), lineage_delta);
          return false;
        }
        if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
              _entire_window_cur, arrangement_rects, expected_arrangement,
              &occupied, &arrangement_cards, &recognition_error)) {
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V581] expected arrangement rejected count=%d error=%s terminal=0\n",
            text_count, recognition_error.c_str());
          return false;
        }

        if (lineage_delta == 1) {
          std::set<string> arranged_labels;
          for (size_t i = 0; i < arrangement_cards.size(); ++i) {
            if (i < occupied.size() && occupied[i]
                && arrangement_cards[i].valid) {
              arranged_labels.insert(arrangement_cards[i].PhysicalLabel());
            }
          }
          std::vector<string> missing_loose;
          for (size_t i = 0; i < expected_arrangement.size(); ++i) {
            if (arranged_labels.find(expected_arrangement[i])
                == arranged_labels.end()) {
              missing_loose.push_back(expected_arrangement[i]);
            }
          }
          const std::set<string> prior_set(
            original_labels.begin(), original_labels.end());
          std::vector<size_t> divergent_loose;
          for (size_t i = 0; i < loose.size(); ++i) {
            if (prior_set.find(loose[i].card.PhysicalLabel()) == prior_set.end())
              divergent_loose.push_back(i);
          }
          if (arranged_labels.size() != static_cast<size_t>(occupied_hint)
              || missing_loose.size() != 1 || divergent_loose.size() != 1
              || !card_from_label(
                   missing_loose[0], &loose[divergent_loose[0]].card)) {
            write_log(k_always_log_errors,
              "[OpenOFC FANTASY V581] single-delta proof rejected arranged=%d "
              "missing=%d divergent=%d terminal=0\n",
              static_cast<int>(arranged_labels.size()),
              static_cast<int>(missing_loose.size()),
              static_cast<int>(divergent_loose.size()));
            return false;
          }

          std::set<string> corrected_loose;
          for (size_t i = 0; i < loose.size(); ++i)
            corrected_loose.insert(loose[i].card.PhysicalLabel());
          std::set<string> expected_loose;
          for (size_t i = 0; i < original_labels.size(); ++i) {
            if (arranged_labels.find(original_labels[i]) == arranged_labels.end())
              expected_loose.insert(original_labels[i]);
          }
          if (corrected_loose.size() != loose.size()
              || corrected_loose != expected_loose) {
            write_log(k_always_log_errors,
              "[OpenOFC FANTASY V581] corrected lineage failed exact partition terminal=0\n");
            return false;
          }
          RequestOpenOFCReplayFrame("FANTASY_LINEAGE_SINGLE_DELTA_RECOVERED");
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V581] recovery=SINGLE_DELTA_EXACT card=%s "
            "source_index=%d occupied=%d loose=%d replay=1\n",
            missing_loose[0].c_str(),
            static_cast<int>(divergent_loose[0]), occupied_hint,
            static_cast<int>(loose.size()));
        }
        loose_pre_recognized = true;
        write_log(true,
          "[OpenOFC FANTASY V581] count=%d score=%.3f identity=TABLEMAP_T7 "
          "occupied=%d lineage_delta=%d\n",
          text_count, count_score, occupied_hint, lineage_delta);
'''
    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        old,
        new,
        "recover one divergent staged-Fantasy identity by exact lineage",
    )

    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '#include "COFCIdentityRecoveryCache.h"\n',
        '#include "COFCIdentityRecoveryCache.h"\n'
        '#include "CSymbolEngineReplayFrameController.h"\n',
        "make lineage recovery request a BMP+HTML replay",
    )


def patch_r4_safety_solver() -> None:
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.h",
        '''  bool exact_available;
  bool applied;
  int candidates;
  int legal_candidates;
''',
        '''  bool exact_available;
  bool opponent_terminal;
  bool applied;
  bool safety_override;
  bool baseline_foul;
  bool selected_foul;
  int candidates;
  int legal_candidates;
  int safe_candidates;
''',
        "extend exact R4 proof report",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.h",
        '''  // Evaluates every legal discard/placement at normal R4 against all complete,
  // visible opponents.  It replaces `baseline` only when the exact candidate
  // has no lower immediate score and no lower Fantasy tier, with at least one
  // strict improvement.  This Pareto gate introduces no guessed conversion
  // rate between current points and future Fantasy value.
''',
        '''  // Always evaluates all 27 Hero terminal assignments. A fouled baseline is
  // replaced by a non-fouled completion even when an earlier-acting Hero
  // cannot yet see the opponent's terminal board. When every opponent is
  // complete and visible, exact match points and Fantasy tier retain the
  // original Pareto-safe replacement contract. No hidden card is invented.
''',
        "document hidden-opponent non-foul safety",
    )

    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''  candidate->action = action;
  COFCPlayerBoard board = state.players[state.hero_chair].board;
  if (!ApplyAction(state, action, &board, error)) return false;
  if (!GlobalPhysicalCardsUnique(state, board))
    return Fail(error, "R4 exact state contains duplicate/unknown physical card");
  if (!COFCExactEvaluator::EvaluateBoard(board, &candidate->board, error))
    return false;
  candidate->points = 0;
  for (size_t i = 0; i < opponents.size(); ++i) {
''',
        '''  candidate->action = action;
  COFCPlayerBoard board = state.players[state.hero_chair].board;
  if (!ApplyAction(state, action, &board, error)) return false;
  if (!COFCExactEvaluator::EvaluateBoard(board, &candidate->board, error))
    return false;
  candidate->points = 0;
  if (opponents.empty()) return true;
  if (!GlobalPhysicalCardsUnique(state, board))
    return Fail(error, "R4 exact state contains duplicate/unknown physical card");
  for (size_t i = 0; i < opponents.size(); ++i) {
''',
        "evaluate Hero terminal safety without hidden opponent cards",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''bool BetterDominatingCandidate(
    const ExactCandidate &left,
    const ExactCandidate &right) {
  if (left.points != right.points) return left.points > right.points;
  if (left.board.fantasy_cards != right.board.fantasy_cards)
    return left.board.fantasy_cards > right.board.fantasy_cards;
  if (left.board.royalties != right.board.royalties)
    return left.board.royalties > right.board.royalties;
  return ActionLess(left.action, right.action);
}
''',
        '''bool BetterDominatingCandidate(
    const ExactCandidate &left,
    const ExactCandidate &right) {
  if (left.points != right.points) return left.points > right.points;
  if (left.board.fantasy_cards != right.board.fantasy_cards)
    return left.board.fantasy_cards > right.board.fantasy_cards;
  if (left.board.royalties != right.board.royalties)
    return left.board.royalties > right.board.royalties;
  return ActionLess(left.action, right.action);
}

int BaselineAgreement(
    const COFCStrategyAction &candidate,
    const COFCStrategyAction &baseline) {
  int agreement = candidate.unused_count == 1 && baseline.unused_count == 1
    && candidate.unused_cards[0] == baseline.unused_cards[0] ? 1 : 0;
  for (int i = 0; i < candidate.placement_count; ++i) {
    for (int j = 0; j < baseline.placement_count; ++j) {
      if (candidate.placements[i].card_value
            == baseline.placements[j].card_value
          && candidate.placements[i].row == baseline.placements[j].row) {
        ++agreement;
        break;
      }
    }
  }
  return agreement;
}

bool BetterSafetyCandidate(
    const ExactCandidate &left,
    const ExactCandidate &right,
    const COFCStrategyAction &baseline) {
  if (left.board.fantasy_cards != right.board.fantasy_cards)
    return left.board.fantasy_cards > right.board.fantasy_cards;
  if (left.board.royalties != right.board.royalties)
    return left.board.royalties > right.board.royalties;
  const int left_agreement = BaselineAgreement(left.action, baseline);
  const int right_agreement = BaselineAgreement(right.action, baseline);
  if (left_agreement != right_agreement) return left_agreement > right_agreement;
  return ActionLess(left.action, right.action);
}
''',
        "add deterministic non-foul safety selector",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''COFCR4ExactTeacherReport::COFCR4ExactTeacherReport()
    : exact_available(false), applied(false), candidates(0), legal_candidates(0),
      baseline_points(0), selected_points(0), baseline_fantasy_cards(0),
''',
        '''COFCR4ExactTeacherReport::COFCR4ExactTeacherReport()
    : exact_available(false), opponent_terminal(false), applied(false),
      safety_override(false), baseline_foul(false), selected_foul(false),
      candidates(0), legal_candidates(0), safe_candidates(0),
      baseline_points(0), selected_points(0), baseline_fantasy_cards(0),
''',
        "initialize exact R4 proof fields",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''  vector<COFCExactBoardResult> opponents;
  for (int p = 0; p < state.player_count; ++p) {
    if (p == state.hero_chair || !state.players[p].occupied
        || state.players[p].sitting_out) continue;
    if (state.players[p].board.CountKnownCards() != 13)
      return Fail(error, "exact R4 opponent terminal board is unavailable");
    COFCExactBoardResult opponent;
    if (!COFCExactEvaluator::EvaluateBoard(
          state.players[p].board, &opponent, error)) return false;
    opponents.push_back(opponent);
  }
  if (opponents.empty())
    return Fail(error, "exact R4 teacher requires at least one opponent");
''',
        '''  vector<COFCExactBoardResult> opponents;
  bool opponent_terminal = true;
  for (int p = 0; p < state.player_count; ++p) {
    if (p == state.hero_chair || !state.players[p].occupied
        || state.players[p].sitting_out) continue;
    if (state.players[p].board.CountKnownCards() != 13) {
      opponent_terminal = false;
      opponents.clear();
      break;
    }
    COFCExactBoardResult opponent;
    if (!COFCExactEvaluator::EvaluateBoard(
          state.players[p].board, &opponent, error)) return false;
    opponents.push_back(opponent);
  }
  if (opponents.empty()) opponent_terminal = false;
''',
        "keep exact Hero safety available before opponent terminal board",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''  report->exact_available = true;
  report->baseline_points = baseline_candidate.points;
''',
        '''  report->exact_available = true;
  report->opponent_terminal = opponent_terminal;
  report->baseline_foul = baseline_candidate.board.foul;
  report->selected_foul = baseline_candidate.board.foul;
  report->baseline_points = baseline_candidate.points;
''',
        "publish baseline foul proof",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''  vector<ExactCandidate> improving;
  const EOFCRow rows[3] = {kOFCRowTop, kOFCRowMiddle, kOFCRowBottom};
''',
        '''  vector<ExactCandidate> improving;
  vector<ExactCandidate> safe_completions;
  const EOFCRow rows[3] = {kOFCRowTop, kOFCRowMiddle, kOFCRowBottom};
''',
        "collect all non-foul R4 completions",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''        ++report->legal_candidates;
        const bool no_worse = candidate.points >= baseline_candidate.points
''',
        '''        ++report->legal_candidates;
        if (!candidate.board.foul) safe_completions.push_back(candidate);
        if (!opponent_terminal) continue;
        const bool no_worse = candidate.points >= baseline_candidate.points
''',
        "separate non-foul safety from exact opponent scoring",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''  }
  if (improving.empty()) return true;
  sort(improving.begin(), improving.end(), BetterDominatingCandidate);
''',
        '''  }
  report->safe_candidates = static_cast<int>(safe_completions.size());
  if (baseline_candidate.board.foul && !safe_completions.empty()) {
    if (opponent_terminal) {
      sort(safe_completions.begin(), safe_completions.end(),
        BetterDominatingCandidate);
    } else {
      sort(safe_completions.begin(), safe_completions.end(),
        [&](const ExactCandidate &left, const ExactCandidate &right) {
          return BetterSafetyCandidate(left, right, baseline);
        });
    }
    *selected = safe_completions[0].action;
    report->applied = true;
    report->safety_override = true;
    report->selected_foul = false;
    report->selected_points = safe_completions[0].points;
    report->selected_fantasy_cards = safe_completions[0].board.fantasy_cards;
    report->selected_royalties = safe_completions[0].board.royalties;
    return true;
  }
  if (!opponent_terminal) return true;
  if (improving.empty()) return true;
  sort(improving.begin(), improving.end(), BetterDominatingCandidate);
''',
        "override only a provably recoverable foul with hidden opponent",
    )
    replace_once(
        "OpenHoldem/COFCR4ExactTeacher.cpp",
        '''  report->applied = true;
  report->selected_points = improving[0].points;
''',
        '''  report->applied = true;
  report->selected_foul = improving[0].board.foul;
  report->selected_points = improving[0].points;
''',
        "publish selected foul state",
    )

    replace_once(
        "OpenHoldem/COFCExactEvaluatorSelftest.cpp",
        '''  state.round_index = 4;
  state.hero_can_prepare = true;
  state.players[0].occupied = true;
  state.players[1].occupied = true;

  COFCPlayerBoard &hero = state.players[0].board;
''',
        '''  state.round_index = 4;
  state.fantasy_card_count = 0;
  state.hero_can_prepare = true;
  state.players[0].occupied = true;
  state.players[1].occupied = true;
  state.players[0].fantasy = false;
  state.players[1].fantasy = false;

  COFCPlayerBoard &hero = state.players[0].board;
''',
        "make exact R4 fixture mode explicit",
    )

    old_test = '''bool TestR4TeacherFailsClosedWithoutTerminalOpponent() {
  COFCState state = ExactR4State();
  state.players[1].board.bottom[4].Clear();
  const COFCStrategyAction baseline = DeliberatelyFouledBaseline(state);
  COFCStrategyAction selected;
  COFCR4ExactTeacherReport report;
  std::string error;
  const bool ok = COFCR4ExactTeacher::Improve(
    state, baseline, &selected, &report, &error);
  return Require(!ok && !report.exact_available && !report.applied
      && selected.valid && error.find("opponent terminal board") != std::string::npos,
      "R4 teacher must leave baseline untouched when exact information is absent");
}
'''
    new_test = '''COFCState LoggedFrame000R4State() {
  COFCState state;
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.acting_chair = 1;
  state.round_index = 4;
  state.fantasy_card_count = 0;
  state.hero_can_prepare = true;
  state.players[0].occupied = true;
  state.players[1].occupied = true;
  state.players[0].fantasy = false;
  state.players[1].fantasy = false;

  COFCPlayerBoard &hero = state.players[1].board;
  hero.top[0].value = Card(14, 1);
  hero.top[1].value = Card(14, 3);
  hero.middle[0].value = Card(9, 1);
  hero.middle[1].value = Card(11, 1);
  hero.middle[2].value = Card(12, 1);
  hero.middle[3].value = Card(13, 1);
  const int bottom[5] = {
    Card(6, 0), Card(2, 1), Card(6, 1), Card(3, 3), Card(12, 3)};
  for (int i = 0; i < 5; ++i) hero.bottom[i].value = bottom[i];

  state.players[0].board.top[0].value = Card(13, 0);
  state.players[0].board.top[1].value = Card(13, 3);
  state.players[0].board.middle[0].value = Card(2, 0);
  state.players[0].board.bottom[0].value = Card(7, 0);

  state.hero_incoming_count = 3;
  state.hero_incoming[0].value = Card(14, 0);
  state.hero_incoming[1].value = Card(6, 3);
  state.hero_incoming[2].value = kOFCCardJoker1;
  return state;
}

bool TestLoggedFrame000IsAlreadyUnavoidableAtR4() {
  COFCState state = LoggedFrame000R4State();
  COFCStrategyAction baseline;
  baseline.placements[0].card_value = Card(14, 0);
  baseline.placements[0].row = kOFCRowTop;
  baseline.placements[1].card_value = kOFCCardJoker1;
  baseline.placements[1].row = kOFCRowMiddle;
  baseline.placement_count = 2;
  baseline.unused_cards[0] = Card(6, 3);
  baseline.unused_count = 1;
  baseline.valid = true;

  COFCStrategyAction selected;
  COFCR4ExactTeacherReport report;
  std::string error;
  const bool ok = COFCR4ExactTeacher::Improve(
    state, baseline, &selected, &report, &error);
  if (!Require(ok, "R4 solver rejected logged frame 000: " + error))
    return false;
  return Require(report.exact_available && !report.opponent_terminal
      && !report.applied && !report.safety_override
      && report.baseline_foul && report.selected_foul
      && report.candidates == 27 && report.safe_candidates == 0
      && selected.valid,
      "logged frame 000 had no non-foul completion; the error happened before R4");
}

bool TestR4SafetyOverrideWithoutTerminalOpponent() {
  COFCState state = ExactR4State();
  state.players[1].board.bottom[4].Clear();
  const COFCStrategyAction baseline = DeliberatelyFouledBaseline(state);
  COFCStrategyAction selected;
  COFCR4ExactTeacherReport report;
  std::string error;
  const bool ok = COFCR4ExactTeacher::Improve(
    state, baseline, &selected, &report, &error);
  return Require(ok && report.exact_available && !report.opponent_terminal
      && report.applied && report.safety_override
      && report.baseline_foul && !report.selected_foul
      && report.safe_candidates > 0 && selected.valid,
      "a recoverable foul must be replaced without inventing opponent cards");
}

bool TestR4SafeBaselineStaysWithoutTerminalOpponent() {
  COFCState state = ExactR4State();
  state.players[1].board.bottom[4].Clear();
  COFCStrategyAction baseline;
  baseline.placements[0].card_value = state.hero_incoming[2].value;
  baseline.placements[0].row = kOFCRowTop;
  baseline.placements[1].card_value = state.hero_incoming[0].value;
  baseline.placements[1].row = kOFCRowMiddle;
  baseline.placement_count = 2;
  baseline.unused_cards[0] = state.hero_incoming[1].value;
  baseline.unused_count = 1;
  baseline.valid = true;
  COFCStrategyAction selected;
  COFCR4ExactTeacherReport report;
  std::string error;
  const bool ok = COFCR4ExactTeacher::Improve(
    state, baseline, &selected, &report, &error);
  return Require(ok && report.exact_available && !report.opponent_terminal
      && !report.applied && !report.safety_override
      && !report.baseline_foul && !report.selected_foul && selected.valid,
      "hidden opponent may not replace an already safe baseline by guesswork");
}
'''
    replace_once(
        "OpenHoldem/COFCExactEvaluatorSelftest.cpp",
        old_test,
        new_test,
        "add logged and recoverable hidden-opponent R4 regressions",
    )
    replace_once(
        "OpenHoldem/COFCExactEvaluatorSelftest.cpp",
        '''      || !TestR4TeacherFailsClosedWithoutTerminalOpponent()
      || !TestProductionPolicyComposition()) return 1;
  std::cout << "PASS OpenOFC v5.6.0 exact terminal oracle + Pareto-safe R4 teacher\\n";
''',
        '''      || !TestLoggedFrame000IsAlreadyUnavoidableAtR4()
      || !TestR4SafetyOverrideWithoutTerminalOpponent()
      || !TestR4SafeBaselineStaysWithoutTerminalOpponent()
      || !TestProductionPolicyComposition()) return 1;
  std::cout << "PASS OpenOFC v5.8.1 exact R4 + hidden-opponent non-foul safety\\n";
''',
        "run v5.8.1 exact R4 safety regressions",
    )


def patch_r4_and_runtime_telemetry() -> None:
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        "engine=EXACT_FANTASY_R4_V570 identity_recovery=ACTIVE_V580",
        "engine=EXACT_FANTASY_R4_V570 identity_recovery=ACTIVE_V580 "
        "field_fix=V581",
        "publish v5.8.1 field-correction engine",
    )
    old = r'''      "[OpenOFC EXACT R4] available=%d applied=%d candidates=%d legal=%d "
      "baseline_points=%d selected_points=%d baseline_fantasy=%d "
      "selected_fantasy=%d reason=\"%s\"\n",
      policy_report.exact_r4.exact_available ? 1 : 0,
      policy_report.exact_r4.applied ? 1 : 0,
      policy_report.exact_r4.candidates,
      policy_report.exact_r4.legal_candidates,
      policy_report.exact_r4.baseline_points,
      policy_report.exact_r4.selected_points,
      policy_report.exact_r4.baseline_fantasy_cards,
      policy_report.exact_r4.selected_fantasy_cards,
      policy_report.exact_r4_reason.c_str());
'''
    new = r'''      "[OpenOFC EXACT R4] available=%d opponent_terminal=%d applied=%d "
      "safety_override=%d baseline_foul=%d selected_foul=%d candidates=%d "
      "legal=%d safe=%d baseline_points=%d selected_points=%d "
      "baseline_fantasy=%d selected_fantasy=%d reason=\"%s\"\n",
      policy_report.exact_r4.exact_available ? 1 : 0,
      policy_report.exact_r4.opponent_terminal ? 1 : 0,
      policy_report.exact_r4.applied ? 1 : 0,
      policy_report.exact_r4.safety_override ? 1 : 0,
      policy_report.exact_r4.baseline_foul ? 1 : 0,
      policy_report.exact_r4.selected_foul ? 1 : 0,
      policy_report.exact_r4.candidates,
      policy_report.exact_r4.legal_candidates,
      policy_report.exact_r4.safe_candidates,
      policy_report.exact_r4.baseline_points,
      policy_report.exact_r4.selected_points,
      policy_report.exact_r4.baseline_fantasy_cards,
      policy_report.exact_r4.selected_fantasy_cards,
      policy_report.exact_r4_reason.c_str());
'''
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        old,
        new,
        "surface exact R4 foul/safety proof",
    )


def main() -> None:
    patch_fantasy_single_delta_lineage()
    patch_r4_safety_solver()
    patch_r4_and_runtime_telemetry()
    print(
        "OPENOFC_FIELD_CORRECTIONS_V581_APPLY=PASS "
        "fantasy_stage=SINGLE_DELTA_EXACT "
        "r4=HIDDEN_OPPONENT_NONFOUL_SAFETY replay=BMP_HTML tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
