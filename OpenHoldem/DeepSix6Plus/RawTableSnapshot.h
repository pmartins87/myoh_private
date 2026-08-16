#pragma once

#include <array>
#include <string>

namespace deepsix6plus {

constexpr int kRawMaxChairs = 10;
constexpr int kRawHoleCards = 2;
constexpr int kRawBoardCards = 5;
constexpr int kRawPotSlots = 10;

// Raw visible-action button bits. These intentionally mirror OpenHoldem's
// F/C/K/R/A my-turn bits at the capture boundary; they are evidence only, not
// a strategic action decision.
constexpr int kRawMyTurnFold = 0x01;
constexpr int kRawMyTurnCall = 0x02;
constexpr int kRawMyTurnCheck = 0x04;
constexpr int kRawMyTurnRaise = 0x08;
constexpr int kRawMyTurnAllin = 0x10;
constexpr int kRawMyTurnAllowedMask =
    kRawMyTurnFold | kRawMyTurnCall | kRawMyTurnCheck |
    kRawMyTurnRaise | kRawMyTurnAllin;

struct RawCard {
  bool any_card = false;
  bool known = false;
  bool card_back = false;
  int openholdem_rank = -1;
  int suit = -1;
};

struct RawSeat {
  int chair = -1;
  bool seated = false;
  bool active = false;
  bool dealer = false;
  bool all_in = false;
  bool has_any_cards = false;
  bool has_known_cards = false;
  double balance = 0.0;
  double current_bet = 0.0;
  double stack_including_current_bet = 0.0;
  std::array<RawCard, kRawHoleCards> hole_cards{};
};

struct RawTableSnapshot {
  int schema_version = 2;
  int dealer_chair = -1;
  int hero_chair = -1;  // -1 is valid in observer mode.
  int hero_myturnbits = 0;
  bool hero_sitting_in = false;
  int community_card_count = 0;
  std::array<RawCard, kRawBoardCards> board{};
  std::array<RawSeat, kRawMaxChairs> seats{};
  std::array<double, kRawPotSlots> pots{};
};

// Pure read-only capture from OpenHoldem's already-scraped table state.
bool CaptureRawTableSnapshot(RawTableSnapshot* snapshot,
                             std::string* error = nullptr);

// Structural Short Deck guard only. This does not infer strategic state.
bool ValidateRawSnapshotForShortDeck(const RawTableSnapshot& snapshot,
                                     std::string* error = nullptr);

}  // namespace deepsix6plus
