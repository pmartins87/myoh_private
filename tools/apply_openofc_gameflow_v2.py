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
        raise RuntimeError(f"{rel}: expected exactly one replacement target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def regex_once(rel: str, pattern: str, replacement: str, flags=re.S):
    path, text, eol, bom = read_source(rel)
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{rel}: regex expected one target, got {count}: {pattern[:100]}")
    write_source(path, new, eol, bom)
    print(f"patched {rel}")


def patch_state_contract():
    replace_once(
        "OpenHoldem/COFCState.h",
        '''    hero_can_prepare = false;
    hero_can_confirm = false;
    action_required = false;
''',
        '''    hero_can_prepare = false;
    hero_can_confirm = false;
    hero_timer_active = false;
    decision_finalizable = false;
    action_required = false;
''')
    replace_once(
        "OpenHoldem/COFCState.h",
        '''  bool hero_can_prepare;
  bool hero_can_confirm;
  bool action_required;
''',
        '''  bool hero_can_prepare;
  bool hero_can_confirm;
  // OFC-native timing facts. Preparation may be simultaneous; finalization is
  // a separate authority gate, especially when Hero is the dealer.
  bool hero_timer_active;
  bool decision_finalizable;
  bool action_required;
''')
    replace_once(
        "OpenHoldem/COFCState.h",
        'const int kOFCCardJoker2 = 53;\n',
        '''const int kOFCCardJoker2 = 53;
// Raw TableMap token X means "a Joker occurrence". The reconstructor resolves
// generic occurrences to internal 52/53 identities before canonical use.
const int kOFCCardJokerGeneric = 54;
''')
    replace_once(
        "OpenHoldem/COFCState.h",
        '''  bool IsJoker() const { return (value == kOFCCardJoker1 || value == kOFCCardJoker2); }
  bool IsKnownPhysicalCard() const { return IsKnownStandardCard() || IsJoker(); }
''',
        '''  bool IsJoker() const {
    return value == kOFCCardJoker1 || value == kOFCCardJoker2
      || value == kOFCCardJokerGeneric;
  }
  bool IsKnownPhysicalCard() const { return IsKnownStandardCard() || IsJoker(); }
''')

    replace_once(
        "OpenHoldem/COFCVisualObservation.h",
        '''    hero_can_prepare = false;
    confirm_visible = false;
''',
        '''    hero_can_prepare = false;
    hero_timer_active = false;
    confirm_visible = false;
''')
    replace_once(
        "OpenHoldem/COFCVisualObservation.h",
        '''  bool hero_can_prepare;
  // Raw UI fact only. Canonical safe Hero confirm additionally requires that
''',
        '''  bool hero_can_prepare;
  // Countdown/timer visibility for the Hero in normal OFC. This is not a
  // movement gate: it tells the runtime when dealer-side provisional work may
  // be finalized using the opponent's now-revealed information.
  bool hero_timer_active;
  // Raw UI fact only. Canonical safe Hero confirm additionally requires that
''')


def patch_joker_rank_token():
    pattern = r'''int CScraper::ScrapeOFCSlot\(CString base_name, COFCCard \*card,\n    bool \*is_back, int \*joker_id\) \{.*?\n\}\n\nstatic bool DeepOFCRegisterKnownCard'''
    replacement = r'''int CScraper::ScrapeOFCSlot(CString base_name, COFCCard *card,
    bool *is_back, int *joker_id) {
  if ((card == NULL) || (is_back == NULL) || (joker_id == NULL)) return -1;
  card->Clear();
  *is_back = false;
  *joker_id = 0;

  const CString empty_region = base_name + "empty";
  const CString back_region = base_name + "back";
  const CString rank_region = base_name + "rank";
  const CString suit_region = base_name + "suit";

  if (!DeepOFCRegionExists(empty_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing mandatory slot empty region: %s\n",
      empty_region.GetString());
    return -1;
  }
  bool empty = false;
  EvaluateTrueFalseRegion(&empty, empty_region);
  if (empty) {
    DeepOFCLogSlot(base_name, "EMPTY", kOFCCardNoCard,
      CString(""), CString(""), true, false, false, false, "");
    return 0;
  }

  if (!DeepOFCRegionExists(back_region) || !DeepOFCRegionExists(rank_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Non-empty slot lacks back/rank contract: %s\n",
      base_name.GetString());
    return -1;
  }

  bool back = false;
  EvaluateTrueFalseRegion(&back, back_region);
  if (back) {
    *is_back = true;
    DeepOFCLogSlot(base_name, "BACK", kOFCCardBack,
      CString(""), CString(""), empty, true, false, false, "");
    return 0;
  }

  // OPENOFC_JOKER_RANK_TOKEN: X is reserved by OpenOFC for a Joker occurrence.
  // It deliberately lives in the same Tn rank transform as A/K/Q/J/T/2..9.
  // Suit is not required for X. Internal occurrence identity (52/53) is
  // assigned later by the state reconstructor, so the TableMap never needs
  // separate joker1/joker2 regions.
  CString rank_result;
  const bool rank_evaluated = EvaluateRegion(rank_region, &rank_result);
  rank_result.Trim();
  rank_result.MakeUpper();
  if (rank_evaluated && rank_result == "X") {
    card->value = kOFCCardJokerGeneric;
    *joker_id = 1;
    DeepOFCLogSlot(base_name, "TABLEMAP_JOKER_X", card->value,
      rank_result, CString(""), empty, false, true, false,
      "rank_token=X suit_ignored=1");
    return 1;
  }

  if (!rank_evaluated || !IsRankString(rank_result)
      || !DeepOFCRegionExists(suit_region)) {
    DeepOFCLogSlot(base_name, "REJECTED", kOFCCardUnknown,
      rank_result, CString(""), empty, false, false, false,
      "rank_eval_or_contract_failed");
    return -3;
  }

  CString suit_result;
  const bool suit_evaluated = EvaluateRegion(suit_region, &suit_result);
  suit_result.Trim();
  if (!suit_evaluated || !IsSuitString(suit_result)) {
    DeepOFCLogSlot(base_name, "REJECTED", kOFCCardUnknown,
      rank_result, suit_result, empty, false, false, false,
      "suit_eval_or_validation_failed");
    return -3;
  }
  if (rank_result == "10") rank_result = "T";
  const int tablemap_card = CardString2CardNumber(rank_result + suit_result);
  if (tablemap_card < 0 || tablemap_card > 51) {
    DeepOFCLogSlot(base_name, "REJECTED", kOFCCardUnknown,
      rank_result, suit_result, empty, false, false, false,
      "rank_suit_to_card_failed");
    return -3;
  }
  card->value = tablemap_card;
  DeepOFCLogSlot(base_name, "TABLEMAP_TEXT", card->value,
    rank_result, suit_result, empty, false, false, false,
    "rank_first=1 joker_token=X");
  return 1;
}

static bool DeepOFCRegisterKnownCard'''
    regex_once("OpenHoldem/COFCScraper.cpp", pattern, replacement)

    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '''static bool DeepOFCRegisterKnownCard(int value, set<int> *seen) {
  if ((value < 0) || (value > kOFCCardJoker2)) return true;
''',
        '''static bool DeepOFCRegisterKnownCard(int value, set<int> *seen) {
  if (value == kOFCCardJokerGeneric) return true;
  if ((value < 0) || (value > kOFCCardJoker2)) return true;
''')
    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '''  if (value == kOFCCardJoker2) return "JK2";
  if (value < 0 || value > 51) return "INVALID";
''',
        '''  if (value == kOFCCardJoker2) return "JK2";
  if (value == kOFCCardJokerGeneric) return "JK";
  if (value < 0 || value > 51) return "INVALID";
''')


