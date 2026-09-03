// Standalone parity test for OpenHoldem/COFCP3Policy.cpp.

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "COFCP3Policy.h"

using namespace std;

namespace {

vector<string> Split(const string &value, char delimiter) {
  vector<string> fields;
  string field;
  istringstream input(value);
  while (getline(input, field, delimiter)) fields.push_back(field);
  if (!value.empty() && value[value.size() - 1] == delimiter) fields.push_back("");
  return fields;
}

int Integer(const string &value) {
  char *end = NULL;
  const long parsed = strtol(value.c_str(), &end, 10);
  if (end == value.c_str() || *end != '\0') {
    throw string("invalid integer: ") + value;
  }
  return static_cast<int>(parsed);
}

vector<int> CardList(const string &value) {
  vector<int> cards;
  if (value == "-") return cards;
  const vector<string> fields = Split(value, ',');
  for (size_t i = 0; i < fields.size(); ++i) cards.push_back(Integer(fields[i]));
  return cards;
}

void FillCards(
    const vector<int> &values, COFCCard *cards, int capacity, const char *label) {
  if (static_cast<int>(values.size()) > capacity) {
    throw string(label) + " exceeds capacity";
  }
  for (size_t i = 0; i < values.size(); ++i) cards[i].value = values[i];
}

COFCState ParseState(const vector<string> &fields) {
  if (fields.size() != 23) throw string("fixture line must contain 23 fields");
  COFCState state;
  state.Reset();
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = Integer(fields[2]);
  state.dealer_chair = Integer(fields[3]);
  state.acting_chair = Integer(fields[4]);
  state.round_index = Integer(fields[5]);
  state.hero_can_prepare = Integer(fields[6]) != 0;
  state.hero_can_confirm = state.hero_can_prepare;
  state.action_required = state.hero_can_prepare;
  for (int chair = 0; chair < 2; ++chair) {
    state.players[chair].occupied = true;
    state.players[chair].source_chair = chair;
    state.players[chair].fantasy = false;
    state.players[chair].sitting_out = false;
  }
  state.players[0].hidden_discard_count = Integer(fields[7]);
  state.players[0].hidden_incoming_count = Integer(fields[8]);
  state.players[1].hidden_discard_count = Integer(fields[9]);
  state.players[1].hidden_incoming_count = Integer(fields[10]);
  FillCards(CardList(fields[11]), state.players[0].board.top, 3, "p0 top");
  FillCards(CardList(fields[12]), state.players[0].board.middle, 5, "p0 middle");
  FillCards(CardList(fields[13]), state.players[0].board.bottom, 5, "p0 bottom");
  FillCards(CardList(fields[14]), state.players[1].board.top, 3, "p1 top");
  FillCards(CardList(fields[15]), state.players[1].board.middle, 5, "p1 middle");
  FillCards(CardList(fields[16]), state.players[1].board.bottom, 5, "p1 bottom");
  const vector<int> incoming = CardList(fields[17]);
  const vector<int> discards = CardList(fields[18]);
  FillCards(incoming, state.hero_incoming, kOFCMaxIncomingCards, "incoming");
  FillCards(discards, state.hero_discards, kOFCMaxDiscards, "discards");
  state.hero_incoming_count = static_cast<int>(incoming.size());
  state.hero_discard_count = static_cast<int>(discards.size());
  return state;
}

string PhysicalAction(const COFCStrategyAction &action) {
  vector<pair<int, int> > placements;
  for (int i = 0; i < action.placement_count; ++i) {
    placements.push_back(make_pair(
        action.placements[i].card_value,
        static_cast<int>(action.placements[i].row)));
  }
  sort(placements.begin(), placements.end());
  ostringstream out;
  for (size_t i = 0; i < placements.size(); ++i) {
    if (i != 0) out << ",";
    out << placements[i].first << "@" << placements[i].second;
  }
  out << "/";
  if (action.unused_count == 0) out << "-";
  else if (action.unused_count == 1) out << action.unused_cards[0];
  else out << "INVALID";
  return out.str();
}

bool Decide(const string &command) {
  return command.size() == 2 && command[1] == '1';
}

bool Reset(const string &command) {
  return command.size() == 2 && command[0] == 'R';
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 3) {
    cerr << "usage: openofc_p3_policy_selftest POLICY_DIR FIXTURE\n";
    return 2;
  }
  COFCP3Policy policy;
  string error;
  if (!policy.LoadDirectory(argv[1], &error)) {
    cerr << "policy load failed: " << error << "\n";
    return 3;
  }
  ifstream fixture(argv[2]);
  if (!fixture) {
    cerr << "cannot open fixture\n";
    return 4;
  }
  COFCP3PublicHistory history;
  COFCState hand_root;
  bool have_hand_root = false;
  string line;
  int states = 0;
  int decisions = 0;
  try {
    while (getline(fixture, line)) {
      if (line.empty() || line[0] == '#') continue;
      const vector<string> fields = Split(line, '|');
      const COFCState state = ParseState(fields);
      if (Reset(fields[0])) {
        if (!history.ResetForKnownNewHand(state, &error)) {
          throw string("history reset failed: ") + error;
        }
        hand_root = state;
        have_hand_root = true;
      } else if (!history.Observe(state, &error)) {
        throw string("history observation failed: ") + error;
      }
      ++states;
      if (!Decide(fields[0])) continue;
      if (!have_hand_root) throw string("decision preceded known-hand reset");
      if (!history.events().empty()) {
        COFCP3PublicHistory incomplete;
        if (!incomplete.ResetForKnownNewHand(hand_root, &error)) {
          throw string("incomplete-history setup failed: ") + error;
        }
        COFCStrategyAction rejected_action;
        COFCP3PolicyReceipt rejected_receipt;
        if (policy.Choose(
              state, incomplete, &rejected_action, &rejected_receipt, &error)) {
          throw string("incomplete public history did not fail closed");
        }
      }
      COFCState hidden_count_tamper = state;
      const int opponent = 1 - state.hero_chair;
      ++hidden_count_tamper.players[opponent].hidden_incoming_count;
      COFCStrategyAction rejected_action;
      COFCP3PolicyReceipt rejected_receipt;
      if (policy.Choose(
            hidden_count_tamper, history,
            &rejected_action, &rejected_receipt, &error)) {
        throw string("contradictory hidden count did not fail closed");
      }
      COFCStrategyAction action;
      COFCP3PolicyReceipt receipt;
      if (!policy.Choose(state, history, &action, &receipt, &error)) {
        throw string("policy decision failed: ") + error;
      }
      if (!receipt.valid || receipt.physical_execution_authorized
          || receipt.authority != COFCP3Policy::Authority()
          || receipt.native_manifest_sha256
              != COFCP3Policy::NativeManifestSha256()
          || receipt.p2_manifest_sha256 != COFCP3Policy::P2ManifestSha256()
          || receipt.p2_source_commit != COFCP3Policy::P2SourceCommit()) {
        throw string("decision receipt authority/identity mismatch");
      }
      if (receipt.canonical_information_key_sha256 != fields[19]) {
        throw string("canonical information-key SHA mismatch at case ") + fields[1];
      }
      if (receipt.canonical_action_key != fields[20]) {
        throw string("canonical action mismatch at case ") + fields[1];
      }
      const double expected_probability = strtod(fields[21].c_str(), NULL);
      if (fabs(receipt.selected_probability - expected_probability) > 1e-15) {
        throw string("selected probability mismatch at case ") + fields[1];
      }
      if (PhysicalAction(action) != fields[22]) {
        throw string("physical action mismatch at case ") + fields[1];
      }
      ++decisions;
    }
  } catch (const string &message) {
    cerr << message << "\n";
    return 5;
  }
  if (states != 20 || decisions != 10) {
    cerr << "fixture cardinality mismatch states=" << states
         << " decisions=" << decisions << "\n";
    return 6;
  }
  cout << "OPENOFC_P3_NATIVE_POLICY_PARITY=PASS states=" << states
       << " decisions=" << decisions << "\n";
  return 0;
}
