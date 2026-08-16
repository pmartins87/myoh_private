//******************************************************************************
//
// DeepOFC R10 solver-action -> physical-turn semantic bridge.
//
//******************************************************************************

#include "StdAfx.h"
#include "COFCTurnPlan.h"

#include <algorithm>
#include <sstream>

using namespace std;

namespace {

bool Fail(COFCTurnPlan *out, string *error, const string &message) {
  if (out != NULL) out->Reset();
  if (error != NULL) *error = message;
  return false;
}

bool KnownPhysical(int value) {
  return value >= 0 && value <= kOFCCardJoker2;
}

int RowCapacity(EOFCRow row) {
  switch (row) {
    case kOFCRowTop: return kOFCTopCards;
    case kOFCRowMiddle: return kOFCMiddleCards;
    case kOFCRowBottom: return kOFCBottomCards;
    default: return 0;
  }
}

int RowKnownCount(const COFCPlayerBoard &board, EOFCRow row) {
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

struct PlacementLess {
  bool operator()(const COFCStrategyPlacement &a,
      const COFCStrategyPlacement &b) const {
    if (a.row != b.row) return static_cast<int>(a.row) < static_cast<int>(b.row);
    return a.card_value < b.card_value;
  }
};

void SortPlacements(COFCStrategyPlacement *items, int count) {
  if (count > 1) std::sort(items, items + count, PlacementLess());
}

void SortInts(int *items, int count) {
  if (count > 1) std::sort(items, items + count);
}

}  // namespace

bool COFCTurnPlanBuilder::Build(
    const COFCState &state,
    const COFCStrategyAction &action,
    COFCTurnPlan *out,
    string *error) {
  if (out == NULL) return false;
  out->Reset();
  if (error != NULL) error->clear();

  if (!state.valid) return Fail(out, error, "canonical OFC state is invalid");
  if (!action.valid) return Fail(out, error, "strategy action is invalid");
  if (action.schema_version != kOFCStrategyActionSchemaVersion) {
    return Fail(out, error, "unsupported strategy-action schema version");
  }
  if (state.hero_chair < 0 || state.hero_chair >= state.player_count) {
    return Fail(out, error, "canonical Hero chair is invalid");
  }
  if (state.acting_chair != state.hero_chair) {
    return Fail(out, error, "turn plan requires Hero to be the ordered acting chair");
  }
  if (!state.hero_can_prepare) {
    return Fail(out, error, "Hero placement preparation is not allowed");
  }

  const bool fantasy = state.players[state.hero_chair].fantasy;
  int expected_placements = 0;
  int expected_unused = 0;
  if (fantasy) {
    if (state.round_index != -1
        || state.hero_incoming_count < 14
        || state.hero_incoming_count > 17) {
      return Fail(out, error, "invalid Fantasy decision shape");
    }
    if (state.players[state.hero_chair].board.CountKnownCards() != 0) {
      return Fail(out, error, "Fantasy turn plan requires empty committed Hero board");
    }
    expected_placements = 13;
    expected_unused = state.hero_incoming_count - 13;
  } else {
    if (state.round_index < 0 || state.round_index > 4) {
      return Fail(out, error, "invalid normal round index");
    }
    const int expected_incoming = state.round_index == 0 ? 5 : 3;
    if (state.hero_incoming_count != expected_incoming) {
      return Fail(out, error, "normal incoming-card count disagrees with round");
    }
    expected_placements = state.round_index == 0 ? 5 : 2;
    expected_unused = state.round_index == 0 ? 0 : 1;
  }

  if (action.placement_count != expected_placements
      || action.unused_count != expected_unused) {
    ostringstream oss;
    oss << "strategy action has wrong shape placements=" << action.placement_count
        << " unused=" << action.unused_count
        << " expected=" << expected_placements << "/" << expected_unused;
    return Fail(out, error, oss.str());
  }

  bool incoming[54] = {false};
  bool target_present[54] = {false};
  bool unused_present[54] = {false};
  bool pending_present[54] = {false};
  EOFCRow target_row[54];
  for (int i = 0; i < 54; ++i) target_row[i] = kOFCRowUndefined;

  for (int i = 0; i < state.hero_incoming_count; ++i) {
    const int card = state.hero_incoming[i].value;
    if (!KnownPhysical(card)) {
      return Fail(out, error, "Hero incoming contains non-physical/unknown card");
    }
    if (incoming[card]) {
      return Fail(out, error, "Hero incoming contains duplicate physical card");
    }
    incoming[card] = true;
  }

  int target_by_row[3] = {0, 0, 0};
  for (int i = 0; i < action.placement_count; ++i) {
    const int card = action.placements[i].card_value;
    const EOFCRow row = action.placements[i].row;
    if (!KnownPhysical(card) || !incoming[card]) {
      return Fail(out, error, "strategy placement is not a current Hero incoming physical card");
    }
    if (row != kOFCRowTop && row != kOFCRowMiddle && row != kOFCRowBottom) {
      return Fail(out, error, "strategy placement has invalid destination row");
    }
    if (target_present[card] || unused_present[card]) {
      return Fail(out, error, "strategy action accounts for one physical card more than once");
    }
    target_present[card] = true;
    target_row[card] = row;
    ++target_by_row[static_cast<int>(row)];
    out->target[out->target_count++] = action.placements[i];
  }

  for (int i = 0; i < action.unused_count; ++i) {
    const int card = action.unused_cards[i];
    if (!KnownPhysical(card) || !incoming[card]) {
      return Fail(out, error, "strategy unused card is not a current Hero incoming physical card");
    }
    if (target_present[card] || unused_present[card]) {
      return Fail(out, error, "strategy action accounts for one physical card more than once");
    }
    unused_present[card] = true;
    out->unused_cards[out->unused_count++] = card;
  }

  for (int card = 0; card < 54; ++card) {
    if (incoming[card] != (target_present[card] || unused_present[card])) {
      return Fail(out, error, "strategy action does not partition the full incoming physical-card set");
    }
  }

  const COFCPlayerBoard &committed = state.players[state.hero_chair].board;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow row = static_cast<EOFCRow>(r);
    if (RowKnownCount(committed, row) + target_by_row[r] > RowCapacity(row)) {
      return Fail(out, error, "strategy target overflows canonical row capacity");
    }
  }
  if (fantasy
      && (target_by_row[kOFCRowTop] != 3
          || target_by_row[kOFCRowMiddle] != 5
          || target_by_row[kOFCRowBottom] != 5)) {
    return Fail(out, error, "Fantasy strategy target must fill rows exactly 3/5/5");
  }