def patch_generic_joker_resolution():
    rel = "OpenHoldem/COFCReconstructor.cpp"
    path, text, eol, bom = read_source(rel)
    anchor = "bool ValidateObservationKnownCardUniqueness(\n"
    if anchor not in text:
        raise RuntimeError("reconstructor uniqueness anchor missing")
    helper = r'''
void CollectGenericJokerPointers(
    COFCVisualObservation *obs,
    vector<COFCCard *> *cards) {
  cards->clear();
  for (int p = 0; p < obs->player_count; ++p) {
    COFCPlayerBoard *b = &obs->players[p].visual_board;
    for (int i = 0; i < kOFCTopCards; ++i)
      if (b->top[i].value == kOFCCardJokerGeneric) cards->push_back(&b->top[i]);
    for (int i = 0; i < kOFCMiddleCards; ++i)
      if (b->middle[i].value == kOFCCardJokerGeneric) cards->push_back(&b->middle[i]);
    for (int i = 0; i < kOFCBottomCards; ++i)
      if (b->bottom[i].value == kOFCCardJokerGeneric) cards->push_back(&b->bottom[i]);
  }
  for (int i = 0; i < obs->hero_loose_count; ++i)
    if (obs->hero_loose_cards[i].value == kOFCCardJokerGeneric)
      cards->push_back(&obs->hero_loose_cards[i]);
  for (int i = 0; i < obs->hero_discard_tracker_count; ++i)
    if (obs->hero_discard_tracker[i].value == kOFCCardJokerGeneric)
      cards->push_back(&obs->hero_discard_tracker[i]);
}

bool ResolveGenericJokerOccurrences(
    COFCVisualObservation *obs,
    string *error) {
  vector<COFCCard *> generic;
  CollectGenericJokerPointers(obs, &generic);
  if (generic.empty()) return true;
  if (generic.size() > 2) {
    if (error != NULL) *error = "more than two generic Joker occurrences are visible";
    return false;
  }

  bool used1 = false;
  bool used2 = false;
  for (int p = 0; p < obs->player_count; ++p) {
    const COFCPlayerBoard &b = obs->players[p].visual_board;
    for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
      vector<int> values = KnownRowValues(b, static_cast<EOFCRow>(r));
      for (size_t i = 0; i < values.size(); ++i) {
        if (values[i] == kOFCCardJoker1) used1 = true;
        if (values[i] == kOFCCardJoker2) used2 = true;
      }
    }
  }
  for (int i = 0; i < obs->hero_loose_count; ++i) {
    if (obs->hero_loose_cards[i].value == kOFCCardJoker1) used1 = true;
    if (obs->hero_loose_cards[i].value == kOFCCardJoker2) used2 = true;
  }
  for (int i = 0; i < obs->hero_discard_tracker_count; ++i) {
    if (obs->hero_discard_tracker[i].value == kOFCCardJoker1) used1 = true;
    if (obs->hero_discard_tracker[i].value == kOFCCardJoker2) used2 = true;
  }

  for (size_t i = 0; i < generic.size(); ++i) {
    if (!used1) { generic[i]->value = kOFCCardJoker1; used1 = true; }
    else if (!used2) { generic[i]->value = kOFCCardJoker2; used2 = true; }
    else {
      if (error != NULL) *error = "generic Joker cannot be assigned a unique internal occurrence";
      return false;
    }
  }
  return true;
}

'''
    text = text.replace(anchor, helper + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")

    replace_once(
        rel,
        '''  COFCVisualObservation observation = input_observation;
  // JK1/JK2 are persistent visual identities; never swap occurrence labels.

''',
        '''  COFCVisualObservation observation = input_observation;
  // The TableMap emits a single rank token X for Joker. Resolve up to two raw
  // occurrences to internal 52/53 identities before uniqueness/state logic.
  string joker_resolution_error;
  if (!ResolveGenericJokerOccurrences(&observation, &joker_resolution_error)) {
    return Fail(out, error, joker_resolution_error);
  }

''')


def patch_timer_and_simultaneous_prepare():
    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '  obs->hero_can_prepare = (obs->acting_chair == hero_chair);\n',
        '''  // OPENOFC_SIMULTANEOUS_PREPARE: visible incoming cards are enough to
  // arrange. OFC preparation is not an exclusive Hold'em-style "my turn".
  obs->hero_can_prepare = true;
  CString hero_timer_region;
  hero_timer_region.Format("ofc_p%d_timer_active", hero_chair);
  if (!DeepOFCReadMandatoryBoolean(
        this, hero_timer_region, &obs->hero_timer_active)) return false;
''')

    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '  obs->hero_can_prepare = obs->acting_chair == hero_chair;\n',
        '''  obs->hero_can_prepare = true;
  obs->hero_timer_active = false;
''')

    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '''    "round=%d prepare=%d confirm=%d loose=%d discards=%d\\n",
''',
        '''    "round=%d prepare=%d confirm=%d timer=%d loose=%d discards=%d\\n",
''')
    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '''    obs.hero_can_prepare ? 1 : 0, obs.confirm_visible ? 1 : 0,
    obs.hero_loose_count, obs.hero_discard_tracker_count);
''',
        '''    obs.hero_can_prepare ? 1 : 0, obs.confirm_visible ? 1 : 0,
    obs.hero_timer_active ? 1 : 0,
    obs.hero_loose_count, obs.hero_discard_tracker_count);
''')


