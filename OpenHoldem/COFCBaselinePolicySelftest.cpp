#include <iostream>
#include <string>

#include "COFCBaselinePolicy.h"

namespace {

int Card(int rank, int suit) {
  return (rank - 2) * 4 + suit;
}

COFCState BaseState(bool fantasy, int round) {
  COFCState state;
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.dealer_chair = 0;
  state.acting_chair = 1;
  state.round_index = round;
  state.hero_can_prepare = true;
  state.players[0].occupied = true;
  state.players[0].source_chair = 0;
  state.players[1].occupied = true;
  state.players[1].source_chair = 1;
  state.players[1].fantasy = fantasy;
  return state;
}

bool Fantasy15() {
  COFCState state = BaseState(true, -1);
  const int cards[15] = {
    Card(14,2), Card(14,0), Card(13,2), Card(11,3), Card(11,1),
    Card(10,0), Card(9,3), Card(9,0), Card(7,3), Card(6,3),
    Card(6,2), Card(5,2), Card(3,3), Card(3,0), Card(2,3)};
  state.hero_incoming_count = 15;
  for (int i = 0; i < 15; ++i) state.hero_incoming[i].value = cards[i];
  COFCStrategyAction action;
  std::string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    std::cerr << "Fantasy15 policy rejected: " << error << "\n";
    return false;
  }
  int rows[3] = {0, 0, 0};
  for (int i = 0; i < action.placement_count; ++i)
    ++rows[static_cast<int>(action.placements[i].row)];
  return action.valid && action.placement_count == 13
    && action.unused_count == 2
    && rows[0] == 3 && rows[1] == 5 && rows[2] == 5;
}

bool NormalOpening() {
  COFCState state = BaseState(false, 0);
  const int cards[5] = {
    Card(13,3), Card(8,0), Card(10,2), Card(6,2), Card(14,2)};
  state.hero_incoming_count = 5;
  for (int i = 0; i < 5; ++i) {
    state.hero_incoming[i].value = cards[i];
    state.pending[i].active = true;
    state.pending[i].incoming_index = i;
    state.pending[i].row = kOFCRowBottom;
  }
  COFCStrategyAction action;
  std::string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    std::cerr << "normal opening policy rejected: " << error << "\n";
    return false;
  }
  int rows[3] = {0, 0, 0};
  for (int i = 0; i < action.placement_count; ++i)
    ++rows[static_cast<int>(action.placements[i].row)];
  COFCTurnPlan plan;
  if (!COFCTurnPlanBuilder::Build(state, action, &plan, &error)) {
    std::cerr << "normal opening relocation plan rejected: " << error << "\n";
    return false;
  }
  return action.valid && action.placement_count == 5 && action.unused_count == 0
    && rows[0] == 1 && rows[1] == 2 && rows[2] == 2
    && plan.valid && plan.already_correct_count == 2 && plan.to_add_count == 3;
}

bool NormalRoundPreservesJoker() {
  COFCState state = BaseState(false, 1);
  state.players[1].board.top[0].value = Card(9, 0);
  state.players[1].board.middle[0].value = Card(8, 2);
  state.players[1].board.middle[1].value = Card(7, 2);
  state.players[1].board.bottom[0].value = Card(14, 3);
  state.players[1].board.bottom[1].value = Card(13, 3);
  const int cards[3] = {kOFCCardJoker1, Card(12, 3), Card(2, 0)};
  state.hero_incoming_count = 3;
  for (int i = 0; i < 3; ++i) state.hero_incoming[i].value = cards[i];
  COFCStrategyAction action;
  std::string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    std::cerr << "normal Joker round policy rejected: " << error << "\n";
    return false;
  }
  return action.valid && action.placement_count == 2
    && action.unused_count == 1
    && action.unused_cards[0] != kOFCCardJoker1;
}

bool Fantasy15DualJoker() {
  COFCState state = BaseState(true, -1);
  const int cards[15] = {
    kOFCCardJoker1, kOFCCardJoker2, Card(14,0), Card(13,1), Card(12,0),
    Card(12,1), Card(11,3), Card(9,3), Card(9,2), Card(7,3),
    Card(6,2), Card(4,3), Card(4,0), Card(3,3), Card(2,0)};
  state.hero_incoming_count = 15;
  for (int i = 0; i < 15; ++i) state.hero_incoming[i].value = cards[i];
  COFCStrategyAction action;
  std::string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    std::cerr << "dual-Joker Fantasy15 policy rejected: " << error << "\n";
    return false;
  }
  return action.valid && action.placement_count == 13 && action.unused_count == 2;
}

}  // namespace

int main() {
  if (!Fantasy15() || !Fantasy15DualJoker() || !NormalOpening()
      || !NormalRoundPreservesJoker()) return 1;
  std::cout << "DEEPOFC BASELINE POLICY: PASS\n";
  return 0;
}
