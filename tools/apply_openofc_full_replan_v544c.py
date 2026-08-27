from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path, text, eol, bom):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel, old, new, label):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: {label}")


def patch_policy_remove_executor_bias():
    rel = "OpenHoldem/COFCBaselinePolicy.cpp"
    old = '''  const int first_unused = state.round_index == 0 ? -1 : 0;
  const int last_unused = state.round_index == 0 ? -1 : expected - 1;
  bool pending_value[54] = {false};
  for (int p = 0; p < kOFCMaxIncomingCards; ++p) {
    if (!state.pending[p].active) continue;
    const int index = state.pending[p].incoming_index;
    if (index < 0 || index >= state.hero_incoming_count) continue;
    const int value = state.hero_incoming[index].value;
    if (value >= 0 && value < 54) pending_value[value] = true;
  }
  bool have_loose_nonjoker_discard = false;
  for (int i = 0; i < expected; ++i) {
    const int value = state.hero_incoming[i].value;
    if (value >= 0 && value < 54
        && !pending_value[value]
        && value != kOFCCardJoker1 && value != kOFCCardJoker2) {
      have_loose_nonjoker_discard = true;
    }
  }
  for (int unused = first_unused; unused <= last_unused; ++unused) {
'''
    new = '''  const int first_unused = state.round_index == 0 ? -1 : 0;
  const int last_unused = state.round_index == 0 ? -1 : expected - 1;
  // OPENOFC_FULL_REPLAN_V544C: UI position is deliberately absent from the
  // strategy objective.  A provisional pending card may become the optimal
  // discard after opponent information is revealed; the executor can now
  // return it to any free incoming slot transactionally.
  for (int unused = first_unused; unused <= last_unused; ++unused) {
'''
    replace_once(rel, old, new, "remove physical-layout discard bias")

    path, text, eol, bom = read_source(rel)
    guard = '''    if (unused >= 0 && have_loose_nonjoker_discard
        && pending_value[incoming[unused].value]) continue;
'''
    count = text.count(guard)
    if count != 2:
        raise RuntimeError(f"remove physical-layout discard guards: expected 2, got {count}")
    text = text.replace(guard, "")
    write_source(path, text, eol, bom)
    print(f"patched {rel}: removed {count} pending-discard guards")


def patch_turn_plan_accept_pending_unused():
    rel = "OpenHoldem/COFCTurnPlan.cpp"
    old = '''    pending_present[card] = true;
    if (!target_present[card]) {
      return Fail(out, error,
        "currently pending card is unused by solver action; moving back to loose is unsupported");
    }
    if (target_row[card] == state.pending[i].row) {
      COFCStrategyPlacement matched;
      matched.card_value = card;
      matched.row = state.pending[i].row;
      out->already_correct[out->already_correct_count++] = matched;
    }
'''
    new = '''    pending_present[card] = true;
    // OPENOFC_FULL_REPLAN_V544C: a pending placement is UI progress, not a
    // strategic commitment.  If the final solver action marks this card unused,
    // the orchestrator will first return it to a free incoming slot.  If it is
    // still a target in another row, the existing relocation path handles it.
    if (target_present[card] && target_row[card] == state.pending[i].row) {
      COFCStrategyPlacement matched;
      matched.card_value = card;
      matched.row = state.pending[i].row;
      out->already_correct[out->already_correct_count++] = matched;
    }
'''
    replace_once(rel, old, new, "pending card may become final discard")