def patch_reconstructor_timing_and_round0_reset():
    rel = "OpenHoldem/COFCReconstructor.cpp"
    old = '''  out->hero_can_prepare = observation.hero_can_prepare;
  out->hero_can_confirm = observation.confirm_visible
    && observation.acting_chair == observation.hero_chair;
  out->action_required = out->hero_can_confirm;
'''
    new = '''  out->hero_can_prepare = observation.hero_can_prepare;
  out->hero_timer_active = observation.hero_timer_active;
  const bool hero_fantasy =
    observation.players[observation.hero_chair].fantasy;
  out->decision_finalizable = hero_fantasy
    || observation.dealer_chair != observation.hero_chair
    || observation.hero_timer_active;
  out->hero_can_confirm =
    observation.confirm_visible && out->decision_finalizable;
  out->action_required = out->hero_can_confirm;
'''
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 2:
        raise RuntimeError(f"{rel}: expected 2 canonical timing blocks, got {count}")
    text = text.replace(old, new)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")

    replace_once(
        "OpenHoldem/CLazyScraper.cpp",
        '''    if (raw->round_index == 0 && previous_state.valid &&
        (previous_state.round_index > 0 ||
         (previous_state.hero_chair >= 0 &&
          previous_state.hero_chair < previous_state.player_count &&
          previous_state.players[previous_state.hero_chair].fantasy))) {
      previous = NULL;
    }
''',
        '''    if (raw->round_index == 0) {
      // OPENOFC_ROUND0_FRESH_RECONSTRUCT: opening placement has no committed
      // Hero board. Rebuild it from the fresh five-card visual set every time.
      // This also recovers cleanly when a prior hand never produced a stable
      // post-Confirm round-1 frame before the next hand began.
      previous = NULL;
    }
''')

    replace_once(
        rel,
        '''      << ",\\"hero_can_confirm\\":" << BoolJson(state.hero_can_confirm)
      << ",\\"action_required\\":" << BoolJson(state.action_required)
''',
        '''      << ",\\"hero_can_confirm\\":" << BoolJson(state.hero_can_confirm)
      << ",\\"hero_timer_active\\":" << BoolJson(state.hero_timer_active)
      << ",\\"decision_finalizable\\":" << BoolJson(state.decision_finalizable)
      << ",\\"action_required\\":" << BoolJson(state.action_required)
''')


