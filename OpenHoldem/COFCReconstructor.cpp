//******************************************************************************
//
// DeepOFC stateful raw-observation -> canonical-state reconstructor.
//
// Ported from the independent DeepOFC Python reference. The implementation is
// intentionally conservative: ambiguity invalidates the canonical state.
//
//******************************************************************************

#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
#include "StdAfx.h"
#endif
#include "COFCReconstructor.h"

#include <algorithm>
#include <set>
#include <sstream>
#include <vector>

using namespace std;

namespace {

bool Fail(COFCState *out, string *error, const string &message) {
  if (out != NULL) {
    out->Reset();
  }
  if (error != NULL) {
    *error = message;
  }
  return false;
}

int RowCapacity(EOFCRow row) {
  switch (row) {
    case kOFCRowTop: return kOFCTopCards;
    case kOFCRowMiddle: return kOFCMiddleCards;
    case kOFCRowBottom: return kOFCBottomCards;
    default: return 0;
  }
}

const COFCCard *RowCards(const COFCPlayerBoard &board, EOFCRow row, int *count) {
  switch (row) {
    case kOFCRowTop:
      *count = kOFCTopCards;
      return board.top;
    case kOFCRowMiddle:
      *count = kOFCMiddleCards;
      return board.middle;
    case kOFCRowBottom:
      *count = kOFCBottomCards;
      return board.bottom;
    default:
      *count = 0;
      return NULL;
  }
}

COFCCard *MutableRowCards(COFCPlayerBoard *board, EOFCRow row, int *count) {
  switch (row) {
    case kOFCRowTop:
      *count = kOFCTopCards;
      return board->top;
    case kOFCRowMiddle:
      *count = kOFCMiddleCards;
      return board->middle;
    case kOFCRowBottom:
      *count = kOFCBottomCards;
      return board->bottom;
    default:
      *count = 0;
      return NULL;
  }
}

vector<int> KnownRowValues(const COFCPlayerBoard &board, EOFCRow row) {
  vector<int> values;
  int count = 0;
  const COFCCard *cards = RowCards(board, row, &count);
  for (int i = 0; i < count; ++i) {
    if (cards[i].IsKnownPhysicalCard()) {
      values.push_back(cards[i].value);
    }
  }
  return values;
}

set<int> KnownBoardSet(const COFCPlayerBoard &board) {
  set<int> values;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    vector<int> row = KnownRowValues(board, static_cast<EOFCRow>(r));
    values.insert(row.begin(), row.end());
  }
  return values;
}

bool ContainsInRow(const COFCPlayerBoard &board, EOFCRow row, int value) {
  int count = 0;
  const COFCCard *cards = RowCards(board, row, &count);
  for (int i = 0; i < count; ++i) {
    if (cards[i].IsKnownPhysicalCard() && cards[i].value == value) {
      return true;
    }
  }
  return false;
}

bool FindUniqueVisualRow(const COFCPlayerBoard &board, int value, EOFCRow *row) {
  int matches = 0;
  EOFCRow found = kOFCRowUndefined;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow candidate = static_cast<EOFCRow>(r);
    if (ContainsInRow(board, candidate, value)) {
      ++matches;
      found = candidate;
    }
  }
  if (matches != 1) {
    return false;
  }
  *row = found;
  return true;
}

bool NormalizeBoard(const COFCPlayerBoard &source, COFCPlayerBoard *out, string *error) {
  out->Reset();
  set<int> board_seen;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow row = static_cast<EOFCRow>(r);
    vector<int> values = KnownRowValues(source, row);
    sort(values.begin(), values.end());
    if (static_cast<int>(values.size()) > RowCapacity(row)) {
      if (error != NULL) *error = "row exceeds 3/5/5 capacity";
      return false;
    }
    int count = 0;
    COFCCard *target = MutableRowCards(out, row, &count);
    for (size_t i = 0; i < values.size(); ++i) {
      if (!board_seen.insert(values[i]).second) {
        if (error != NULL) *error = "duplicate physical card inside board";
        return false;
      }
      target[i].value = values[i];
    }
  }
  return true;
}