def patch_action_planner_header():
    rel = "OpenHoldem/COFCActionPlanner.h"
    old = '''  static bool BuildPlacementStep(
      const COFCState &state,
      int card_value,
      EOFCRow row,
      const RECT &source_rect,
      COFCUIPlacementStep *out,
      std::string *error);

  // Verify that a rescraped state contains the requested physical card as a
'''
    new = '''  static bool BuildPlacementStep(
      const COFCState &state,
      int card_value,
      EOFCRow row,
      const RECT &source_rect,
      COFCUIPlacementStep *out,
      std::string *error);

  // Return one tentative normal-round placement to any currently empty one of
  // KKPoker's three incoming-card positions.  This is the inverse UI operation
  // required for a dealer provisional arrangement to be fully re-optimized
  // after the opponent reveals final information.
  static bool BuildReturnToLooseStepFromObservation(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int card_value,
      COFCUIPlacementStep *out,
      std::string *error);

  // Verify that a rescraped state contains the requested physical card as a
'''
    replace_once(rel, old, new, "declare pending-to-loose builder")

    old = '''  static bool VerifyPendingTransition(
      const COFCState &before,
      const COFCState &after,
      int card_value,
      EOFCRow row,
      std::string *error);

 private:
'''
    new = '''  static bool VerifyPendingTransition(
      const COFCState &before,
      const COFCState &after,
      int card_value,
      EOFCRow row,
      std::string *error);

  static bool VerifyReturnToLooseTransition(
      const COFCState &before,
      const COFCState &after,
      int card_value,
      std::string *error);

 private:
'''
    replace_once(rel, old, new, "declare pending-to-loose verifier")

    old = '''  static bool ResolveDropTarget(
      const COFCState &state, EOFCRow row, RECT *out, std::string *error);
  static int FindIncomingIndex(const COFCState &state, int card_value);
'''
    new = '''  static bool ResolveDropTarget(
      const COFCState &state, EOFCRow row, RECT *out, std::string *error);
  static bool ResolveIncomingReturnTarget(
      const COFCVisualObservation &observation,
      RECT *out,
      std::string *error);
  static int FindIncomingIndex(const COFCState &state, int card_value);
'''
    replace_once(rel, old, new, "declare free incoming target resolver")