def patch_simultaneous_gates():
    replace_once(
        "OpenHoldem/COFCBaselinePolicy.cpp",
        '''  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare)
    return Fail(action, error, "policy called when Hero cannot prepare");
''',
        '''  if (!state.hero_can_prepare)
    return Fail(action, error, "policy called when Hero cannot prepare");
''')
    replace_once(
        "OpenHoldem/COFCTurnPlan.cpp",
        '''  if (state.acting_chair != state.hero_chair) {
    return Fail(out, error, "turn plan requires Hero to be the ordered acting chair");
  }
''',
        '')
    replace_once(
        "OpenHoldem/COFCTurnOrchestrator.cpp",
        '''  if (state.acting_chair != state.hero_chair) {
    if (error != NULL) *error = "ordered actor changed away from Hero during placement turn";
    return false;
  }
''',
        '')
    replace_once(
        "OpenHoldem/COFCConfirmVerifier.cpp",
        '''  if (before.acting_chair != before.hero_chair
      || !before.hero_can_confirm
      || !before.action_required) {
''',
        '''  if (!before.hero_can_confirm || !before.action_required) {
''')
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  if (!state.valid || !state.hero_can_confirm || !state.action_required
      || state.acting_chair != state.hero_chair) {
''',
        '''  if (!state.valid || !state.hero_can_confirm || !state.action_required
      || !state.decision_finalizable) {
''')


def patch_provisional_dealer_runtime():
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        '''    kArranging,
    kConfirmSent,
''',
        '''    kArranging,
    kWaitingFinalInfo,
    kConfirmSent,
''')
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        '''  int drag_retry_count_;
  std::string hand_signature_;
''',
        '''  int drag_retry_count_;
  bool provisional_;
  std::string hand_signature_;
''')

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''COFCRuntimeController::COFCRuntimeController()
    : phase_(kIdle), pending_before_drag_(0), drag_wait_cycles_(0),
      drag_retry_count_(0) {}
''',
        '''COFCRuntimeController::COFCRuntimeController()
    : phase_(kIdle), pending_before_drag_(0), drag_wait_cycles_(0),
      drag_retry_count_(0), provisional_(false) {}
''')
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  drag_retry_count_ = 0;
  hand_signature_ = IncomingSignature(state);
''',
        '''  drag_retry_count_ = 0;
  provisional_ = false;
  hand_signature_ = IncomingSignature(state);
''')
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1 && PendingCount(state) == 0
    && state.hero_incoming_count == 15;
''',
        '''  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1 && PendingCount(state) == 0
    && state.hero_incoming_count >= 14 && state.hero_incoming_count <= 17;
''')

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''bool COFCRuntimeController::StartDecision(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  COFCStrategyAction action;
''',
        '''bool COFCRuntimeController::StartDecision(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  provisional_ = !state.decision_finalizable
    && !state.players[state.hero_chair].fantasy;
  write_log(true,
    "[OpenOFC DECISION] mode=%s dealer=%d hero=%d timer=%d finalizable=%d\\n",
    provisional_ ? "PROVISIONAL" : "FINAL",
    state.dealer_chair, state.hero_chair,
    state.hero_timer_active ? 1 : 0,
    state.decision_finalizable ? 1 : 0);
  COFCStrategyAction action;
''')

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  phase_ = kArranging;
  if (complete && ready) {
''',
        '''  phase_ = kArranging;
  if (complete && provisional_) {
    orchestrator_.ResetForKnownNewHand();
    plan_.Reset();
    phase_ = kWaitingFinalInfo;
    write_log(true,
      "[OpenOFC PROVISIONAL] arrangement_complete=1 confirm=HELD waiting=OPPONENT_FINAL_INFO\\n");
    return true;
  }
  if (complete && ready) {
''')

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  drag_retry_count_ = 0;
  if (complete && ready) return SendConfirm(state);
  return true;
}
''',
        '''  drag_retry_count_ = 0;
  if (complete && provisional_) {
    orchestrator_.ResetForKnownNewHand();
    plan_.Reset();
    phase_ = kWaitingFinalInfo;
    write_log(true,
      "[OpenOFC PROVISIONAL] arrangement_complete=1 confirm=HELD timer=%d\\n",
      state.hero_timer_active ? 1 : 0);
    if (state.decision_finalizable) {
      provisional_ = false;
      phase_ = kIdle;
      return StartDecision(state, observation);
    }
    return true;
  }
  if (complete && ready) return SendConfirm(state);
  return true;
}
''')

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=WAITING_TURN actor=%d hero=%d prepare=%d\\n",
      state.acting_chair, state.hero_chair, state.hero_can_prepare ? 1 : 0);
    return;
  }
  if (phase_ == kIdle) {
''',
        '''  if (!state.hero_can_prepare) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=NO_PREPARABLE_CARDS actor=%d hero=%d prepare=0\\n",
      state.acting_chair, state.hero_chair);
    return;
  }
  if (phase_ == kWaitingFinalInfo) {
    if (!state.decision_finalizable) {
      write_log(true,
        "[OpenOFC PROVISIONAL] waiting=1 dealer=%d hero=%d timer=%d confirm=HELD\\n",
        state.dealer_chair, state.hero_chair, state.hero_timer_active ? 1 : 0);
      return;
    }
    provisional_ = false;
    phase_ = kIdle;
    write_log(true,
      "[OpenOFC PROVISIONAL] opponent_final_info=1 reanalyze=1\\n");
    StartDecision(state, observation);
    return;
  }
  if (phase_ == kIdle) {
''')

    rel = "OpenHoldem/COFCTurnOrchestrator.cpp"
    old = '''    if (pa.occupied != pb.occupied
        || pa.source_chair != pb.source_chair
        || pa.fantasy != pb.fantasy
        || pa.sitting_out != pb.sitting_out
        || pa.hidden_discard_count != pb.hidden_discard_count
        || pa.hidden_incoming_count != pb.hidden_incoming_count
        || !SameBoard(pa.board, pb.board)) {
      if (error != NULL) *error = "player canonical state changed during fixed turn";
      return false;
    }
'''
    new = '''    const bool opponent_drift_allowed =
      !a.decision_finalizable && p != a.hero_chair;
    if (pa.occupied != pb.occupied
        || pa.source_chair != pb.source_chair
        || pa.fantasy != pb.fantasy
        || pa.sitting_out != pb.sitting_out
        || (!opponent_drift_allowed
            && (pa.hidden_discard_count != pb.hidden_discard_count
                || pa.hidden_incoming_count != pb.hidden_incoming_count
                || !SameBoard(pa.board, pb.board)))) {
      if (error != NULL) *error = "player canonical state changed during fixed turn";
      return false;
    }
'''
    replace_once(rel, old, new)


