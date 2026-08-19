//******************************************************************************
//
// DeepOFC canonical state.
//
// This file deliberately does NOT reuse Hold'em hole/community-card semantics.
// It is isolated state storage for KKPoker Open Face Chinese Poker and never
// reuses legacy Hold'em hole/community-card semantics.
//
//******************************************************************************

#ifndef INC_COFCSTATE_H
#define INC_COFCSTATE_H

const int kOFCStateSchemaVersion = 1;
const int kOFCMaxPlayers = 3;
const int kOFCTopCards = 3;
const int kOFCMiddleCards = 5;
const int kOFCBottomCards = 5;
const int kOFCCardsPerBoard = 13;
const int kOFCMaxIncomingCards = 17;
const int kOFCMaxDiscards = 4;

// Standard cards use the existing OpenHoldem/StdDeck 0..51 convention where
// possible. 52 and 53 are reserved for the two physical Jokers. Negative
// values are OFC-local sentinels and must never be passed to legacy Hold'em
// evaluators.
const int kOFCCardUnknown = -3;
const int kOFCCardNoCard = -2;
const int kOFCCardBack = -1;
const int kOFCCardJoker1 = 52;
const int kOFCCardJoker2 = 53;

enum EOFCRow {
  kOFCRowTop = 0,
  kOFCRowMiddle = 1,
  kOFCRowBottom = 2,
  kOFCRowUndefined = -1
};

struct COFCCard {
  int value;

  COFCCard() { Clear(); }
  void Clear() { value = kOFCCardNoCard; }
  bool IsKnownStandardCard() const { return (value >= 0 && value <= 51); }
  bool IsJoker() const { return (value == kOFCCardJoker1 || value == kOFCCardJoker2); }
  bool IsKnownPhysicalCard() const { return IsKnownStandardCard() || IsJoker(); }
  bool IsCardBack() const { return value == kOFCCardBack; }
};

struct COFCPlayerBoard {
  COFCCard top[kOFCTopCards];
  COFCCard middle[kOFCMiddleCards];
  COFCCard bottom[kOFCBottomCards];

  void Reset() {
    for (int i = 0; i < kOFCTopCards; ++i) top[i].Clear();
    for (int i = 0; i < kOFCMiddleCards; ++i) middle[i].Clear();
    for (int i = 0; i < kOFCBottomCards; ++i) bottom[i].Clear();
  }

  int CountKnownCards() const {
    int result = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsKnownPhysicalCard()) ++result;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsKnownPhysicalCard()) ++result;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsKnownPhysicalCard()) ++result;
    return result;
  }
};

struct COFCPlayerState {
  bool occupied;
  int source_chair;
  bool fantasy;
  bool sitting_out;
  int hidden_discard_count;
  int hidden_incoming_count;
  COFCPlayerBoard board;

  void Reset() {
    occupied = false;
    source_chair = -1;
    fantasy = false;
    sitting_out = false;
    hidden_discard_count = 0;
    hidden_incoming_count = 0;
    board.Reset();
  }
};

// A placement is row-based, not slot-based. Supplied KKPoker replay evidence
// shows that cards inside each row are automatically re-sorted after Confirm,
// so persistent visual slot identity is not a strategic concept.
struct COFCPendingPlacement {
  bool active;
  int incoming_index;
  EOFCRow row;

  void Reset() {
    active = false;
    incoming_index = -1;
    row = kOFCRowUndefined;
  }
};

class COFCState {
 public:
  COFCState() { Reset(); }

  void Reset() {
    valid = false;
    schema_version = kOFCStateSchemaVersion;
    player_count = 0;
    hero_chair = -1;
    dealer_chair = -1;
    acting_chair = -1;
    round_index = -1;
    hero_can_prepare = false;
    hero_can_confirm = false;
    action_required = false;
    hero_incoming_count = 0;
    hero_discard_count = 0;
    for (int i = 0; i < kOFCMaxPlayers; ++i) players[i].Reset();
    for (int i = 0; i < kOFCMaxIncomingCards; ++i) hero_incoming[i].Clear();
    for (int i = 0; i < kOFCMaxDiscards; ++i) hero_discards[i].Clear();
    for (int i = 0; i < kOFCMaxIncomingCards; ++i) pending[i].Reset();
  }

 public:
  bool valid;
  int schema_version;
  int player_count;
  int hero_chair;
  int dealer_chair;
  int acting_chair;
  int round_index;
  bool hero_can_prepare;
  bool hero_can_confirm;
  bool action_required;

  COFCPlayerState players[kOFCMaxPlayers];
  COFCCard hero_incoming[kOFCMaxIncomingCards];
  int hero_incoming_count;
  COFCCard hero_discards[kOFCMaxDiscards];
  int hero_discard_count;
  COFCPendingPlacement pending[kOFCMaxIncomingCards];
};

#endif  // INC_COFCSTATE_H
