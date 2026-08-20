//******************************************************************************
//
// DeepOFC R10 physical-placement planner.
//
// No mouse input is sent here. This file only prepares and verifies one drag
// transaction for the dedicated FP0 runtime controller.
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

const char *RowName(EOFCRow row) {
  switch (row) {
    case kOFCRowTop: return "top";
    case kOFCRowMiddle: return "middle";
    case kOFCRowBottom: return "bottom";
    default: return NULL;
  }
}

int KnownInRow(const COFCPlayerBoard &board, EOFCRow row) {
  int count = 0;
  if (row == kOFCRowTop) {
    for (int i = 0; i < kOFCTopCards; ++i)
      if (board.top[i].IsKnownPhysicalCard()) ++count;
  } else if (row == kOFCRowMiddle) {
    for (int i = 0; i < kOFCMiddleCards; ++i)
      if (board.middle[i].IsKnownPhysicalCard()) ++count;
  } else if (row == kOFCRowBottom) {
    for (int i = 0; i < kOFCBottomCards; ++i)
      if (board.bottom[i].IsKnownPhysicalCard()) ++count;
  }
  return count;
}

int PendingInRow(const COFCState &state, EOFCRow row) {
  int count = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (state.pending[i].active && state.pending[i].row == row) ++count;
  }
  return count;
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
    // A pending card can also be a movable source. This is required for the
    // normal five-card opening layout, where KKPoker initially draws all five
    // cards in the bottom row before the player redistributes them.
    int source_row = -1;
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
      return Fail(error,
        "requested physical card is neither loose nor a current visual-board source");
    }
    const char *row_name = RowName(static_cast<EOFCRow>(source_row));
    CString region;
    if (observation.players[observation.hero_chair].fantasy) {
      region.Format("ofc_fantasy15_drop_%s%d", row_name, source_slot);
    } else {
      region.Format("ofc_drop_%s%d", row_name, source_slot);
    }
    RMapCI it = p_tablemap->r$()->find(region);
    if (it == p_tablemap->r$()->end()) {
      return Fail(error, "pending physical card has no calibrated source rectangle");
    }
    out->left = static_cast<LONG>(it->second.left);
    out->top = static_cast<LONG>(it->second.top);
    out->right = static_cast<LONG>(it->second.right);
    out->bottom = static_cast<LONG>(it->second.bottom);
    if (!IsUsableRect(*out)) {
      return Fail(error, "pending physical-card source rectangle is unusable");
    }
    return true;
  }

  const COFCVisualCardSource &source = observation.hero_loose_sources[found];
  if (!source.valid || source.card_value != card_value || !IsUsableRect(source.rect)) {
    return Fail(error, "current physical card has no validated click-safe source rectangle");
  }
  *out = source.rect;
  return true;
}

bool COFCActionPlanner::ResolveDropTarget(
    const COFCState &state, EOFCRow row, RECT *out, string *error) {
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

  const char *row_name = RowName(row);
  if (row_name == NULL) return Fail(error, "invalid OFC destination row");
  const int slot = KnownInRow(state.players[state.hero_chair].board, row)
    + PendingInRow(state, row);
  const int capacity = row == kOFCRowTop ? kOFCTopCards : kOFCMiddleCards;
  if (slot < 0 || slot >= capacity) {
    return Fail(error, "destination row has no free calibrated slot");
  }
  CString region_name;
  if (state.players[state.hero_chair].fantasy) {
    region_name.Format("ofc_fantasy15_drop_%s%d", row_name, slot);
  } else {
    region_name.Format("ofc_drop_%s%d", row_name, slot);
  }

  RMapCI it = p_tablemap->r$()->find(region_name);
  if (it == p_tablemap->r$()->end()) {
    ostringstream oss;
    oss << "missing calibrated tablemap drop region: "
        << region_name.GetString();
    return Fail(error, oss.str());
  }

  RECT rect;
  rect.left = static_cast<LONG>(it->second.left);
  rect.top = static_cast<LONG>(it->second.top);
  rect.right = static_cast<LONG>(it->second.right);
  rect.bottom = static_cast<LONG>(it->second.bottom);
  if (!IsUsableRect(rect)) {
    ostringstream oss;
    oss << "invalid/empty tablemap drop region: "
        << region_name.GetString();
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
      if (state.pending[i].row == row) {
        return Fail(error, "requested physical card is already in its target row");
      }
      // A different current row is a certified relocation transaction.
    }
  }

  RECT target;
  if (!ResolveDropTarget(state, row, &target, error)) return false;

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
  bool relocated = false;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (before.pending[i].active
        && before.pending[i].incoming_index == before_index) {
      relocated = true;
    }
  }
  const int expected_after = relocated ? before_pending : before_pending + 1;
  if (after_pending != expected_after) {
    return Fail(error,
      relocated
        ? "one relocation drag changed pending cardinality"
        : "one drag did not produce exactly one additional pending placement");
  }

  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!before.pending[i].active) continue;
    int old_index = before.pending[i].incoming_index;
    if (old_index < 0 || old_index >= before.hero_incoming_count) {
      return Fail(error, "pre-drag pending placement has invalid incoming index");
    }
    int old_card = before.hero_incoming[old_index].value;
    if (relocated && old_card == card_value) continue;
    int new_index = FindIncomingIndex(after, old_card);
    if (new_index < 0 || !PendingContains(after, new_index, before.pending[i].row)) {
      return Fail(error, "pre-existing tentative placement changed during drag");
    }
  }

  return true;
}