bool BuildBoardFromMembership(
    const set<int> &top,
    const set<int> &middle,
    const set<int> &bottom,
    COFCPlayerBoard *out,
    string *error) {
  COFCPlayerBoard source;
  source.Reset();
  const set<int> *sets[3] = {&top, &middle, &bottom};
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow row = static_cast<EOFCRow>(r);
    if (static_cast<int>(sets[r]->size()) > RowCapacity(row)) {
      if (error != NULL) *error = "committed row exceeds capacity";
      return false;
    }
    int count = 0;
    COFCCard *target = MutableRowCards(&source, row, &count);
    int i = 0;
    for (set<int>::const_iterator it = sets[r]->begin(); it != sets[r]->end(); ++it, ++i) {
      target[i].value = *it;
    }
  }
  return NormalizeBoard(source, out, error);
}

bool EnsureCommittedStillVisible(
    const COFCPlayerBoard &committed,
    const COFCPlayerBoard &visual,
    const char *who,
    string *error) {
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow row = static_cast<EOFCRow>(r);
    vector<int> old_values = KnownRowValues(committed, row);
    for (size_t i = 0; i < old_values.size(); ++i) {
      if (!ContainsInRow(visual, row, old_values[i])) {
        ostringstream oss;
        oss << who << " committed card moved/disappeared: value="
            << old_values[i] << " row=" << r;
        if (error != NULL) *error = oss.str();
        return false;
      }
    }
  }
  return true;
}

set<int> CardArraySet(const COFCCard *cards, int count) {
  set<int> out;
  for (int i = 0; i < count; ++i) {
    if (cards[i].IsKnownPhysicalCard()) {
      out.insert(cards[i].value);
    }
  }
  return out;
}

bool IsSubset(const set<int> &a, const set<int> &b) {
  for (set<int>::const_iterator it = a.begin(); it != a.end(); ++it) {
    if (b.find(*it) == b.end()) return false;
  }
  return true;
}

set<int> Difference(const set<int> &a, const set<int> &b) {
  set<int> out;
  for (set<int>::const_iterator it = a.begin(); it != a.end(); ++it) {
    if (b.find(*it) == b.end()) out.insert(*it);
  }
  return out;
}

bool IsJokerValue(int value) {
  return value == kOFCCardJoker1 || value == kOFCCardJoker2;
}

int SwappedJokerValue(int value) {
  if (value == kOFCCardJoker1) return kOFCCardJoker2;
  if (value == kOFCCardJoker2) return kOFCCardJoker1;
  return value;
}

void SwapJoker(COFCCard *card) {
  if (card->IsJoker()) card->value = SwappedJokerValue(card->value);
}

void SwapJokersInBoard(COFCPlayerBoard *board) {
  for (int i = 0; i < kOFCTopCards; ++i) SwapJoker(&board->top[i]);
  for (int i = 0; i < kOFCMiddleCards; ++i) SwapJoker(&board->middle[i]);
  for (int i = 0; i < kOFCBottomCards; ++i) SwapJoker(&board->bottom[i]);
}

void SwapJokersInObservation(COFCVisualObservation *observation) {
  for (int p = 0; p < observation->player_count; ++p) {
    SwapJokersInBoard(&observation->players[p].visual_board);
  }
  for (int i = 0; i < observation->hero_loose_count; ++i) {
    SwapJoker(&observation->hero_loose_cards[i]);
  }
  for (int i = 0; i < observation->hero_discard_tracker_count; ++i) {
    SwapJoker(&observation->hero_discard_tracker[i]);
  }
}

bool ObservationContainsHeroCardAnywhere(const COFCVisualObservation &obs, int value) {
  const COFCPlayerBoard &visual = obs.players[obs.hero_chair].visual_board;
  set<int> visual_cards = KnownBoardSet(visual);
  if (visual_cards.find(value) != visual_cards.end()) return true;
  for (int i = 0; i < obs.hero_loose_count; ++i) {
    if (obs.hero_loose_cards[i].IsKnownPhysicalCard() && obs.hero_loose_cards[i].value == value) return true;
  }
  for (int i = 0; i < obs.hero_discard_tracker_count; ++i) {
    if (obs.hero_discard_tracker[i].IsKnownPhysicalCard() && obs.hero_discard_tracker[i].value == value) return true;
  }
  return false;
}

