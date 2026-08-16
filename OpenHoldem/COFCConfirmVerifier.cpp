//******************************************************************************
//
// DeepOFC R10 normal-play Confirm semantic verifier.
//
//******************************************************************************

#include "StdAfx.h"
#include "COFCConfirmVerifier.h"

using namespace std;

namespace {

bool Fail(COFCConfirmReceipt *receipt, string *error, const string &message) {
  if (receipt != NULL) *receipt = COFCConfirmReceipt();
  if (error != NULL) *error = message;
  return false;
}

bool SameBoard(const COFCPlayerBoard &a, const COFCPlayerBoard &b) {
  for (int i = 0; i < kOFCTopCards; ++i)
    if (a.top[i].value != b.top[i].value) return false;
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (a.middle[i].value != b.middle[i].value) return false;
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (a.bottom[i].value != b.bottom[i].value) return false;
  return true;
}

bool KnownPhysical(int value) {
  return value >= 0 && value <= kOFCCardJoker2;
}

void RowSet(const COFCPlayerBoard &board, EOFCRow row, bool out[54]) {
  for (int i = 0; i < 54; ++i) out[i] = false;
  if (row == kOFCRowTop) {
    for (int i = 0; i < kOFCTopCards; ++i)
      if (board.top[i].IsKnownPhysicalCard()) out[board.top[i].value] = true;
  } else if (row == kOFCRowMiddle) {
    for (int i = 0; i < kOFCMiddleCards; ++i)
      if (board.middle[i].IsKnownPhysicalCard()) out[board.middle[i].value] = true;
  } else if (row == kOFCRowBottom) {
    for (int i = 0; i < kOFCBottomCards; ++i)
      if (board.bottom[i].IsKnownPhysicalCard()) out[board.bottom[i].value] = true;
  }
}

bool SameBoolSet(const bool a[54], const bool b[54]) {
  for (int i = 0; i < 54; ++i)
    if (a[i] != b[i]) return false;
  return true;
}

bool SameIncoming(const COFCState &a, const COFCState &b) {
  if (a.hero_incoming_count != b.hero_incoming_count) return false;
  for (int i = 0; i < a.hero_incoming_count; ++i)
    if (a.hero_incoming[i].value != b.hero_incoming[i].value) return false;
  return true;
}

bool SameDiscards(const COFCState &a, const COFCState &b) {
  if (a.hero_discard_count != b.hero_discard_count) return false;
  for (int i = 0; i < a.hero_discard_count; ++i)
    if (a.hero_discards[i].value != b.hero_discards[i].value) return false;
  return true;
}

bool SameBoundDecision(const COFCState &bound, const COFCState &current) {
  if (!bound.valid || !current.valid) return false;
  if (bound.schema_version != current.schema_version
      || bound.player_count != current.player_count
      || bound.hero_chair != current.hero_chair
      || bound.dealer_chair != current.dealer_chair
      || bound.acting_chair != current.acting_chair
      || bound.round_index != current.round_index
      || !SameIncoming(bound, current)
      || !SameDiscards(bound, current)) {
    return false;
  }
  for (int p = 0; p < bound.player_count; ++p) {
    const COFCPlayerState &a = bound.players[p];
    const COFCPlayerState &b = current.players[p];
    if (a.occupied != b.occupied
        || a.source_chair != b.source_chair
        || a.fantasy != b.fantasy
        || a.sitting_out != b.sitting_out
        || a.hidden_discard_count != b.hidden_discard_count
        || a.hidden_incoming_count != b.hidden_incoming_count
        || !SameBoard(a.board, b.board)) {
      return false;
    }
  }
  // pending[] and Hero UI action flags are intentionally UI progress.
  return true;
}

bool PendingExactlyMatchesPlan(
    const COFCState &state,
    const COFCTurnPlan &plan) {
  bool target[54] = {false};
  bool pending[54] = {false};
  EOFCRow target_row[54];
  for (int i = 0; i < 54; ++i) target_row[i] = kOFCRowUndefined;

  for (int i = 0; i < plan.target_count; ++i) {
    const int card = plan.target[i].card_value;
    if (!KnownPhysical(card) || target[card]) return false;
    target[card] = true;
    target_row[card] = plan.target[i].row;
  }

  int pending_count = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active) continue;
    const int incoming_index = state.pending[i].incoming_index;
    if (incoming_index < 0 || incoming_index >= state.hero_incoming_count) return false;
    const int card = state.hero_incoming[incoming_index].value;
    if (!KnownPhysical(card) || pending[card]) return false;
    pending[card] = true;
    ++pending_count;
    if (!target[card] || target_row[card] != state.pending[i].row) return false;
  }
  if (pending_count != plan.target_count) return false;
  for (int card = 0; card < 54; ++card)
    if (target[card] != pending[card]) return false;
  return true;
}

bool NextRoundBoardCommitsPlan(
    const COFCState &before,
    const COFCState &after,
    const COFCTurnPlan &plan) {
  const COFCPlayerBoard &old_board = before.players[before.hero_chair].board;
  const COFCPlayerBoard &new_board = after.players[after.hero_chair].board;

  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    bool expected[54];
    bool actual[54];
    RowSet(old_board, static_cast<EOFCRow>(r), expected);
    RowSet(new_board, static_cast<EOFCRow>(r), actual);
    for (int i = 0; i < plan.target_count; ++i) {
      if (plan.target[i].row == static_cast<EOFCRow>(r)) {
        const int card = plan.target[i].card_value;
        if (!KnownPhysical(card) || expected[card]) return false;
        expected[card] = true;
      }
    }
    if (!SameBoolSet(expected, actual)) return false;
  }
  return true;
}

