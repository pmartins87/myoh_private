//******************************************************************************
// OpenOFC reversible UNKNOWN-card probe state machine.
//******************************************************************************

#ifndef DEEPOFC_IDENTITY_RECOVERY_STANDALONE
#include "StdAfx.h"
#endif
#include "COFCUnknownCardProbe.h"

#include <cstddef>
#include <sstream>

using namespace std;

namespace {

bool UsableRect(const RECT &rect) {
  return rect.right > rect.left && rect.bottom > rect.top;
}

void CollectBoard(const COFCPlayerBoard &board, set<int> *values) {
  if (values == NULL) return;
  for (int i = 0; i < kOFCTopCards; ++i)
    if (board.top[i].IsKnownPhysicalCard()) values->insert(board.top[i].value);
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (board.middle[i].IsKnownPhysicalCard()) values->insert(board.middle[i].value);
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (board.bottom[i].IsKnownPhysicalCard()) values->insert(board.bottom[i].value);
}

}  // namespace

COFCUnknownCardProbe::COFCUnknownCardProbe() {
  Reset();
}

void COFCUnknownCardProbe::Reset() {
  phase_ = kIdle;
  fantasy_ = false;
  staging_row_ = kOFCRowUndefined;
  source_rect_.left = source_rect_.top = 0;
  source_rect_.right = source_rect_.bottom = 0;
  fantasy_card_count_ = 0;
  wait_cycles_ = 0;
  resolved_card_ = kOFCCardNoCard;
  known_before_.clear();
  failure_reason_.clear();
}

void COFCUnknownCardProbe::CollectKnown(
    const COFCState &state,
    const COFCVisualObservation &observation,
    set<int> *values) {
  if (values == NULL) return;
  values->clear();
  if (state.valid && state.hero_chair >= 0
      && state.hero_chair < state.player_count) {
    CollectBoard(state.players[state.hero_chair].board, values);
    for (int i = 0; i < state.hero_incoming_count; ++i)
      if (state.hero_incoming[i].IsKnownPhysicalCard())
        values->insert(state.hero_incoming[i].value);
  }
  if (observation.hero_chair >= 0
      && observation.hero_chair < observation.player_count) {
    CollectBoard(
      observation.players[observation.hero_chair].visual_board, values);
    for (int i = 0; i < observation.hero_loose_count; ++i)
      if (observation.hero_loose_cards[i].IsKnownPhysicalCard())
        values->insert(observation.hero_loose_cards[i].value);
  }
}

void COFCUnknownCardProbe::CollectVisualRowKnown(
    const COFCVisualObservation &observation,
    EOFCRow row,
    set<int> *values) {
  if (values == NULL) return;
  values->clear();
  if (observation.hero_chair < 0
      || observation.hero_chair >= observation.player_count) return;
  const COFCPlayerBoard &board =
    observation.players[observation.hero_chair].visual_board;
  const COFCCard *cards = NULL;
  int count = 0;
  if (row == kOFCRowTop) { cards = board.top; count = kOFCTopCards; }
  else if (row == kOFCRowMiddle) { cards = board.middle; count = kOFCMiddleCards; }
  else if (row == kOFCRowBottom) { cards = board.bottom; count = kOFCBottomCards; }
  if (cards == NULL) return;
  for (int i = 0; i < count; ++i)
    if (cards[i].IsKnownPhysicalCard()) values->insert(cards[i].value);
}

bool COFCUnknownCardProbe::BeginNormal(
    const COFCState &state,
    const COFCVisualObservation &observation,
    EOFCRow staging_row,
    const RECT &source_rect,
    string *error) {
  Reset();
  if (!state.valid || !observation.valid || !UsableRect(source_rect)
      || staging_row < kOFCRowTop || staging_row > kOFCRowBottom) {
    if (error != NULL) *error = "normal identity probe precondition failed";
    return false;
  }
  fantasy_ = false;
  staging_row_ = staging_row;
  source_rect_ = source_rect;
  CollectKnown(state, observation, &known_before_);
  phase_ = kAwaitNormalPlacement;
  if (error != NULL) error->clear();
  return true;
}