int JokerPersistenceScore(const COFCVisualObservation &obs, const COFCState &previous) {
  int score = 0;
  for (int p = 0; p < previous.player_count; ++p) {
    const COFCPlayerBoard &old_board = previous.players[p].board;
    const COFCPlayerBoard &visual = obs.players[p].visual_board;
    for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
      EOFCRow row = static_cast<EOFCRow>(r);
      vector<int> old_values = KnownRowValues(old_board, row);
      for (size_t i = 0; i < old_values.size(); ++i) {
        if (IsJokerValue(old_values[i]) && ContainsInRow(visual, row, old_values[i])) {
          score += 8;
        }
      }
    }
  }
  for (int i = 0; i < previous.hero_discard_count; ++i) {
    int value = previous.hero_discards[i].value;
    if (!IsJokerValue(value)) continue;
    for (int j = 0; j < obs.hero_discard_tracker_count; ++j) {
      if (obs.hero_discard_tracker[j].value == value) score += 6;
    }
  }
  for (int i = 0; i < previous.hero_incoming_count; ++i) {
    int value = previous.hero_incoming[i].value;
    if (IsJokerValue(value) && ObservationContainsHeroCardAnywhere(obs, value)) score += 4;
  }
  return score;
}

void NormalizeJokerOccurrenceLabels(
    COFCVisualObservation *observation,
    const COFCState *previous) {
  if (previous == NULL || !previous->valid) return;
  int identity_score = JokerPersistenceScore(*observation, *previous);
  COFCVisualObservation swapped = *observation;
  SwapJokersInObservation(&swapped);
  int swapped_score = JokerPersistenceScore(swapped, *previous);
  if (swapped_score > identity_score) {
    *observation = swapped;
  }
}

bool ValidateObservationKnownCardUniqueness(
    const COFCVisualObservation &obs,
    string *error) {
  set<int> seen;
  for (int p = 0; p < obs.player_count; ++p) {
    for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
      vector<int> row = KnownRowValues(obs.players[p].visual_board, static_cast<EOFCRow>(r));
      for (size_t i = 0; i < row.size(); ++i) {
        if (!seen.insert(row[i]).second) {
          if (error != NULL) *error = "duplicate physical card in raw visual observation";
          return false;
        }
      }
    }
  }
  for (int i = 0; i < obs.hero_loose_count; ++i) {
    if (!obs.hero_loose_cards[i].IsKnownPhysicalCard()) continue;
    if (!seen.insert(obs.hero_loose_cards[i].value).second) {
      if (error != NULL) *error = "Hero card appears both loose and elsewhere";
      return false;
    }
  }
  for (int i = 0; i < obs.hero_discard_tracker_count; ++i) {
    if (!obs.hero_discard_tracker[i].IsKnownPhysicalCard()) continue;
    if (!seen.insert(obs.hero_discard_tracker[i].value).second) {
      if (error != NULL) *error = "Hero discard duplicates another visible physical card";
      return false;
    }
  }
  return true;
}

bool ValidateCanonicalKnownCardUniqueness(const COFCState &state, string *error) {
  set<int> seen;
  for (int p = 0; p < state.player_count; ++p) {
    set<int> board = KnownBoardSet(state.players[p].board);
    for (set<int>::const_iterator it = board.begin(); it != board.end(); ++it) {
      if (!seen.insert(*it).second) {
        if (error != NULL) *error = "duplicate physical card across canonical boards";
        return false;
      }
    }
  }
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    if (!state.hero_incoming[i].IsKnownPhysicalCard()) continue;
    if (!seen.insert(state.hero_incoming[i].value).second) {
      if (error != NULL) *error = "canonical Hero incoming duplicates committed/visible card";
      return false;
    }
  }
  for (int i = 0; i < state.hero_discard_count; ++i) {
    if (!state.hero_discards[i].IsKnownPhysicalCard()) continue;
    if (!seen.insert(state.hero_discards[i].value).second) {
      if (error != NULL) *error = "canonical Hero discard duplicates another physical card";
      return false;
    }
  }
  return true;
}

void CopySortedValuesToCards(const set<int> &values, COFCCard *cards, int max_count, int *count) {
  *count = 0;
  for (set<int>::const_iterator it = values.begin(); it != values.end(); ++it) {
    if (*count >= max_count) return;
    cards[*count].value = *it;
    ++(*count);
  }
}

string BoolJson(bool value) {
  return value ? "true" : "false";
}

string RowJson(const COFCPlayerBoard &board, EOFCRow row) {
  vector<int> values = KnownRowValues(board, row);
  sort(values.begin(), values.end());
  ostringstream oss;
  oss << "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i != 0) oss << ",";
    oss << values[i];
  }
  oss << "]";
  return oss.str();
}

