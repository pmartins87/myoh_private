//******************************************************************************
//
// DeepOFC R10 physical-placement planner.
//
// No mouse input is sent here. This file only prepares and verifies one drag
// transaction. Live execution remains blocked by the R9 hard read-only guard.
//
//******************************************************************************

#include "StdAfx.h"
#include "COFCActionPlanner.h"

#include <sstream>

#include "..\CTablemap\CTablemap.h"

using namespace std;

namespace {

bool Fail(string *error, const string &message) {
  if (error != NULL) *error = message;
  return false;
}

const char *DropRegionName(EOFCRow row) {
  switch (row) {
    case kOFCRowTop: return "ofc_drop_top";
    case kOFCRowMiddle: return "ofc_drop_middle";
    case kOFCRowBottom: return "ofc_drop_bottom";
    default: return NULL;
  }
}

bool DragTargetsExplicitlyCalibrated() {
  if (p_tablemap == NULL) return false;
  SMapCI it = p_tablemap->s$()->find(CString("ofc_drag_targets_calibrated"));
  if (it == p_tablemap->s$()->end()) return false;
  CString value = it->second.text;
  value.Trim();
  return value == "1";
}

}  // namespace

bool COFCActionPlanner::IsUsableRect(const RECT &rect) {
  return rect.right > rect.left && rect.bottom > rect.top;
}

int COFCActionPlanner::FindIncomingIndex(const COFCState &state, int card_value) {
  if (card_value < 0 || card_value > kOFCCardJoker2) return -1;
  int found = -1;
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    if (!state.hero_incoming[i].IsKnownPhysicalCard()) continue;
    if (state.hero_incoming[i].value != card_value) continue;
    if (found >= 0) return -1;  // impossible/ambiguous duplicate
    found = i;
  }
  return found;
}

bool COFCActionPlanner::PendingContains(
    const COFCState &state, int incoming_index, EOFCRow row) {
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active) continue;
    if (state.pending[i].incoming_index == incoming_index
        && state.pending[i].row == row) {
      return true;
    }
  }
  return false;
}

bool COFCActionPlanner::ResolveLooseSource(
    const COFCVisualObservation &observation,
    int card_value,
    RECT *out,
    string *error) {
  if (out == NULL) return Fail(error, "source-rectangle output is null");
  SetRectEmpty(out);
  if (!observation.valid) return Fail(error, "raw OFC observation is invalid");

  int found = -1;
  for (int i = 0; i < observation.hero_loose_count; ++i) {
    if (!observation.hero_loose_cards[i].IsKnownPhysicalCard()) continue;
    if (observation.hero_loose_cards[i].value != card_value) continue;
    if (found >= 0) {
      return Fail(error, "requested physical card has duplicate raw loose-card sources");
    }
    found = i;
  }
  if (found < 0) {
    return Fail(error, "requested physical card is not currently loose in the raw observation");
  }

  const COFCVisualCardSource &source = observation.hero_loose_sources[found];
  if (!source.valid || source.card_value != card_value || !IsUsableRect(source.rect)) {
    return Fail(error, "current physical card has no validated click-safe source rectangle");
  }
  *out = source.rect;
  return true;
}

bool COFCActionPlanner::ResolveDropTarget(
    EOFCRow row, RECT *out, string *error) {
  if (out == NULL) return Fail(error, "drop-target output is null");
  SetRectEmpty(out);
  if (p_tablemap == NULL) return Fail(error, "tablemap is not available");
  if (!p_tablemap->SupportsOFCJokerUltimate()) {
    return Fail(error, "tablemap is not explicitly Joker Ultimate");
  }
  // Region existence alone is never enough to authorize physical movement.
  // Replay drafts and guessed geometry must carry this symbol as 0. Only a
  // deliberately calibrated runtime tablemap may set it to 1.
  if (!DragTargetsExplicitlyCalibrated()) {
    return Fail(error,
      "OFC drag targets are not explicitly calibrated (s$ofc_drag_targets_calibrated != 1)");
  }

  const char *name = DropRegionName(row);
  if (name == NULL) return Fail(error, "invalid OFC destination row");

  RMapCI it = p_tablemap->r$()->find(CString(name));
  if (it == p_tablemap->r$()->end()) {
    ostringstream oss;
    oss << "missing calibrated tablemap drop region: " << name;
    return Fail(error, oss.str());
  }

  RECT rect;
  rect.left = static_cast<LONG>(it->second.left);
  rect.top = static_cast<LONG>(it->second.top);
  rect.right = static_cast<LONG>(it->second.right);
  rect.bottom = static_cast<LONG>(it->second.bottom);
  if (!IsUsableRect(rect)) {
    ostringstream oss;
    oss << "invalid/empty tablemap drop region: " << name;
    return Fail(error, oss.str());
  }
  *out = rect;
  return true;
}

