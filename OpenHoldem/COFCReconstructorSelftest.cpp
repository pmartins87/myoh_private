//******************************************************************************
//
// Native standalone self-test for COFCReconstructor.
//
// This file is NOT part of OpenHoldem.vcxproj. The R9 Windows gate compiles it
// separately against a reference stream exported by pmartins87/DeepOFC.
//
//******************************************************************************

#include "COFCReconstructor.h"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

namespace {

struct ReplayFrame {
  string name;
  COFCVisualObservation raw;
  string expected;
};

vector<string> Split(const string &text, char delim) {
  vector<string> out;
  string current;
  for (size_t i = 0; i < text.size(); ++i) {
    if (text[i] == delim) {
      out.push_back(current);
      current.clear();
    } else {
      current.push_back(text[i]);
    }
  }
  out.push_back(current);
  return out;
}

int ToInt(const string &text) {
  return atoi(text.c_str());
}

vector<int> ParseCards(const string &text) {
  vector<int> cards;
  if (text.empty() || text == "-") return cards;
  vector<string> parts = Split(text, ',');
  for (size_t i = 0; i < parts.size(); ++i) {
    cards.push_back(ToInt(parts[i]));
  }
  return cards;
}

bool FillRow(COFCPlayerBoard *board, EOFCRow row, const string &text, string *error) {
  vector<int> values = ParseCards(text);
  int capacity = row == kOFCRowTop ? kOFCTopCards : kOFCMiddleCards;
  if (static_cast<int>(values.size()) > capacity) {
    *error = "reference row exceeds capacity";
    return false;
  }
  COFCCard *target = NULL;
  if (row == kOFCRowTop) target = board->top;
  else if (row == kOFCRowMiddle) target = board->middle;
  else target = board->bottom;
  for (size_t i = 0; i < values.size(); ++i) target[i].value = values[i];
  return true;
}

bool LoadReference(const string &path, vector<ReplayFrame> *frames, string *error) {
  ifstream in(path.c_str());
  if (!in) {
    *error = "cannot open replay reference: " + path;
    return false;
  }

  string line;
  if (!getline(in, line) || (line != "DEEPOFC_OPENHOLDEM_REPLAY_REFERENCE|1" && line != "DEEPOFC_OPENHOLDEM_REPLAY_REFERENCE|2")) {
    *error = "bad replay reference header";
    return false;
  }

  ReplayFrame current;
  bool in_frame = false;
  while (getline(in, line)) {
    if (line.empty()) continue;
    vector<string> fields = Split(line, '|');
    const string &kind = fields[0];

    if (kind == "FRAME") {
      if (fields.size() != 2 || in_frame) {
        *error = "malformed FRAME record";
        return false;
      }
      current = ReplayFrame();
      current.name = fields[1];
      current.raw.Reset();
      in_frame = true;
    } else if (kind == "META") {
      if (!in_frame || fields.size() != 8) {
        *error = "malformed META record";
        return false;
      }
      current.raw.player_count = ToInt(fields[1]);
      current.raw.hero_chair = ToInt(fields[2]);
      current.raw.dealer_chair = ToInt(fields[3]);
      current.raw.acting_chair = ToInt(fields[4]);
      current.raw.round_index = ToInt(fields[5]);
      current.raw.hero_can_prepare = ToInt(fields[6]) != 0;
      current.raw.confirm_visible = ToInt(fields[7]) != 0;
    } else if (kind == "PLAYER") {
      if (!in_frame || fields.size() != 9) {
        *error = "malformed PLAYER record";
        return false;
      }
      int chair = ToInt(fields[1]);
      if (chair < 0 || chair >= kOFCMaxPlayers) {
        *error = "reference chair out of range";
        return false;
      }
      COFCVisualPlayerObservation *player = &current.raw.players[chair];
      player->occupied = true;
      player->source_chair = chair;
      player->hidden_incoming_count = ToInt(fields[2]);
      player->hidden_discard_count = ToInt(fields[3]);
      player->fantasy = ToInt(fields[4]) != 0;
      player->sitting_out = ToInt(fields[5]) != 0;
      if (!FillRow(&player->visual_board, kOFCRowTop, fields[6], error)
          || !FillRow(&player->visual_board, kOFCRowMiddle, fields[7], error)
          || !FillRow(&player->visual_board, kOFCRowBottom, fields[8], error)) {
        return false;
      }
    } else if (kind == "LOOSE") {
      if (!in_frame || fields.size() != 2) {
        *error = "malformed LOOSE record";
        return false;
      }
      vector<int> cards = ParseCards(fields[1]);
      if (static_cast<int>(cards.size()) > kOFCMaxIncomingCards) {
        *error = "too many reference loose cards";
        return false;
      }
      current.raw.hero_loose_count = static_cast<int>(cards.size());
      for (size_t i = 0; i < cards.size(); ++i) current.raw.hero_loose_cards[i].value = cards[i];
    } else if (kind == "DISCARDS") {
      if (!in_frame || fields.size() != 2) {
        *error = "malformed DISCARDS record";
        return false;
      }
      vector<int> cards = ParseCards(fields[1]);
      if (static_cast<int>(cards.size()) > kOFCMaxDiscards) {
        *error = "too many reference discards";
        return false;
      }
      current.raw.hero_discard_tracker_count = static_cast<int>(cards.size());
      for (size_t i = 0; i < cards.size(); ++i) current.raw.hero_discard_tracker[i].value = cards[i];
    } else if (kind == "EXPECTED") {
      if (!in_frame) {
        *error = "EXPECTED outside frame";
        return false;
      }
      size_t sep = line.find('|');
      current.expected = sep == string::npos ? "" : line.substr(sep + 1);
    } else if (kind == "END") {
      if (!in_frame || current.expected.empty()) {
        *error = "malformed END record";
        return false;
      }
      current.raw.valid = true;
      frames->push_back(current);
      in_frame = false;
    } else {
      *error = "unknown replay record: " + kind;
      return false;
    }
  }

  if (in_frame || frames->empty()) {
    *error = "truncated/empty replay reference";
    return false;
  }
  return true;
}

bool RunGoldenSequence(const vector<ReplayFrame> &frames) {
  COFCState previous;
  bool have_previous = false;

  for (size_t i = 0; i < frames.size(); ++i) {
    COFCState rebuilt;
    string error;
    const COFCState *previous_ptr = have_previous ? &previous : NULL;
    if (!COFCReconstructor::Reconstruct(frames[i].raw, previous_ptr, &rebuilt, &error)) {
      cerr << "RECONSTRUCT FAIL " << frames[i].name << ": " << error << endl;
      return false;
    }
    string actual = COFCReconstructor::DiagnosticSnapshot(rebuilt);
    if (actual != frames[i].expected) {
      cerr << "SNAPSHOT MISMATCH " << frames[i].name << endl;
      cerr << "EXPECTED: " << frames[i].expected << endl;
      cerr << "ACTUAL:   " << actual << endl;
      return false;
    }
    previous = rebuilt;
    have_previous = true;
  }
  return true;
}

bool RunNegativeAndJokerTests(const vector<ReplayFrame> &frames) {
  if (frames.size() < 4) return false;

  // Mid-hand attach without canonical history must fail closed.
  COFCState ignored;
  string error;
  if (COFCReconstructor::Reconstruct(frames[3].raw, NULL, &ignored, &error)) {
    cerr << "NEGATIVE TEST FAIL: mid-hand attach unexpectedly accepted" << endl;
    return false;
  }

  // A visible Confirm control while the opponent acts must never become a safe
  // Hero confirmation.
  COFCState first;
  error.clear();
  if (!COFCReconstructor::Reconstruct(frames[0].raw, NULL, &first, &error)) {
    cerr << "NEGATIVE TEST SETUP FAIL: " << error << endl;
    return false;
  }
  if (first.hero_can_confirm || first.action_required) {
    cerr << "NEGATIVE TEST FAIL: raw Confirm overrode acting order" << endl;
    return false;
  }

  // Joker occurrence labels are visual occurrences, not persistent identities.
  // If the raw scanner flips JK1<->JK2 between same-round frames, the canonical
  // state must preserve the previous occurrence identity when evidence supports it.
  COFCVisualObservation joker_raw;
  joker_raw.Reset();
  joker_raw.valid = true;
  joker_raw.player_count = 2;
  joker_raw.hero_chair = 1;
  joker_raw.dealer_chair = 1;
  joker_raw.acting_chair = 0;
  joker_raw.round_index = 0;
  joker_raw.hero_can_prepare = true;
  joker_raw.confirm_visible = true;
  joker_raw.players[0].occupied = true;
  joker_raw.players[0].source_chair = 0;
  joker_raw.players[0].hidden_incoming_count = 5;
  joker_raw.players[1].occupied = true;
  joker_raw.players[1].source_chair = 1;
  const int values[5] = {kOFCCardJoker1, 0, 1, 2, 3};
  joker_raw.hero_loose_count = 5;
  for (int i = 0; i < 5; ++i) joker_raw.hero_loose_cards[i].value = values[i];

  COFCState joker_first;
  error.clear();
  if (!COFCReconstructor::Reconstruct(joker_raw, NULL, &joker_first, &error)) {
    cerr << "JOKER TEST SETUP FAIL: " << error << endl;
    return false;
  }
  COFCVisualObservation flipped = joker_raw;
  flipped.hero_loose_cards[0].value = kOFCCardJoker2;
  COFCState joker_second;
  error.clear();
  if (!COFCReconstructor::Reconstruct(flipped, &joker_first, &joker_second, &error)) {
    cerr << "JOKER LABEL NORMALIZATION FAIL: " << error << endl;
    return false;
  }
  bool preserved = false;
  for (int i = 0; i < joker_second.hero_incoming_count; ++i) {
    if (joker_second.hero_incoming[i].value == kOFCCardJoker1) preserved = true;
    if (joker_second.hero_incoming[i].value == kOFCCardJoker2) {
      cerr << "JOKER LABEL NORMALIZATION FAIL: JK2 leaked into canonical same-round identity" << endl;
      return false;
    }
  }
  if (!preserved) {
    cerr << "JOKER LABEL NORMALIZATION FAIL: JK1 not preserved" << endl;
    return false;
  }

  return true;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    cerr << "usage: COFCReconstructorSelftest <reference.txt>" << endl;
    return 2;
  }

  vector<ReplayFrame> frames;
  string error;
  if (!LoadReference(argv[1], &frames, &error)) {
    cerr << "REFERENCE LOAD FAIL: " << error << endl;
    return 2;
  }
  if (!RunGoldenSequence(frames)) return 1;
  if (!RunNegativeAndJokerTests(frames)) return 1;

  cout << "DEEPOFC_CPP_RECONSTRUCTOR_SELFTEST_PASS frames=" << frames.size() << endl;
  return 0;
}