string CardsJson(const COFCCard *cards, int count) {
  vector<int> values;
  for (int i = 0; i < count; ++i) {
    if (cards[i].IsKnownPhysicalCard()) values.push_back(cards[i].value);
  }
  sort(values.begin(), values.end());
  ostringstream oss;
  oss << "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i != 0) oss << ",";
    oss << values[i];
  }
  oss << "]";
  return oss.str();
}

}  // namespace

bool COFCReconstructor::Reconstruct(
    const COFCVisualObservation &input_observation,
    const COFCState *previous,
    COFCState *out,
    string *error) {
  if (out == NULL) return false;
  out->Reset();
  if (error != NULL) error->clear();

  if (!input_observation.valid) {
    return Fail(out, error, "raw observation is invalid");
  }

  COFCVisualObservation observation = input_observation;
  NormalizeJokerOccurrenceLabels(&observation, previous);

  if ((observation.player_count != 2 && observation.player_count != 3)
      || observation.hero_chair < 0
      || observation.hero_chair >= observation.player_count
      || observation.dealer_chair < 0
      || observation.dealer_chair >= observation.player_count
      || observation.acting_chair < 0
      || observation.acting_chair >= observation.player_count
      || observation.round_index < 0
      || observation.round_index > 4) {
    return Fail(out, error, "raw observation has invalid player/chair/round metadata");
  }
  for (int p = 0; p < observation.player_count; ++p) {
    if (!observation.players[p].occupied || observation.players[p].source_chair != p) {
      return Fail(out, error, "raw observation chair mapping is incomplete/inconsistent");
    }
  }
  string validation_error;
  if (!ValidateObservationKnownCardUniqueness(observation, &validation_error)) {
    return Fail(out, error, validation_error);
  }

  COFCPlayerBoard hero_committed;
  hero_committed.Reset();

  if (previous == NULL || !previous->valid) {
    if (observation.round_index != 0) {
      return Fail(out, error,
        "mid-hand observation requires prior canonical state to distinguish committed/pending Hero cards");
    }
  } else {
    if (previous->player_count != observation.player_count) {
      return Fail(out, error, "player count changed inside hand");
    }
    if (previous->hero_chair != observation.hero_chair) {
      return Fail(out, error, "Hero chair changed inside hand");
    }
    if (previous->dealer_chair != observation.dealer_chair) {
      return Fail(out, error, "dealer chair changed inside hand");
    }
    if (observation.round_index < previous->round_index) {
      return Fail(out, error, "round moved backwards");
    }
    if (observation.round_index > previous->round_index + 1) {
      return Fail(out, error, "skipped more than one round between observations");
    }

    const COFCPlayerBoard &hero_visual = observation.players[observation.hero_chair].visual_board;
    if (observation.round_index == previous->round_index) {
      hero_committed = previous->players[previous->hero_chair].board;
      if (!EnsureCommittedStillVisible(hero_committed, hero_visual, "Hero", &validation_error)) {
        return Fail(out, error, validation_error);
      }
    } else {
      const COFCPlayerBoard &old_board = previous->players[previous->hero_chair].board;
      if (!EnsureCommittedStillVisible(old_board, hero_visual, "Hero", &validation_error)) {
        return Fail(out, error, validation_error);
      }

      set<int> old_discards = CardArraySet(previous->hero_discards, previous->hero_discard_count);
      set<int> new_tracker = CardArraySet(
        observation.hero_discard_tracker, observation.hero_discard_tracker_count);
      if (!IsSubset(old_discards, new_tracker)) {
        return Fail(out, error, "Hero discard tracker lost a previously known discard");
      }
      set<int> discard_delta = Difference(new_tracker, old_discards);
      int expected_discards = previous->round_index == 0 ? 0 : 1;
      if (static_cast<int>(discard_delta.size()) != expected_discards) {
        ostringstream oss;
        oss << "round transition expected " << expected_discards
            << " new Hero discard(s), got " << discard_delta.size();
        return Fail(out, error, oss.str());
      }

      set<int> prior_incoming = CardArraySet(previous->hero_incoming, previous->hero_incoming_count);
      if (prior_incoming.empty()) {
        return Fail(out, error, "cannot advance round without previous Hero incoming cards");
      }
      if (!IsSubset(discard_delta, prior_incoming)) {
        return Fail(out, error, "new Hero discard was not part of previous incoming cards");
      }
      set<int> committed_from_prior = Difference(prior_incoming, discard_delta);
      int expected_commit_count = previous->round_index == 0 ? 5 : 2;
      if (static_cast<int>(committed_from_prior.size()) != expected_commit_count) {
        ostringstream oss;
        oss << "previous round should commit " << expected_commit_count
            << " cards, got " << committed_from_prior.size();
        return Fail(out, error, oss.str());
      }

      set<int> membership[3];
      for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
        vector<int> vals = KnownRowValues(old_board, static_cast<EOFCRow>(r));
        membership[r].insert(vals.begin(), vals.end());
      }
      for (set<int>::const_iterator it = committed_from_prior.begin();
           it != committed_from_prior.end(); ++it) {
        EOFCRow row = kOFCRowUndefined;
        if (!FindUniqueVisualRow(hero_visual, *it, &row)) {
          ostringstream oss;
          oss << "previous incoming card " << *it
              << " is neither uniquely discarded nor visible as committed";
          return Fail(out, error, oss.str());
        }
        membership[row].insert(*it);
      }
      if (!BuildBoardFromMembership(
            membership[kOFCRowTop], membership[kOFCRowMiddle], membership[kOFCRowBottom],
            &hero_committed, &validation_error)) {
        return Fail(out, error, validation_error);
      }
      if (!EnsureCommittedStillVisible(hero_committed, hero_visual, "Hero", &validation_error)) {
        return Fail(out, error, validation_error);
      }
    }
  }

  const COFCPlayerBoard &hero_visual = observation.players[observation.hero_chair].visual_board;
  set<int> committed_cards = KnownBoardSet(hero_committed);
  set<int> pending_cards;
  vector<pair<int, EOFCRow> > pending;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow row = static_cast<EOFCRow>(r);
    vector<int> visible = KnownRowValues(hero_visual, row);
    for (size_t i = 0; i < visible.size(); ++i) {
      if (committed_cards.find(visible[i]) == committed_cards.end()) {
        if (!pending_cards.insert(visible[i]).second) {
          return Fail(out, error, "same Hero tentative card appears more than once");
        }
        pending.push_back(make_pair(visible[i], row));
      }
    }
  }

  set<int> loose = CardArraySet(observation.hero_loose_cards, observation.hero_loose_count);
  for (set<int>::const_iterator it = pending_cards.begin(); it != pending_cards.end(); ++it) {
    if (loose.find(*it) != loose.end()) {
      return Fail(out, error, "same Hero current card is both loose and tentatively placed");
    }
  }
  set<int> current_incoming = pending_cards;
  current_incoming.insert(loose.begin(), loose.end());

  if (previous != NULL && previous->valid
      && observation.round_index == previous->round_index) {
    set<int> old_incoming = CardArraySet(previous->hero_incoming, previous->hero_incoming_count);
    if (old_incoming != current_incoming) {
      return Fail(out, error, "Hero incoming card identities changed within the same round");
    }
  }

  int expected_incoming = observation.round_index == 0 ? 5 : 3;
  if (static_cast<int>(current_incoming.size()) != expected_incoming) {
    ostringstream oss;
    oss << "normal round " << observation.round_index << " requires "
        << expected_incoming << " visible Hero incoming cards; got "
        << current_incoming.size();
    return Fail(out, error, oss.str());
  }

  out->schema_version = kOFCStateSchemaVersion;
  out->player_count = observation.player_count;
  out->hero_chair = observation.hero_chair;
  out->dealer_chair = observation.dealer_chair;
  out->acting_chair = observation.acting_chair;
  out->round_index = observation.round_index;
  out->hero_can_prepare = observation.hero_can_prepare;
  out->hero_can_confirm = observation.confirm_visible
    && observation.acting_chair == observation.hero_chair;
  out->action_required = out->hero_can_confirm;

  for (int p = 0; p < observation.player_count; ++p) {
    out->players[p].occupied = observation.players[p].occupied;
    out->players[p].source_chair = observation.players[p].source_chair;
    out->players[p].fantasy = observation.players[p].fantasy;
    out->players[p].sitting_out = observation.players[p].sitting_out;
    out->players[p].hidden_incoming_count = observation.players[p].hidden_incoming_count;
    out->players[p].hidden_discard_count = observation.players[p].hidden_discard_count;

    if (p == observation.hero_chair) {
      out->players[p].board = hero_committed;
    } else {
      COFCPlayerBoard normalized;
      if (!NormalizeBoard(observation.players[p].visual_board, &normalized, &validation_error)) {
        return Fail(out, error, validation_error);
      }
      if (previous != NULL && previous->valid) {
        if (!EnsureCommittedStillVisible(
              previous->players[p].board, normalized, "opponent", &validation_error)) {
          return Fail(out, error, validation_error);
        }
      }
      out->players[p].board = normalized;
    }
  }

  if (static_cast<int>(current_incoming.size()) > kOFCMaxIncomingCards) {
    return Fail(out, error, "Hero incoming exceeds storage capacity");
  }
  CopySortedValuesToCards(
    current_incoming, out->hero_incoming, kOFCMaxIncomingCards, &out->hero_incoming_count);

  set<int> discards = CardArraySet(
    observation.hero_discard_tracker, observation.hero_discard_tracker_count);
  if (static_cast<int>(discards.size()) > kOFCMaxDiscards) {
    return Fail(out, error, "Hero discard tracker exceeds storage capacity");
  }
  CopySortedValuesToCards(
    discards, out->hero_discards, kOFCMaxDiscards, &out->hero_discard_count);

  sort(pending.begin(), pending.end());
  int pending_index = 0;
  for (size_t i = 0; i < pending.size(); ++i) {
    int incoming_index = -1;
    for (int j = 0; j < out->hero_incoming_count; ++j) {
      if (out->hero_incoming[j].value == pending[i].first) {
        incoming_index = j;
        break;
      }
    }
    if (incoming_index < 0 || pending_index >= kOFCMaxIncomingCards) {
      return Fail(out, error, "pending Hero placement cannot be mapped to incoming card");
    }
    out->pending[pending_index].active = true;
    out->pending[pending_index].incoming_index = incoming_index;
    out->pending[pending_index].row = pending[i].second;
    ++pending_index;
  }

  if (!ValidateCanonicalKnownCardUniqueness(*out, &validation_error)) {
    return Fail(out, error, validation_error);
  }

  out->valid = true;
  return true;
}

