//******************************************************************************
// OpenOFC v5.4.3H pure Fantasy Confirm semantic selftest.
//******************************************************************************

#include <cstdlib>
#include <iostream>
#include <string>

#include "COFCFantasyConfirmGuard.h"

namespace {

const int kDeal17[17] = {
  kOFCCardJoker1, kOFCCardJoker2,
  0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
};

void Require(bool condition, const std::string &message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(2);
  }
}

EOFCRow TargetRow(int target_ordinal) {
  // Keep the physical Jokers in different rows so identity/row binding is
  // independently observable: JK1 -> top, JK2 -> middle.
  if (target_ordinal == 0) return kOFCRowTop;      // JK1
  if (target_ordinal == 1) return kOFCRowMiddle;   // JK2
  if (target_ordinal <= 2) return kOFCRowTop;      // card 0
  if (target_ordinal == 3) return kOFCRowTop;      // card 1
  if (target_ordinal <= 7) return kOFCRowMiddle;   // cards 2..5
  return kOFCRowBottom;                            // cards 6..10
}

COFCState MakeState(int count, bool arranged) {
  COFCState state;
  state.Reset();
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.dealer_chair = 0;
  state.acting_chair = 1;
  state.round_index = -1;
  state.fantasy_card_count = count;
  state.hero_can_prepare = true;
  state.hero_can_confirm = true;
  state.action_required = true;
  state.players[0].occupied = true;
  state.players[0].source_chair = 0;
  state.players[1].occupied = true;
  state.players[1].source_chair = 1;
  state.players[1].fantasy = true;
  state.hero_incoming_count = count;
  for (int i = 0; i < count; ++i) state.hero_incoming[i].value = kDeal17[i];
  if (arranged) {
    for (int i = 0; i < 13; ++i) {
      state.pending[i].active = true;
      state.pending[i].incoming_index = i;
      state.pending[i].row = TargetRow(i);
    }
  }
  return state;
}

COFCTurnPlan MakePlan(int count) {
  COFCTurnPlan plan;
  plan.Reset();
  plan.valid = true;
  plan.decision_state = MakeState(count, false);
  plan.decision_state.hero_can_confirm = false;
  plan.decision_state.action_required = false;
  plan.target_count = 13;
  plan.to_add_count = 13;
  for (int i = 0; i < 13; ++i) {
    plan.target[i].card_value = kDeal17[i];
    plan.target[i].row = TargetRow(i);
    plan.to_add[i] = plan.target[i];
  }
  plan.unused_count = count - 13;
  for (int i = 13; i < count; ++i)
    plan.unused_cards[i - 13] = kDeal17[i];
  return plan;
}

void ExpectReject(
    const COFCState &state,
    const COFCTurnPlan &plan,
    const std::string &needle) {
  std::string error;
  Require(!COFCFantasyConfirmGuard::Validate(state, plan, &error),
    "negative Confirm case was accepted");
  Require(error.find(needle) != std::string::npos,
    "negative Confirm case reported unexpected reason: " + error);
}

void TestAllFantasyCounts() {
  for (int count = 14; count <= 17; ++count) {
    COFCState state = MakeState(count, true);
    COFCTurnPlan plan = MakePlan(count);
    std::string error;
    Require(COFCFantasyConfirmGuard::Validate(state, plan, &error),
      "valid Fantasy Confirm rejected for count=" + std::to_string(count)
        + " reason=" + error);
  }
  std::cout << "FANTASY_CONFIRM_14_17_GATE=PASS" << std::endl;
}

void TestExactBoardAndJokerBinding() {
  COFCState missing = MakeState(15, true);
  missing.pending[12].Reset();
  ExpectReject(missing, MakePlan(15), "exactly 13");

  COFCState wrong_joker_row = MakeState(15, true);
  wrong_joker_row.pending[1].row = kOFCRowTop;  // JK2 target is middle.
  ExpectReject(wrong_joker_row, MakePlan(15), "does not match bound target");

  COFCState duplicate_index = MakeState(15, true);
  duplicate_index.pending[12].incoming_index = 11;
  ExpectReject(duplicate_index, MakePlan(15), "duplicates an incoming index");

  COFCState unused_on_board = MakeState(15, true);
  unused_on_board.pending[12].incoming_index = 13;
  ExpectReject(unused_on_board, MakePlan(15), "unused/unexpected");

  std::cout << "FANTASY_CONFIRM_EXACT_3_5_5_GATE=PASS" << std::endl;
  std::cout << "FANTASY_CONFIRM_JOKER_IDENTITY_GATE=PASS" << std::endl;
}

void TestPlanBindingAndAuthority() {
  COFCState state = MakeState(16, true);
  COFCTurnPlan stale = MakePlan(16);
  stale.decision_state.hero_incoming[15].value = 20;
  ExpectReject(state, stale, "identities drifted");

  COFCState no_authority = MakeState(16, true);
  no_authority.hero_can_confirm = false;
  ExpectReject(no_authority, MakePlan(16), "authority is absent");

  COFCState wrong_actor = MakeState(16, true);
  wrong_actor.acting_chair = 0;
  ExpectReject(wrong_actor, MakePlan(16), "authority is absent");

  COFCTurnPlan wrong_unused = MakePlan(16);
  wrong_unused.unused_count = 2;
  ExpectReject(state, wrong_unused, "unused-card count");

  std::cout << "FANTASY_CONFIRM_PLAN_BINDING_GATE=PASS" << std::endl;
  std::cout << "FANTASY_CONFIRM_AUTHORITY_GATE=PASS" << std::endl;
}

}  // namespace

int main() {
  TestAllFantasyCounts();
  TestExactBoardAndJokerBinding();
  TestPlanBindingAndAuthority();
  std::cout << "FANTASY_CONFIRM_SEMANTIC_GUARD=PASS" << std::endl;
  std::cout << "FIELD_PACKAGE_AUTHORIZED=0" << std::endl;
  return 0;
}