  // Existing tentative placements are UI progress, not strategy. Preserve only
  // those that already match the solver target. A mismatch would require
  // picking up/re-routing a board card, which current R10 has not certified.
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active) continue;
    const int incoming_index = state.pending[i].incoming_index;
    if (incoming_index < 0 || incoming_index >= state.hero_incoming_count) {
      return Fail(out, error, "pending placement has invalid incoming index");
    }
    const int card = state.hero_incoming[incoming_index].value;
    if (!KnownPhysical(card) || pending_present[card]) {
      return Fail(out, error, "pending placement physical identity is invalid/duplicated");
    }
    pending_present[card] = true;
    if (!target_present[card]) {
      return Fail(out, error,
        "currently pending card must be unused by solver action; rearrangement is not certified");
    }
    if (target_row[card] != state.pending[i].row) {
      return Fail(out, error,
        "currently pending card is in a different row than solver target; rearrangement is not certified");
    }
    COFCStrategyPlacement matched;
    matched.card_value = card;
    matched.row = state.pending[i].row;
    out->already_correct[out->already_correct_count++] = matched;
  }

  for (int i = 0; i < action.placement_count; ++i) {
    const int card = action.placements[i].card_value;
    if (!pending_present[card]) {
      out->to_add[out->to_add_count++] = action.placements[i];
    }
  }

  SortPlacements(out->target, out->target_count);
  SortPlacements(out->already_correct, out->already_correct_count);
  SortPlacements(out->to_add, out->to_add_count);
  SortInts(out->unused_cards, out->unused_count);

  // Bind the complete semantic plan to the exact canonical state for which the
  // solver action was validated. R10 orchestration may later ignore only
  // tentative pending/UI-progress fields while proving the decision is still
  // the same; it must never reuse the plan after strategic state drift.
  out->decision_state = state;
  out->valid = true;
  return true;
}