def patch_fantasy_14_17():
    replace_once(
        "OpenHoldem/COFCFantasy15PixelRecognizer.cpp",
        '''  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(
        labels, &identity_error)
      || !COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(
        labels, original_fantasy_cards, &identity_error)) {
''',
        '''  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(
        labels, &identity_error)
      || (!original_fantasy_cards.empty()
          && !COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(
            labels, original_fantasy_cards, &identity_error))) {
''')

    rel = "OpenHoldem/COFCScraper.cpp"
    regex_once(
        rel,
        r'''  // Prove that the geometry package contains the complete measured source\n  // and arrangement contract before any pixel classifier is allowed to run\.\n  CString region;\n  for \(int i = 0; i < 15; \+\+i\) \{.*?\n  \}\n  const int row_counts''',
        '''  // Fantasy loose cards reflow after every placement. Only destination
  // arrangement geometry is fixed; every source rectangle is detected anew.
  CString region;
  const int row_counts''')

    replace_once(
        rel,
        '''      && previous->round_index == -1
      && previous->hero_incoming_count == 15) {
''',
        '''      && previous->round_index == -1
      && previous->hero_incoming_count >= 14
      && previous->hero_incoming_count <= 17) {
''')

    replace_once(
        rel,
        '''    if (original_labels.size() == 15
        && COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
          _entire_window_cur, true, original_labels,
          &loose, &recognition_error)
        && loose.size() == 2) {
''',
        '''    if (original_labels.size() >= 14 && original_labels.size() <= 17
        && COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
          _entire_window_cur, true, original_labels,
          &loose, &recognition_error)
        && loose.size() == original_labels.size() - 13) {
''')

    old_initial = '''  if (arrangement_count == 0) {
    if (!COFCFantasy15PixelRecognizer::RecognizeInitialFanObjects(
          _entire_window_cur, &loose, &recognition_error)) {
      write_log(k_always_log_errors,
        "[DeepOFC] Initial Fantasy15 fan rejected: %s\\n",
        recognition_error.c_str());
      return false;
    }
    original_labels.clear();
    for (size_t i = 0; i < loose.size(); ++i) {
      original_labels.push_back(loose[i].card.PhysicalLabel());
    }
  } else if (!loose_pre_recognized) {
    if (original_labels.size() != 15) {
      write_log(k_always_log_errors,
        "[DeepOFC] Dynamic Fantasy reflow lacks a validated original 15-card lineage\\n");
      return false;
    }
'''
    new_initial = '''  if (arrangement_count == 0) {
    std::vector<string> no_prior_lineage;
    if (!COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
          _entire_window_cur, false, no_prior_lineage,
          &loose, &recognition_error)) {
      write_log(k_always_log_errors,
        "[DeepOFC] Initial dynamic Fantasy fan rejected: %s\\n",
        recognition_error.c_str());
      return false;
    }
    if (loose.size() < 14 || loose.size() > 17) {
      write_log(k_always_log_errors,
        "[DeepOFC] Initial Fantasy requires 14..17 dynamic loose cards; got=%d\\n",
        static_cast<int>(loose.size()));
      return false;
    }
    original_labels.clear();
    for (size_t i = 0; i < loose.size(); ++i) {
      original_labels.push_back(loose[i].card.PhysicalLabel());
    }
  } else if (!loose_pre_recognized) {
    if (original_labels.size() < 14 || original_labels.size() > 17) {
      write_log(k_always_log_errors,
        "[DeepOFC] Dynamic Fantasy reflow lacks validated original 14..17-card lineage\\n");
      return false;
    }
'''
    replace_once(rel, old_initial, new_initial)

    replace_once(
        rel,
        '''  if (arrangement_count + static_cast<int>(loose.size()) != 15) {
    write_log(k_always_log_errors,
      "[DeepOFC] Operational Fantasy15 requires exactly 15 cards; got pending=%d loose=%d\\n",
      arrangement_count, static_cast<int>(loose.size()));
    return false;
  }
''',
        '''  const int fantasy_total =
    arrangement_count + static_cast<int>(loose.size());
  if (fantasy_total < 14 || fantasy_total > 17
      || (!original_labels.empty()
          && fantasy_total != static_cast<int>(original_labels.size()))) {
    write_log(k_always_log_errors,
      "[DeepOFC] Operational Fantasy requires stable 14..17-card lineage; pending=%d loose=%d original=%d\\n",
      arrangement_count, static_cast<int>(loose.size()),
      static_cast<int>(original_labels.size()));
    return false;
  }
''')

    pattern = r'''  int dealer_count = 0;\n  int actor_count = 0;\n  for \(int p = 0; p < player_count; \+\+p\) \{.*?\n  obs->hero_can_prepare = true;\n  obs->hero_timer_active = false;\n'''
    replacement = '''  int dealer_count = 0;
  for (int p = 0; p < player_count; ++p) {
    bool value = false;
    CString name;
    name.Format("ofc_p%d_dealer", p);
    if (!DeepOFCReadMandatoryBoolean(this, name, &value)) return false;
    if (value) { obs->dealer_chair = p; ++dealer_count; }
  }
  if (dealer_count != 1) return false;
  if (!DeepOFCReadMandatoryBoolean(
        this, "ofc_fantasy15_confirm_visible", &obs->confirm_visible)) {
    return false;
  }
  obs->acting_chair = hero_chair;
  obs->hero_can_prepare = true;
  obs->hero_timer_active = false;
'''
    regex_once(rel, pattern, replacement)

    replace_once(
        "OpenHoldem/COFCBaselinePolicy.cpp",
        '''  if (state.hero_incoming_count != 15) {
    return Fail(action, error,
      "operational FP0 Fantasy policy is intentionally limited to exactly 15 cards");
  }
  vector<PolicyCard> incoming;
  for (int i = 0; i < 15; ++i) {
''',
        '''  const int fantasy_count = state.hero_incoming_count;
  if (fantasy_count < 14 || fantasy_count > 17) {
    return Fail(action, error,
      "operational Fantasy policy requires 14..17 cards");
  }
  vector<PolicyCard> incoming;
  for (int i = 0; i < fantasy_count; ++i) {
''')
    replace_once(
        "OpenHoldem/COFCBaselinePolicy.cpp",
        '  const unsigned int limit = 1u << 15;\n',
        '  const unsigned int limit = 1u << fantasy_count;\n')
    replace_once(
        "OpenHoldem/COFCBaselinePolicy.cpp",
        '''  for (int i = 0; i < 15; ++i) {
    EOFCRow row = kOFCRowUndefined;
''',
        '''  for (int i = 0; i < fantasy_count; ++i) {
    EOFCRow row = kOFCRowUndefined;
''')
    replace_once(
        "OpenHoldem/COFCBaselinePolicy.cpp",
        '''  action->valid = action->placement_count == 13 && action->unused_count == 2;
''',
        '''  action->valid = action->placement_count == 13
    && action->unused_count == fantasy_count - 13;
''')


def patch_contract_v2():
    replace_once(
        "OpenHoldem/CHeartbeatThread.cpp",
        'const int kOpenOFCContractVersion = 1;\n',
        'const int kOpenOFCContractVersion = 2;\n')


def main():
    patch_state_contract()
    patch_joker_rank_token()
    patch_generic_joker_resolution()
    patch_timer_and_simultaneous_prepare()
    patch_reconstructor_timing_and_round0_reset()
    patch_simultaneous_gates()
    patch_provisional_dealer_runtime()
    patch_fantasy_14_17()
    patch_contract_v2()
    print("OpenOFC gameflow/Joker/Fantasy14-17 repair applied successfully")


if __name__ == "__main__":
    main()
