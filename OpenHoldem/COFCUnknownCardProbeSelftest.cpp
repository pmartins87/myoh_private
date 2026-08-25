//******************************************************************************
// Standalone regression for active UNKNOWN-card recovery semantics.
//******************************************************************************

#include "COFCUnknownCardProbe.h"
#include "COFCIdentityRecoveryCache.h"

#include <iostream>
#include <string>
#include <vector>

using namespace std;

namespace {

bool Expect(bool condition, const char *message) {
  if (!condition) cerr << "FAIL: " << message << endl;
  return condition;
}

void InitNormal(COFCState *state, COFCVisualObservation *obs) {
  state->Reset(); obs->Reset();
  state->valid = true; state->player_count = 2; state->hero_chair = 1;
  state->round_index = 0; state->players[1].occupied = true;
  state->hero_incoming_count = 5;
  const int cards[5] = {0, 1, 2, 3, kOFCCardUnknown};
  obs->valid = true; obs->player_count = 2; obs->hero_chair = 1;
  obs->round_index = 0; obs->players[1].occupied = true;
  obs->hero_loose_count = 5;
  for (int i = 0; i < 5; ++i) {
    state->hero_incoming[i].value = cards[i];
    obs->hero_loose_cards[i].value = cards[i];
    obs->hero_loose_sources[i].valid = true;
    obs->hero_loose_sources[i].card_value = cards[i];
    obs->hero_loose_sources[i].rect.left = 10 + i * 10;
    obs->hero_loose_sources[i].rect.top = 10;
    obs->hero_loose_sources[i].rect.right = 18 + i * 10;
    obs->hero_loose_sources[i].rect.bottom = 30;
  }
}

}  // namespace

int main() {
  bool ok = true;
  COFCState before;
  COFCVisualObservation obs;
  InitNormal(&before, &obs);
  COFCUnknownCardProbe probe;
  string error;
  ok &= Expect(probe.BeginNormal(
      before, obs, kOFCRowTop, obs.hero_loose_sources[4].rect, &error),
      "normal probe must arm on one exact UNKNOWN source");

  COFCState after = before;
  COFCVisualObservation after_obs = obs;
  after.hero_incoming[4].value = 10;
  after_obs.hero_loose_count = 4;
  after_obs.players[1].visual_board.top[0].value = 10;
  int resolved = kOFCCardNoCard;
  string event;
  ok &= Expect(probe.ObservePlacement(
      after, after_obs, 8, &resolved, &event),
      "fresh normal placement must resolve by unique set difference");
  ok &= Expect(resolved == 10 && probe.phase() == COFCUnknownCardProbe::kComplete,
      "normal recovered identity/phase mismatch");

  COFCIdentityRecoveryCache cache;
  vector<int> full;
  for (int i = 0; i < 15; ++i) full.push_back(i);
  ok &= Expect(cache.RememberFantasySet(15, full, 7, &error),
      "Fantasy exact set must arm cache");
  vector<int> unread = full;
  unread[7] = kOFCCardUnknown;
  vector<int> completed;
  resolved = kOFCCardNoCard;
  ok &= Expect(cache.CompleteOneUnknown(
      15, unread, &completed, &resolved, &error),
      "one unread fan card must complete by exact set subtraction");
  ok &= Expect(completed == full && resolved == 7,
      "Fantasy exact-set completion produced wrong identity");

  unread[6] = kOFCCardUnknown;
  ok &= Expect(!cache.CompleteOneUnknown(
      15, unread, &completed, &resolved, &error),
      "two unread Fantasy cards must remain fail-closed");

  if (!ok) return 1;
  cout << "OPENOFC_V580_NORMAL_UNIQUE_DELTA=PASS" << endl
       << "OPENOFC_V580_FANTASY_EXACT_COMPLEMENT=PASS" << endl
       << "OPENOFC_V580_MULTI_UNKNOWN_FAIL_CLOSED=PASS" << endl;
  return 0;
}