string COFCReconstructor::DiagnosticSnapshot(const COFCState &state) {
  ostringstream oss;
  oss << "{"
      << "\"schema_version\":" << state.schema_version
      << ",\"valid\":" << BoolJson(state.valid)
      << ",\"player_count\":" << state.player_count
      << ",\"hero_chair\":" << state.hero_chair
      << ",\"dealer_chair\":" << state.dealer_chair
      << ",\"acting_chair\":" << state.acting_chair
      << ",\"round_index\":" << state.round_index
      << ",\"players\":[";

  for (int p = 0; p < state.player_count; ++p) {
    if (p != 0) oss << ",";
    const COFCPlayerState &player = state.players[p];
    oss << "{"
        << "\"chair\":" << p
        << ",\"occupied\":" << BoolJson(player.occupied)
        << ",\"source_chair\":" << player.source_chair
        << ",\"top\":" << RowJson(player.board, kOFCRowTop)
        << ",\"middle\":" << RowJson(player.board, kOFCRowMiddle)
        << ",\"bottom\":" << RowJson(player.board, kOFCRowBottom)
        << ",\"hidden_incoming_count\":" << player.hidden_incoming_count
        << ",\"hidden_discard_count\":" << player.hidden_discard_count
        << ",\"fantasy\":" << BoolJson(player.fantasy)
        << ",\"sitting_out\":" << BoolJson(player.sitting_out)
        << "}";
  }

  oss << "]"
      << ",\"hero_incoming\":" << CardsJson(state.hero_incoming, state.hero_incoming_count)
      << ",\"hero_discards\":" << CardsJson(state.hero_discards, state.hero_discard_count)
      << ",\"pending\":[";

  bool first_pending = true;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active) continue;
    if (!first_pending) oss << ",";
    first_pending = false;
    oss << "{\"incoming_index\":" << state.pending[i].incoming_index
        << ",\"row\":" << static_cast<int>(state.pending[i].row) << "}";
  }

  oss << "]"
      << ",\"hero_can_prepare\":" << BoolJson(state.hero_can_prepare)
      << ",\"hero_can_confirm\":" << BoolJson(state.hero_can_confirm)
      << ",\"action_required\":" << BoolJson(state.action_required)
      << "}";
  return oss.str();
}