def patch_action_planner_cpp():
    rel = "OpenHoldem/COFCActionPlanner.cpp"

    old = '''bool DragTargetsExplicitlyCalibrated() {
  if (p_tablemap == NULL) return false;
  SMapCI it = p_tablemap->s$()->find(CString("ofc_drag_targets_calibrated"));
  if (it == p_tablemap->s$()->end()) return false;
  CString value = it->second.text;
  value.Trim();
  return value == "1";
}

}  // namespace
'''
    new = '''bool DragTargetsExplicitlyCalibrated() {
  if (p_tablemap == NULL) return false;
  SMapCI it = p_tablemap->s$()->find(CString("ofc_drag_targets_calibrated"));
  if (it == p_tablemap->s$()->end()) return false;
  CString value = it->second.text;
  value.Trim();
  return value == "1";
}

bool RectsOverlap(const RECT &a, const RECT &b) {
  return a.left < b.right && b.left < a.right
    && a.top < b.bottom && b.top < a.bottom;
}

}  // namespace
'''
    replace_once(rel, old, new, "add rectangle overlap helper")

    anchor = '''bool COFCActionPlanner::BuildPlacementStepFromObservation(
'''
    path, text, eol, bom = read_source(rel)
    if text.count(anchor) != 1:
        raise RuntimeError("pending-to-loose planner insertion anchor not unique")
    helper = r'''bool COFCActionPlanner::ResolveIncomingReturnTarget(
    const COFCVisualObservation &observation,
    RECT *out,
    string *error) {
  if (out == NULL) return Fail(error, "incoming return-target output is null");
  SetRectEmpty(out);
  if (p_tablemap == NULL) return Fail(error, "tablemap is not available");
  if (!DragTargetsExplicitlyCalibrated()) {
    return Fail(error,
      "OFC drag targets are not explicitly calibrated for pending-to-loose movement");
  }
  if (!observation.valid || observation.hero_chair < 0
      || observation.hero_chair >= observation.player_count) {
    return Fail(error, "raw OFC observation is invalid for pending-to-loose movement");
  }
  if (observation.players[observation.hero_chair].fantasy) {
    return Fail(error, "pending-to-loose incoming return is currently normal-OFC only");
  }
  if (observation.round_index <= 0 || observation.round_index > 4) {
    return Fail(error, "pending-to-loose return requires normal discard round R1-R4");
  }

  RECT incoming[3];
  bool occupied[3] = {false, false, false};
  for (int slot = 0; slot < 3; ++slot) {
    CString name;
    name.Format("ofc_hero_in%ddrag", slot);
    RMapCI it = p_tablemap->r$()->find(name);
    if (it == p_tablemap->r$()->end()) {
      return Fail(error, "missing calibrated incoming drag region for return-to-loose");
    }
    incoming[slot].left = static_cast<LONG>(it->second.left);
    incoming[slot].top = static_cast<LONG>(it->second.top);
    incoming[slot].right = static_cast<LONG>(it->second.right);
    incoming[slot].bottom = static_cast<LONG>(it->second.bottom);
    if (!IsUsableRect(incoming[slot])) {
      return Fail(error, "incoming return target rectangle is unusable");
    }
  }

  int mapped_loose = 0;
  for (int i = 0; i < observation.hero_loose_count; ++i) {
    const COFCVisualCardSource &source = observation.hero_loose_sources[i];
    if (!source.valid || !IsUsableRect(source.rect)) {
      return Fail(error,
        "loose-card source geometry is incomplete; cannot prove an empty incoming slot");
    }
    int matched = -1;
    for (int slot = 0; slot < 3; ++slot) {
      if (!RectsOverlap(source.rect, incoming[slot])) continue;
      if (matched >= 0) {
        return Fail(error, "one loose-card source overlaps multiple incoming slots");
      }
      matched = slot;
    }
    if (matched < 0) {
      return Fail(error, "loose-card source does not map to any incoming slot");
    }
    if (occupied[matched]) {
      return Fail(error, "multiple loose cards map to one incoming slot");
    }
    occupied[matched] = true;
    ++mapped_loose;
  }
  if (mapped_loose != observation.hero_loose_count) {
    return Fail(error, "incoming occupancy proof disagrees with loose-card count");
  }

  for (int slot = 0; slot < 3; ++slot) {
    if (!occupied[slot]) {
      *out = incoming[slot];
      return true;
    }
  }
  return Fail(error, "no empty incoming slot is available for pending-to-loose return");
}

bool COFCActionPlanner::BuildReturnToLooseStepFromObservation(
    const COFCState &state,
    const COFCVisualObservation &observation,
    int card_value,
    COFCUIPlacementStep *out,
    string *error) {
  if (out == NULL) return Fail(error, "return-to-loose step output is null");
  *out = COFCUIPlacementStep();
  if (error != NULL) error->clear();
  if (!state.valid || !observation.valid)
    return Fail(error, "state/raw observation is invalid for pending-to-loose movement");
  if (state.hero_chair < 0 || state.hero_chair >= state.player_count)
    return Fail(error, "canonical Hero chair is invalid");
  if (state.players[state.hero_chair].fantasy)
    return Fail(error, "pending-to-loose return is currently normal-OFC only");
  if (state.round_index <= 0 || state.round_index > 4)
    return Fail(error, "pending-to-loose return requires R1-R4");
  if (!state.hero_can_prepare)
    return Fail(error, "Hero cannot prepare placements in this state");
  if (observation.player_count != state.player_count
      || observation.hero_chair != state.hero_chair
      || observation.dealer_chair != state.dealer_chair
      || observation.round_index != state.round_index) {
    return Fail(error, "raw/canonical metadata mismatch for pending-to-loose movement");
  }

  const int incoming_index = FindIncomingIndex(state, card_value);
  if (incoming_index < 0)
    return Fail(error, "return card is not a unique current Hero incoming card");
  bool pending = false;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (state.pending[i].active && state.pending[i].incoming_index == incoming_index) {
      pending = true;
      break;
    }
  }
  if (!pending)
    return Fail(error, "return-to-loose card is not currently pending");

  // A pending card must be sourced from its current row rectangle.  Refuse a
  // contradictory raw frame that simultaneously reports the same card loose.
  for (int i = 0; i < observation.hero_loose_count; ++i) {
    if (observation.hero_loose_cards[i].IsKnownPhysicalCard()
        && observation.hero_loose_cards[i].value == card_value) {
      return Fail(error, "pending return card is simultaneously visible as loose");
    }
  }

  RECT source;
  if (!ResolveLooseSource(observation, card_value, &source, error)) return false;
  RECT target;
  if (!ResolveIncomingReturnTarget(observation, &target, error)) return false;

  out->card_value = card_value;
  out->row = kOFCRowUndefined;  // explicit pending -> loose transaction
  out->source_rect = source;
  out->target_rect = target;
  return true;
}

'''
    text = text.replace(anchor, helper + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: add pending-to-loose planning")

    path, text, eol, bom = read_source(rel)
    tail = '''  return true;
}
'''
    pos = text.rfind(tail)
    if pos < 0:
        raise RuntimeError("pending-to-loose verifier tail anchor missing")
    verifier = r'''
bool COFCActionPlanner::VerifyReturnToLooseTransition(
    const COFCState &before,
    const COFCState &after,
    int card_value,
    string *error) {
  if (error != NULL) error->clear();
  if (!before.valid || !after.valid)
    return Fail(error, "pending-to-loose verification received invalid state");
  if (before.player_count != after.player_count
      || before.hero_chair != after.hero_chair
      || before.dealer_chair != after.dealer_chair
      || before.round_index != after.round_index) {
    return Fail(error, "unexpected hand metadata change during pending-to-loose drag");
  }

  const int before_index = FindIncomingIndex(before, card_value);
  const int after_index = FindIncomingIndex(after, card_value);
  if (before_index < 0 || after_index < 0)
    return Fail(error, "returned physical card disappeared or became ambiguous");

  bool was_pending = false;
  int before_pending = 0;
  int after_pending = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (before.pending[i].active) {
      ++before_pending;
      if (before.pending[i].incoming_index == before_index) was_pending = true;
    }
    if (after.pending[i].active) {
      ++after_pending;
      if (after.pending[i].incoming_index == after_index) {
        return Fail(error, "returned card is still pending after drag to incoming area");
      }
    }
  }
  if (!was_pending)
    return Fail(error, "return transaction was not pending before drag");
  if (after_pending != before_pending - 1)
    return Fail(error, "pending-to-loose drag did not remove exactly one pending placement");

  // Every other tentative placement must survive byte-semantically: same
  // physical identity and same row.  Only the requested card may leave pending.
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!before.pending[i].active) continue;
    const int old_index = before.pending[i].incoming_index;
    if (old_index < 0 || old_index >= before.hero_incoming_count)
      return Fail(error, "pre-return pending placement has invalid incoming index");
    const int old_card = before.hero_incoming[old_index].value;
    if (old_card == card_value) continue;
    const int new_index = FindIncomingIndex(after, old_card);
    if (new_index < 0 || !PendingContains(after, new_index, before.pending[i].row)) {
      return Fail(error, "another pending placement changed during return-to-loose drag");
    }
  }
  return true;
}
'''
    insert_at = pos + len(tail)
    text = text[:insert_at] + verifier + text[insert_at:]
    write_source(path, text, eol, bom)
    print(f"patched {rel}: add pending-to-loose verification")


def patch_action_executor():
    rel = "OpenHoldem/COFCActionExecutor.h"
    old = '''  bool BeginPlacement(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int card_value,
      EOFCRow row,
      int duration_ms,
      std::string *error);

  bool VerifyAfterFreshScrape(
'''
    new = '''  bool BeginPlacement(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int card_value,
      EOFCRow row,
      int duration_ms,
      std::string *error);

  bool BeginReturnToLoose(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int card_value,
      int duration_ms,
      std::string *error);

  bool VerifyAfterFreshScrape(
'''
    replace_once(rel, old, new, "declare return-to-loose executor")
    old = '''  bool awaiting_verification_;
  bool blocked_;
  int card_value_;
'''
    new = '''  bool awaiting_verification_;
  bool blocked_;
  bool returning_to_loose_;
  int card_value_;
'''
    replace_once(rel, old, new, "store transaction direction")

    rel = "OpenHoldem/COFCActionExecutor.cpp"
    old = '''  awaiting_verification_ = false;
  blocked_ = false;
  card_value_ = kOFCCardNoCard;
'''
    new = '''  awaiting_verification_ = false;
  blocked_ = false;
  returning_to_loose_ = false;
  card_value_ = kOFCCardNoCard;
'''
    replace_once(rel, old, new, "reset return transaction flag")

    old = '''  before_ = state;
  card_value_ = card_value;
  row_ = row;
  awaiting_verification_ = true;
'''
    new = '''  before_ = state;
  card_value_ = card_value;
  row_ = row;
  returning_to_loose_ = false;
  awaiting_verification_ = true;
'''
    replace_once(rel, old, new, "mark placement transaction")

    anchor = '''bool COFCActionExecutor::VerifyAfterFreshScrape(
'''
    path, text, eol, bom = read_source(rel)
    if text.count(anchor) != 1:
        raise RuntimeError("return-to-loose executor insertion anchor not unique")
    method = r'''bool COFCActionExecutor::BeginReturnToLoose(
    const COFCState &state,
    const COFCVisualObservation &observation,
    int card_value,
    int duration_ms,
    string *error) {
  if (error != NULL) error->clear();
  if (blocked_) {
    if (error != NULL) *error = "executor is blocked until a known new-hand reset";
    return false;
  }
  if (awaiting_verification_) {
    return FailAndBlock(error,
      "attempted pending-to-loose drag before verification of previous drag");
  }

  string enable_error;
  if (!RuntimeExecutionExplicitlyEnabled(&enable_error)) {
    if (error != NULL) *error = enable_error;
    return false;
  }
  if (p_casino_interface == NULL)
    return FailAndBlock(error, "casino interface is unavailable");

  COFCUIPlacementStep step;
  string plan_error;
  if (!COFCActionPlanner::BuildReturnToLooseStepFromObservation(
        state, observation, card_value, &step, &plan_error)) {
    if (error != NULL) *error = plan_error;
    return false;
  }

  before_ = state;
  card_value_ = card_value;
  row_ = kOFCRowUndefined;
  returning_to_loose_ = true;
  awaiting_verification_ = true;

  write_log(true,
    "[DeepOFC DRAG] stage=SEND card=%s value=%d operation=RETURN_TO_LOOSE "
    "source=(%ld,%ld,%ld,%ld) target=(%ld,%ld,%ld,%ld) duration_ms=%d\n",
    CardLabel(card_value_).c_str(), card_value_,
    step.source_rect.left, step.source_rect.top,
    step.source_rect.right, step.source_rect.bottom,
    step.target_rect.left, step.target_rect.top,
    step.target_rect.right, step.target_rect.bottom,
    duration_ms);

  if (!p_casino_interface->DragRectToRect(
        step.source_rect, step.target_rect, duration_ms)) {
    return FailAndBlock(error,
      "physical pending-to-loose drag failed or was refused after transaction start");
  }
  write_log(true,
    "[DeepOFC DRAG] stage=SENT card=%s value=%d operation=RETURN_TO_LOOSE result=OK awaiting=FRESH_SCRAPE\n",
    CardLabel(card_value_).c_str(), card_value_);
  return true;
}

'''
    text = text.replace(anchor, method + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: implement return-to-loose executor")

    old = '''  string verify_error;
  if (!COFCActionPlanner::VerifyPendingTransition(
        before_, after, card_value_, row_, &verify_error)) {
    return FailAndBlock(error, verify_error);
  }

  write_log(true,
    "[DeepOFC DRAG] stage=VERIFIED card=%s value=%d row=%s result=OK\\n",
    CardLabel(card_value_).c_str(), card_value_, RowLabel(row_));
  awaiting_verification_ = false;
  card_value_ = kOFCCardNoCard;
  row_ = kOFCRowUndefined;
  before_.Reset();
'''
    new = '''  string verify_error;
  const bool verified = returning_to_loose_
    ? COFCActionPlanner::VerifyReturnToLooseTransition(
        before_, after, card_value_, &verify_error)
    : COFCActionPlanner::VerifyPendingTransition(
        before_, after, card_value_, row_, &verify_error);
  if (!verified) return FailAndBlock(error, verify_error);

  write_log(true,
    "[DeepOFC DRAG] stage=VERIFIED card=%s value=%d operation=%s row=%s result=OK\\n",
    CardLabel(card_value_).c_str(), card_value_,
    returning_to_loose_ ? "RETURN_TO_LOOSE" : "PLACE",
    RowLabel(row_));
  awaiting_verification_ = false;
  returning_to_loose_ = false;
  card_value_ = kOFCCardNoCard;
  row_ = kOFCRowUndefined;
  before_.Reset();
'''
    replace_once(rel, old, new, "verify both placement directions")


def patch_orchestrator():
    rel = "OpenHoldem/COFCTurnOrchestrator.h"
    old = '''  bool ValidateProgress(
      const COFCState &state,
      bool *placements_complete,
      bool *ready_for_confirm,
      COFCStrategyPlacement *next,
      bool *has_next,
      std::string *error) const;
'''
    new = '''  bool ValidateProgress(
      const COFCState &state,
      bool *placements_complete,
      bool *ready_for_confirm,
      int *return_to_loose_card,
      bool *has_return_to_loose,
      COFCStrategyPlacement *next,
      bool *has_next,
      std::string *error) const;
'''
    replace_once(rel, old, new, "extend progress with reverse operation")
    old = '''  bool BeginNextPlacement(
      const COFCState &state,
      const COFCVisualObservation &observation,
      const COFCStrategyPlacement &next,
      int duration_ms,
      bool starting_turn,
      std::string *error);
'''
    new = '''  bool BeginNextPlacement(
      const COFCState &state,
      const COFCVisualObservation &observation,
      const COFCStrategyPlacement &next,
      int duration_ms,
      bool starting_turn,
      std::string *error);
  bool BeginReturnToLoose(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int card_value,
      int duration_ms,
      bool starting_turn,
      std::string *error);
'''
    replace_once(rel, old, new, "declare reverse orchestrator step")

    rel = "OpenHoldem/COFCTurnOrchestrator.cpp"
    old = '''    bool *placements_complete,
    bool *ready_for_confirm,
    COFCStrategyPlacement *next,
    bool *has_next,
    string *error) const {
  if (placements_complete != NULL) *placements_complete = false;
  if (ready_for_confirm != NULL) *ready_for_confirm = false;
  if (has_next != NULL) *has_next = false;
  if (next != NULL) *next = COFCStrategyPlacement();
'''
    new = '''    bool *placements_complete,
    bool *ready_for_confirm,
    int *return_to_loose_card,
    bool *has_return_to_loose,
    COFCStrategyPlacement *next,
    bool *has_next,
    string *error) const {
  if (placements_complete != NULL) *placements_complete = false;
  if (ready_for_confirm != NULL) *ready_for_confirm = false;
  if (return_to_loose_card != NULL) *return_to_loose_card = kOFCCardNoCard;
  if (has_return_to_loose != NULL) *has_return_to_loose = false;
  if (has_next != NULL) *has_next = false;
  if (next != NULL) *next = COFCStrategyPlacement();
'''
    replace_once(rel, old, new, "extend progress function signature")

    old = '''    ++pending_count;
    if (!target_present[card]) {
      if (error != NULL) *error =
        "fresh pending card is not a solver target; rearrangement is not certified";
      return false;
    }
  }

  bool found_next = false;
'''
    new = '''    ++pending_count;
    if (!target_present[card]) {
      // OPENOFC_FULL_REPLAN_V544C: normal R1-R4 has exactly one final unused
      // card.  A provisional placement of that card must be reversed before
      // applying the new final target arrangement.
      if (state.players[state.hero_chair].fantasy || state.round_index <= 0) {
        if (error != NULL) *error =
          "non-target pending card requires unsupported non-normal reverse movement";
        return false;
      }
      if (has_return_to_loose != NULL && *has_return_to_loose) {
        if (error != NULL) *error =
          "multiple pending cards require return-to-loose in one normal decision";
        return false;
      }
      if (return_to_loose_card != NULL) *return_to_loose_card = card;
      if (has_return_to_loose != NULL) *has_return_to_loose = true;
    }
  }

  if (has_return_to_loose != NULL && *has_return_to_loose) {
    // Reverse stale provisional UI progress first.  A fresh scrape then proves
    // the card is loose before any new final placement is attempted.
    return true;
  }

  bool found_next = false;
'''
    replace_once(rel, old, new, "schedule stale provisional card return")

    anchor = '''bool COFCTurnOrchestrator::StartTurn(
'''
    path, text, eol, bom = read_source(rel)
    if text.count(anchor) != 1:
        raise RuntimeError("orchestrator reverse insertion anchor not unique")
    method = r'''bool COFCTurnOrchestrator::BeginReturnToLoose(
    const COFCState &state,
    const COFCVisualObservation &observation,
    int card_value,
    int duration_ms,
    bool starting_turn,
    string *error) {
  string movement_error;
  if (placement_executor_.BeginReturnToLoose(
        state, observation, card_value, duration_ms, &movement_error)) {
    return true;
  }
  if (placement_executor_.blocked()) return FailAndBlock(error, movement_error);
  if (starting_turn) {
    active_ = false;
    baseline_.Reset();
    plan_.Reset();
    if (error != NULL) *error = movement_error;
    return false;
  }
  return FailAndBlock(error, movement_error);
}

'''
    text = text.replace(anchor, method + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: add reverse movement orchestration")

    # Update both progress call sites and operation dispatches.
    path, text, eol, bom = read_source(rel)
    old_call = '''  COFCStrategyPlacement next;
  bool has_next = false;
  string progress_error;
  if (!ValidateProgress(
        state, placements_complete, ready_for_confirm,
        &next, &has_next, &progress_error)) {
'''
    new_call = '''  int return_to_loose_card = kOFCCardNoCard;
  bool has_return_to_loose = false;
  COFCStrategyPlacement next;
  bool has_next = false;
  string progress_error;
  if (!ValidateProgress(
        state, placements_complete, ready_for_confirm,
        &return_to_loose_card, &has_return_to_loose,
        &next, &has_next, &progress_error)) {
'''
    if text.count(old_call) != 1:
        raise RuntimeError(f"StartTurn progress call expected 1, got {text.count(old_call)}")
    text = text.replace(old_call, new_call, 1)
    old_dispatch = '''  if (!has_next) {
    return true;
  }

  return BeginNextPlacement(
    state, observation, next, duration_ms, true, error);
}
'''
    new_dispatch = '''  if (has_return_to_loose) {
    return BeginReturnToLoose(
      state, observation, return_to_loose_card, duration_ms, true, error);
  }
  if (!has_next) return true;
  return BeginNextPlacement(
    state, observation, next, duration_ms, true, error);
}
'''
    if text.count(old_dispatch) != 1:
        raise RuntimeError(f"StartTurn dispatch expected 1, got {text.count(old_dispatch)}")
    text = text.replace(old_dispatch, new_dispatch, 1)

    old_call2 = '''  COFCStrategyPlacement next;
  bool has_next = false;
  string progress_error;
  if (!ValidateProgress(
        fresh_state, placements_complete, ready_for_confirm,
        &next, &has_next, &progress_error)) {
'''
    new_call2 = '''  int return_to_loose_card = kOFCCardNoCard;
  bool has_return_to_loose = false;
  COFCStrategyPlacement next;
  bool has_next = false;
  string progress_error;
  if (!ValidateProgress(
        fresh_state, placements_complete, ready_for_confirm,
        &return_to_loose_card, &has_return_to_loose,
        &next, &has_next, &progress_error)) {
'''
    if text.count(old_call2) != 1:
        raise RuntimeError(f"Advance progress call expected 1, got {text.count(old_call2)}")
    text = text.replace(old_call2, new_call2, 1)
    old_dispatch2 = '''  if (!has_next) {
    return true;
  }

  return BeginNextPlacement(
    fresh_state, fresh_observation, next, duration_ms, false, error);
}
'''
    new_dispatch2 = '''  if (has_return_to_loose) {
    return BeginReturnToLoose(
      fresh_state, fresh_observation, return_to_loose_card,
      duration_ms, false, error);
  }
  if (!has_next) return true;
  return BeginNextPlacement(
    fresh_state, fresh_observation, next, duration_ms, false, error);
}
'''
    if text.count(old_dispatch2) != 1:
        raise RuntimeError(f"Advance dispatch expected 1, got {text.count(old_dispatch2)}")
    text = text.replace(old_dispatch2, new_dispatch2, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: wire reverse operation into Start/Advance")


def patch_selftest():
    rel = "OpenHoldem/COFCUnknownToleranceSelftest.cpp"
    anchor = '''bool OpeningUnknownStaysValidButPolicyWaits() {
'''
    path, text, eol, bom = read_source(rel)
    if text.count(anchor) != 1:
        raise RuntimeError("full-replan selftest insertion anchor not unique")
    test = r'''bool PendingUnusedIsAcceptedForFullReplan() {
  COFCState state;
  state.Reset();
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.dealer_chair = 1;
  state.dealer_known = true;
  state.acting_chair = 1;
  state.round_index = 1;
  state.hero_can_prepare = true;
  state.players[0].occupied = state.players[1].occupied = true;
  state.players[0].source_chair = 0;
  state.players[1].source_chair = 1;
  PutOpeningBoard(&state.players[1].board);
  state.hero_incoming_count = 3;
  state.hero_incoming[0].value = 20;
  state.hero_incoming[1].value = 21;
  state.hero_incoming[2].value = 22;

  // Provisional plan had card 20 in middle.  After opponent reveal the final
  // strategy wants 20 discarded and uses 21/22 instead.
  state.pending[0].active = true;
  state.pending[0].incoming_index = 0;
  state.pending[0].row = kOFCRowMiddle;

  COFCStrategyAction action;
  action.valid = true;
  action.placements[0].card_value = 21;
  action.placements[0].row = kOFCRowTop;
  action.placements[1].card_value = 22;
  action.placements[1].row = kOFCRowBottom;
  action.placement_count = 2;
  action.unused_cards[0] = 20;
  action.unused_count = 1;

  COFCTurnPlan plan;
  std::string error;
  if (!Require(COFCTurnPlanBuilder::Build(state, action, &plan, &error),
        "final replan must accept a currently pending card as new discard")) {
    std::cerr << error << "\n";
    return false;
  }
  return Require(plan.valid && plan.target_count == 2
      && plan.unused_count == 1 && plan.unused_cards[0] == 20,
      "turn plan preserves strategy freedom despite provisional UI placement");
}

'''
    text = text.replace(anchor, test + anchor, 1)
    old_main = '''  if (!UnknownUnusedDoesNotBlockNextRound(r1)) return 1;
  if (!OpeningUnknownStaysValidButPolicyWaits()) return 1;
  std::cout
    << "PASS OpenOFC v5.4.4 UNKNOWN_OCCUPIED: transient lineage repair, "
    << "later-round safe unused, next-round continuation, opening wait\\n";
'''
    new_main = '''  if (!UnknownUnusedDoesNotBlockNextRound(r1)) return 1;
  if (!PendingUnusedIsAcceptedForFullReplan()) return 1;
  if (!OpeningUnknownStaysValidButPolicyWaits()) return 1;
  std::cout
    << "PASS OpenOFC v5.4.4 UNKNOWN_OCCUPIED/FULL_REPLAN: transient lineage repair, "
    << "later-round safe unused, pending-to-loose strategy freedom, next-round continuation, opening wait\\n";
'''
    if text.count(old_main) != 1:
        raise RuntimeError("full-replan selftest main anchor missing")
    text = text.replace(old_main, new_main, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: add pending-unused strategy regression")


def assert_contract():
    checks = {
        "OpenHoldem/COFCBaselinePolicy.cpp": [
            "OPENOFC_FULL_REPLAN_V544C",
        ],
        "OpenHoldem/COFCActionPlanner.cpp": [
            "BuildReturnToLooseStepFromObservation",
            "ofc_hero_in%ddrag",
            "VerifyReturnToLooseTransition",
        ],
        "OpenHoldem/COFCActionExecutor.cpp": [
            "operation=RETURN_TO_LOOSE",
            "BeginReturnToLoose",
        ],
        "OpenHoldem/COFCTurnOrchestrator.cpp": [
            "has_return_to_loose",
            "BeginReturnToLoose",
        ],
    }
    for rel, tokens in checks.items():
        _, text, _, _ = read_source(rel)
        for token in tokens:
            if token not in text:
                raise RuntimeError(f"full-replan contract missing {token} in {rel}")
    _, policy, _, _ = read_source("OpenHoldem/COFCBaselinePolicy.cpp")
    if "have_loose_nonjoker_discard" in policy:
        raise RuntimeError("executor limitation still biases strategy discard choice")
    _, plan, _, _ = read_source("OpenHoldem/COFCTurnPlan.cpp")
    if "moving back to loose is unsupported" in plan:
        raise RuntimeError("legacy pending-to-loose strategy prohibition still present")
    print("OpenOFC v5.4.4C full-replan source contract: PASS")


def main():
    patch_policy_remove_executor_bias()
    patch_turn_plan_accept_pending_unused()
    patch_action_planner_header()
    patch_action_planner_cpp()
    patch_action_executor()
    patch_orchestrator()
    patch_selftest()
    assert_contract()
    print("OpenOFC v5.4.4C full dealer replan patch applied successfully")


if __name__ == "__main__":
    main()
