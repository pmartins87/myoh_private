//******************************************************************************
// OpenOFC v5.4.3H Fantasy Confirm safety contract.
//
// This is a pure semantic guard. It performs no mouse/TableMap I/O and is
// included into the materialized v5.4.3 runtime only after generic Fantasy
// fields (fantasy_card_count 14..17) exist.
//******************************************************************************

#ifndef INC_COFCFANTASYCONFIRMGUARD_H
#define INC_COFCFANTASYCONFIRMGUARD_H

#include <sstream>
#include <string>

#include "COFCTurnPlan.h"

class COFCFantasyConfirmGuard {
 public:
  static bool Validate(
      const COFCState &state,
      const COFCTurnPlan &plan,
      std::string *error) {
    if (error != NULL) error->clear();
    if (!state.valid || !plan.valid || !plan.decision_state.valid)
      return Fail(error, "invalid state/plan binding");
    if (state.hero_chair < 0 || state.hero_chair >= state.player_count)
      return Fail(error, "invalid Hero chair");
    if (!state.players[state.hero_chair].fantasy || state.round_index != -1)
      return Fail(error, "Confirm guard received non-Fantasy state");
    if (state.fantasy_card_count < 14 || state.fantasy_card_count > 17)
      return Fail(error, "Fantasy count is outside 14..17");
    if (state.hero_incoming_count != state.fantasy_card_count)
      return Fail(error, "incoming count does not equal Fantasy count");
    if (plan.target_count != 13)
      return Fail(error, "Fantasy Confirm requires exactly 13 target cards");
    if (plan.unused_count != state.fantasy_card_count - 13)
      return Fail(error, "unused-card count does not match Fantasy count minus 13");

    const COFCState &decision = plan.decision_state;
    if (decision.hero_chair != state.hero_chair
        || decision.player_count != state.player_count
        || decision.round_index != -1
        || !decision.players[decision.hero_chair].fantasy
        || !decision.decision_finalizable
        || decision.fantasy_card_count != state.fantasy_card_count
        || decision.hero_incoming_count != state.hero_incoming_count) {
      return Fail(error, "turn plan is not bound to this finalizable Fantasy deal shape");
    }

    bool incoming_present[kOFCCardJoker2 + 1] = {false};
    bool partition_seen[kOFCCardJoker2 + 1] = {false};
    int expected_row[kOFCCardJoker2 + 1];
    for (int i = 0; i <= kOFCCardJoker2; ++i)
      expected_row[i] = static_cast<int>(kOFCRowUndefined);

    for (int i = 0; i < state.hero_incoming_count; ++i) {
      const int value = state.hero_incoming[i].value;
      if (value < 0 || value > kOFCCardJoker2)
        return Fail(error, "Fantasy incoming card is not a known physical card");
      if (incoming_present[value])
        return Fail(error, "duplicate physical card in Fantasy incoming set");
      incoming_present[value] = true;
    }

    bool decision_present[kOFCCardJoker2 + 1] = {false};
    for (int i = 0; i < decision.hero_incoming_count; ++i) {
      const int value = decision.hero_incoming[i].value;
      if (value < 0 || value > kOFCCardJoker2 || decision_present[value])
        return Fail(error, "decision-state incoming identity set is invalid");
      decision_present[value] = true;
    }
    for (int value = 0; value <= kOFCCardJoker2; ++value) {
      if (decision_present[value] != incoming_present[value])
        return Fail(error, "turn plan incoming identities drifted before Confirm");
    }

    int target_row_counts[3] = {0, 0, 0};
    for (int i = 0; i < plan.target_count; ++i) {
      const int value = plan.target[i].card_value;
      const int row = static_cast<int>(plan.target[i].row);
      if (value < 0 || value > kOFCCardJoker2 || !incoming_present[value])
        return Fail(error, "Fantasy target card is not in current incoming set");
      if (row < static_cast<int>(kOFCRowTop)
          || row > static_cast<int>(kOFCRowBottom))
        return Fail(error, "Fantasy target has invalid row");
      if (partition_seen[value])
        return Fail(error, "Fantasy target/unused partition contains duplicate card");
      partition_seen[value] = true;
      expected_row[value] = row;
      ++target_row_counts[row];
    }
    if (target_row_counts[kOFCRowTop] != kOFCTopCards
        || target_row_counts[kOFCRowMiddle] != kOFCMiddleCards
        || target_row_counts[kOFCRowBottom] != kOFCBottomCards) {
      return Fail(error, "Fantasy target is not exact 3/5/5");
    }

    for (int i = 0; i < plan.unused_count; ++i) {
      const int value = plan.unused_cards[i];
      if (value < 0 || value > kOFCCardJoker2 || !incoming_present[value])
        return Fail(error, "Fantasy unused card is not in current incoming set");
      if (partition_seen[value])
        return Fail(error, "Fantasy target/unused partition contains duplicate card");
      partition_seen[value] = true;
    }
    for (int value = 0; value <= kOFCCardJoker2; ++value) {
      if (incoming_present[value] != partition_seen[value])
        return Fail(error, "Fantasy target/unused cards do not exactly partition the deal");
    }

    bool pending_incoming_index[kOFCMaxIncomingCards] = {false};
    int pending_row_counts[3] = {0, 0, 0};
    int pending_count = 0;
    for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
      if (!state.pending[i].active) continue;
      ++pending_count;
      const int incoming_index = state.pending[i].incoming_index;
      const int row = static_cast<int>(state.pending[i].row);
      if (incoming_index < 0 || incoming_index >= state.hero_incoming_count)
        return Fail(error, "Fantasy pending placement has invalid incoming index");
      if (pending_incoming_index[incoming_index])
        return Fail(error, "Fantasy pending placement duplicates an incoming index");
      pending_incoming_index[incoming_index] = true;
      if (row < static_cast<int>(kOFCRowTop)
          || row > static_cast<int>(kOFCRowBottom))
        return Fail(error, "Fantasy pending placement has invalid row");
      const int value = state.hero_incoming[incoming_index].value;
      if (value < 0 || value > kOFCCardJoker2
          || expected_row[value] == static_cast<int>(kOFCRowUndefined))
        return Fail(error, "unused/unexpected physical card is present on Fantasy board");
      if (expected_row[value] != row)
        return Fail(error, "Fantasy board row does not match bound target");
      ++pending_row_counts[row];
    }
    if (pending_count != 13)
      return Fail(error, "Fantasy Confirm requires exactly 13 independently observed placements");
    if (pending_row_counts[kOFCRowTop] != kOFCTopCards
        || pending_row_counts[kOFCRowMiddle] != kOFCMiddleCards
        || pending_row_counts[kOFCRowBottom] != kOFCBottomCards) {
      return Fail(error, "observed Fantasy board is not exact 3/5/5");
    }

    if (!state.hero_can_confirm || !state.action_required
        || !state.decision_finalizable
        || state.acting_chair != state.hero_chair) {
      return Fail(error, "canonical finalizable Hero Confirm authority is absent");
    }
    return true;
  }

 private:
  static bool Fail(std::string *error, const std::string &message) {
    if (error != NULL) *error = message;
    return false;
  }
};

#endif  // INC_COFCFANTASYCONFIRMGUARD_H