bool COFCActionPlanner::BuildPlacementStepFromObservation(
    const COFCState &state,
    const COFCVisualObservation &observation,
    int card_value,
    EOFCRow row,
    COFCUIPlacementStep *out,
    string *error) {
  if (!observation.valid) return Fail(error, "raw OFC observation is invalid");
  if (!state.valid) return Fail(error, "canonical OFC state is invalid");
  if (observation.player_count != state.player_count
      || observation.hero_chair != state.hero_chair
      || observation.dealer_chair != state.dealer_chair
      || observation.acting_chair != state.acting_chair
      || observation.round_index != state.round_index) {
    return Fail(error, "raw/canonical metadata mismatch; source geometry may be stale");
  }

  RECT source;
  if (!ResolveLooseSource(observation, card_value, &source, error)) return false;
  return BuildPlacementStep(state, card_value, row, source, out, error);
}

bool COFCActionPlanner::BuildPlacementStep(
    const COFCState &state,
    int card_value,
    EOFCRow row,
    const RECT &source_rect,
    COFCUIPlacementStep *out,
    string *error) {
  if (out == NULL) return Fail(error, "placement-step output is null");
  *out = COFCUIPlacementStep();
  if (error != NULL) error->clear();

  if (!state.valid) return Fail(error, "canonical OFC state is invalid");
  if (!state.hero_can_prepare) return Fail(error, "Hero cannot prepare placements in this state");
  if (state.hero_chair < 0 || state.hero_chair >= state.player_count) {
    return Fail(error, "canonical Hero chair is invalid");
  }
  if (row != kOFCRowTop && row != kOFCRowMiddle && row != kOFCRowBottom) {
    return Fail(error, "invalid OFC destination row");
  }
  if (!IsUsableRect(source_rect)) return Fail(error, "source-card rectangle is invalid/empty");

  int incoming_index = FindIncomingIndex(state, card_value);
  if (incoming_index < 0) {
    return Fail(error, "requested physical card is not a unique current Hero incoming card");
  }
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active) continue;
    if (state.pending[i].incoming_index == incoming_index) {
      return Fail(error, "requested physical card is already tentatively placed");
    }
  }

  RECT target;
  if (!ResolveDropTarget(row, &target, error)) return false;

  out->card_value = card_value;
  out->row = row;
  out->source_rect = source_rect;
  out->target_rect = target;
  return true;
}

bool COFCActionPlanner::VerifyPendingTransition(
    const COFCState &before,
    const COFCState &after,
    int card_value,
    EOFCRow row,
    string *error) {
  if (error != NULL) error->clear();
  if (!before.valid) return Fail(error, "pre-drag canonical state is invalid");
  if (!after.valid) return Fail(error, "post-drag canonical state is invalid");
  if (before.player_count != after.player_count
      || before.hero_chair != after.hero_chair
      || before.dealer_chair != after.dealer_chair
      || before.round_index != after.round_index) {
    return Fail(error, "unexpected hand metadata change during one drag transaction");
  }

  int before_index = FindIncomingIndex(before, card_value);
  int after_index = FindIncomingIndex(after, card_value);
  if (before_index < 0 || after_index < 0) {
    return Fail(error, "dragged physical card disappeared or became ambiguous");
  }
  if (PendingContains(before, before_index, row)) {
    return Fail(error, "requested transition was already present before drag");
  }
  if (!PendingContains(after, after_index, row)) {
    return Fail(error, "post-drag state does not contain requested card in requested pending row");
  }

  // A single drag may add exactly one new pending card; it must not silently
  // remove or reroute any pre-existing tentative placement.
  int before_pending = 0;
  int after_pending = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (before.pending[i].active) ++before_pending;
    if (after.pending[i].active) ++after_pending;
  }
  if (after_pending != before_pending + 1) {
    return Fail(error, "one drag did not produce exactly one additional pending placement");
  }

  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!before.pending[i].active) continue;
    int old_index = before.pending[i].incoming_index;
    if (old_index < 0 || old_index >= before.hero_incoming_count) {
      return Fail(error, "pre-drag pending placement has invalid incoming index");
    }
    int old_card = before.hero_incoming[old_index].value;
    int new_index = FindIncomingIndex(after, old_card);
    if (new_index < 0 || !PendingContains(after, new_index, before.pending[i].row)) {
      return Fail(error, "pre-existing tentative placement changed during drag");
    }
  }

  return true;
}