bool NextRoundDiscardsCommitPlan(
    const COFCState &before,
    const COFCState &after,
    const COFCTurnPlan &plan) {
  bool expected[54] = {false};
  bool actual[54] = {false};
  for (int i = 0; i < before.hero_discard_count; ++i) {
    const int card = before.hero_discards[i].value;
    if (!KnownPhysical(card)) return false;
    expected[card] = true;
  }
  if (before.round_index == 0) {
    if (plan.unused_count != 0) return false;
  } else {
    if (plan.unused_count != 1) return false;
    const int card = plan.unused_cards[0];
    if (!KnownPhysical(card) || expected[card]) return false;
    expected[card] = true;
  }
  for (int i = 0; i < after.hero_discard_count; ++i) {
    const int card = after.hero_discards[i].value;
    if (!KnownPhysical(card) || actual[card]) return false;
    actual[card] = true;
  }
  return SameBoolSet(expected, actual);
}

}  // namespace

bool COFCConfirmVerifier::VerifyNormalTransition(
    const COFCState &before,
    const COFCState &after,
    const COFCTurnPlan &plan,
    COFCConfirmReceipt *receipt,
    string *error) {
  if (receipt == NULL) return false;
  *receipt = COFCConfirmReceipt();
  if (error != NULL) error->clear();

  if (!before.valid || !after.valid || !plan.valid || !plan.decision_state.valid) {
    return Fail(receipt, error, "Confirm verification requires valid bound states/plan");
  }
  if (before.hero_chair < 0 || before.hero_chair >= before.player_count
      || after.hero_chair < 0 || after.hero_chair >= after.player_count) {
    return Fail(receipt, error, "invalid Hero chair across Confirm");
  }
  if (before.players[before.hero_chair].fantasy
      || after.players[after.hero_chair].fantasy) {
    return Fail(receipt, error,
      "normal Confirm verifier does not certify Fantasy transitions");
  }
  if (before.round_index < 0 || before.round_index > 3) {
    return Fail(receipt, error,
      "normal Confirm verifier currently certifies rounds 0..3 only");
  }
  if (before.player_count != after.player_count
      || before.hero_chair != after.hero_chair
      || before.dealer_chair != after.dealer_chair) {
    return Fail(receipt, error, "player/Hero/dealer mapping changed across Confirm");
  }
  if (!SameBoundDecision(plan.decision_state, before)) {
    return Fail(receipt, error, "pre-Confirm state no longer matches bound solver decision");
  }
  if (before.acting_chair != before.hero_chair
      || !before.hero_can_confirm
      || !before.action_required) {
    return Fail(receipt, error, "pre-Confirm state is not an actionable Hero Confirm");
  }
  if (!PendingExactlyMatchesPlan(before, plan)) {
    return Fail(receipt, error, "pre-Confirm pending placements do not exactly match solver plan");
  }

  if (after.round_index == before.round_index) {
    if (after.acting_chair == after.hero_chair) {
      return Fail(receipt, error, "same-round evidence still says Hero is acting");
    }
    if (after.hero_can_confirm || after.action_required) {
      return Fail(receipt, error, "same-round evidence still exposes Hero Confirm action");
    }
    if (!SameIncoming(before, after)) {
      return Fail(receipt, error, "same-round incoming physical-card set changed");
    }
    if (!SameBoard(
          before.players[before.hero_chair].board,
          after.players[after.hero_chair].board)) {
      return Fail(receipt, error,
        "committed Hero board changed before canonical round advancement");
    }
    if (!SameDiscards(before, after)) {
      return Fail(receipt, error,
        "Hero discard history changed before canonical round advancement");
    }
    if (!PendingExactlyMatchesPlan(after, plan)) {
      return Fail(receipt, error,
        "same-round target placements are not preserved exactly after Confirm");
    }

    receipt->accepted = true;
    receipt->transition = kOFCConfirmSameRoundHandoff;
    receipt->previous_round = before.round_index;
    receipt->observed_round = after.round_index;
    return true;
  }

  if (after.round_index == before.round_index + 1) {
    if (!NextRoundBoardCommitsPlan(before, after, plan)) {
      return Fail(receipt, error,
        "next-round canonical board does not commit solver targets exactly");
    }
    if (!NextRoundDiscardsCommitPlan(before, after, plan)) {
      return Fail(receipt, error,
        "next-round discard history does not commit prior unused card exactly");
    }
    if (after.hero_incoming_count != 3) {
      return Fail(receipt, error,
        "advanced normal round does not expose three new Hero incoming cards");
    }

    receipt->accepted = true;
    receipt->transition = kOFCConfirmNextRoundCommitted;
    receipt->previous_round = before.round_index;
    receipt->observed_round = after.round_index;
    return true;
  }

  return Fail(receipt, error,
    "post-Confirm state is neither same-round handoff nor one-round advancement");
}
