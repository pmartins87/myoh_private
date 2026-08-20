//******************************************************************************
// OpenOFC v5.4.3 generic Fantasy state/policy regression.
// Built only after the v5.4.3 late patch has added fantasy_card_count.
//******************************************************************************

#include "COFCReconstructor.h"
#include "COFCBaselinePolicy.h"

#include <chrono>
#include <iostream>
#include <set>
#include <string>

namespace {

bool Require(bool condition, const char *message) {
  if (condition) return true;
  std::cerr << "FAIL: " << message << "\n";
  return false;
}

COFCVisualObservation FantasyCurrentScreen(int count, int arranged) {
  COFCVisualObservation obs;
  obs.Reset();
  obs.valid = true;
  obs.player_count = 2;
  obs.hero_chair = 1;
  obs.dealer_chair = 0;
  obs.dealer_known = true;
  obs.acting_chair = 1;
  obs.round_index = -1;
  obs.fantasy_card_count = count;
  obs.hero_can_prepare = true;
  obs.confirm_visible = false;
  for (int p = 0; p < 2; ++p) {
    obs.players[p].occupied = true;
    obs.players[p].source_chair = p;
    obs.players[p].fantasy = p == 1;
  }

  // Use deterministic unique standard physical-card IDs. Put up to five
  // current cards tentatively in the middle row and leave the rest loose.
  const int placed = arranged < 0 ? 0 : (arranged > 5 ? 5 : arranged);
  for (int i = 0; i < placed; ++i)
    obs.players[1].visual_board.middle[i].value = i;
  for (int i = placed; i < count; ++i) {
    const int loose = obs.hero_loose_count++;
    obs.hero_loose_cards[loose].value = i;
    obs.hero_loose_sources[loose].valid = true;
    obs.hero_loose_sources[loose].card_value = i;
    obs.hero_loose_sources[loose].rect.left = 20 + loose * 2;
    obs.hero_loose_sources[loose].rect.top = 650;
    obs.hero_loose_sources[loose].rect.right = 40 + loose * 2;
    obs.hero_loose_sources[loose].rect.bottom = 710;
  }
  return obs;
}

bool CheckPolicyCount(int count) {
  COFCVisualObservation obs = FantasyCurrentScreen(count, 5);
  COFCState state;
  std::string error;
  if (!COFCReconstructor::Reconstruct(obs, NULL, &state, &error)) {
    std::cerr << "reconstruct count=" << count << " error=" << error << "\n";
    return false;
  }
  if (state.fantasy_card_count != count || state.hero_incoming_count != count)
    return false;

  const auto started = std::chrono::steady_clock::now();
  COFCStrategyAction action;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    std::cerr << "policy count=" << count << " error=" << error << "\n";
    return false;
  }
  const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
    std::chrono::steady_clock::now() - started).count();

  if (!action.valid || action.placement_count != 13
      || action.unused_count != count - 13) return false;
  std::set<int> seen;
  for (int i = 0; i < action.placement_count; ++i) {
    if (!seen.insert(action.placements[i].card_value).second) return false;
  }
  for (int i = 0; i < action.unused_count; ++i) {
    if (!seen.insert(action.unused_cards[i]).second) return false;
  }
  if (static_cast<int>(seen.size()) != count) return false;
  std::cout << "GENERIC_FANTASY_POLICY count=" << count
            << " placements=13 unused=" << action.unused_count
            << " elapsed_ms=" << elapsed << " PASS\n";
  return true;
}

}  // namespace

int main() {
  bool ok = true;

  // Fresh process memory must not be needed even after some Fantasy cards were
  // already arranged on screen. This models reconnect into active Fantasy.
  for (int count = 14; count <= 17; ++count) {
    COFCVisualObservation obs = FantasyCurrentScreen(count, 5);
    COFCState state;
    std::string error;
    ok &= Require(COFCReconstructor::Reconstruct(obs, NULL, &state, &error),
      "fresh partial Fantasy current screen must reconstruct without lineage");
    ok &= Require(state.valid && state.fantasy_card_count == count,
      "canonical Fantasy count must equal current-screen count");
    ok &= Require(state.hero_incoming_count == count,
      "canonical incoming set must contain every current Fantasy physical card");
  }

  for (int count = 14; count <= 17; ++count)
    ok &= Require(CheckPolicyCount(count),
      "generic Fantasy policy must support every 14..17 count");

  COFCVisualObservation mismatch = FantasyCurrentScreen(15, 5);
  mismatch.fantasy_card_count = 14;
  COFCState rejected;
  std::string error;
  ok &= Require(!COFCReconstructor::Reconstruct(mismatch, NULL, &rejected, &error),
    "Fantasy count mismatch must fail closed");

  if (!ok) return 1;
  std::cout << "PASS OpenOFC v5.4.3 generic Fantasy: current-screen bootstrap + 14/15/16/17 policy\n";
  return 0;
}