bool COFCUnknownCardProbe::BeginFantasy(
    const COFCVisualObservation &observation,
    EOFCRow staging_row,
    string *error) {
  Reset();
  const COFCIdentityProbeEvidence &evidence = observation.identity_probe;
  if (!evidence.candidate_available
      || evidence.fantasy_card_count < 14
      || evidence.fantasy_card_count > 17
      || !evidence.candidate_source.valid
      || !UsableRect(evidence.candidate_source.rect)
      || staging_row < kOFCRowTop || staging_row > kOFCRowBottom) {
    if (error != NULL) *error = "Fantasy identity probe evidence is incomplete";
    return false;
  }
  fantasy_ = true;
  staging_row_ = staging_row;
  source_rect_ = evidence.candidate_source.rect;
  fantasy_card_count_ = evidence.fantasy_card_count;
  for (int i = 0; i < evidence.known_count; ++i)
    if (evidence.known_values[i] >= 0)
      known_before_.insert(evidence.known_values[i]);
  phase_ = kAwaitFantasyPlacement;
  if (error != NULL) error->clear();
  return true;
}

bool COFCUnknownCardProbe::ObserveUniqueDelta(
    const COFCState &state,
    const COFCVisualObservation &observation,
    int *resolved_card,
    string *event) {
  set<int> row;
  CollectVisualRowKnown(observation, staging_row_, &row);
  set<int> all;
  CollectKnown(state, observation, &all);
  int candidate = kOFCCardNoCard;
  int candidates = 0;
  for (set<int>::const_iterator it = row.begin(); it != row.end(); ++it) {
    if (known_before_.find(*it) != known_before_.end()) continue;
    if (all.find(*it) == all.end()) continue;
    candidate = *it;
    ++candidates;
  }
  if (candidates != 1) return false;
  resolved_card_ = candidate;
  if (resolved_card != NULL) *resolved_card = candidate;
  if (event != NULL) *event = "UNIQUE_BOARD_SET_DIFFERENCE";
  return true;
}

bool COFCUnknownCardProbe::ObservePlacement(
    const COFCState &state,
    const COFCVisualObservation &observation,
    int maximum_wait_cycles,
    int *resolved_card,
    string *event) {
  if (resolved_card != NULL) *resolved_card = kOFCCardNoCard;
  if (event != NULL) event->clear();
  if (phase_ != kAwaitNormalPlacement
      && phase_ != kAwaitFantasyPlacement) return false;
  if (state.valid && observation.valid
      && ObserveUniqueDelta(state, observation, resolved_card, event)) {
    if (fantasy_) {
      // The runtime sends the reversible row-X only after this exact proof.
      return true;
    }
    phase_ = kComplete;
    return true;
  }
  ++wait_cycles_;
  if (wait_cycles_ >= maximum_wait_cycles) {
    Fail("identity probe placement was not observed within bounded window");
    if (event != NULL) *event = failure_reason_;
  } else if (event != NULL) {
    ostringstream out;
    out << "WAIT_FRESH_PLACEMENT " << wait_cycles_
        << "/" << maximum_wait_cycles;
    *event = out.str();
  }
  return false;
}

void COFCUnknownCardProbe::MarkFantasyClearSent() {
  if (phase_ == kAwaitFantasyPlacement && resolved_card_ >= 0) {
    phase_ = kAwaitFantasyClear;
    wait_cycles_ = 0;
  }
}

bool COFCUnknownCardProbe::ObserveFantasyClear(
    const COFCVisualObservation &observation,
    int maximum_wait_cycles,
    string *event) {
  if (event != NULL) event->clear();
  if (phase_ != kAwaitFantasyClear) return false;
  set<int> row;
  CollectVisualRowKnown(observation, staging_row_, &row);
  if (observation.valid && row.empty()
      && observation.fantasy_card_count == fantasy_card_count_) {
    phase_ = kComplete;
    if (event != NULL) *event = "FANTASY_ROW_CLEAR_VERIFIED";
    return true;
  }
  ++wait_cycles_;
  if (wait_cycles_ >= maximum_wait_cycles) {
    Fail("Fantasy diagnostic row clear was not observed within bounded window");
    if (event != NULL) *event = failure_reason_;
  } else if (event != NULL) {
    ostringstream out;
    out << "WAIT_FRESH_CLEAR " << wait_cycles_
        << "/" << maximum_wait_cycles;
    *event = out.str();
  }
  return false;
}

void COFCUnknownCardProbe::Fail(const string &reason) {
  phase_ = kFailed;
  failure_reason_ = reason;
}
