#include "RawTableSnapshot.h"

#include <cmath>

namespace deepsix6plus {
namespace {

bool Fail(const char* message, std::string* error) {
  if (error != nullptr) {
    *error = message;
  }
  return false;
}

bool ValidateKnownCard(const RawCard& card,
                       bool seen[15][4],
                       std::string* error) {
  if (!card.known) {
    return true;
  }
  if (card.openholdem_rank < 6 || card.openholdem_rank > 14) {
    return Fail("known card rank is outside Short Deck 6..A", error);
  }
  if (card.suit < 0 || card.suit >= 4) {
    return Fail("known card suit is outside 0..3", error);
  }
  if (seen[card.openholdem_rank][card.suit]) {
    return Fail("duplicate known card in raw snapshot", error);
  }
  seen[card.openholdem_rank][card.suit] = true;
  return true;
}

bool IsValidMoney(double value) {
  return std::isfinite(value) && value >= 0.0;
}

}  // namespace

bool ValidateRawSnapshotForShortDeck(const RawTableSnapshot& snapshot,
                                     std::string* error) {
  if (snapshot.schema_version != 2) {
    return Fail("unsupported raw snapshot schema version", error);
  }
  if (snapshot.dealer_chair < 0 || snapshot.dealer_chair >= kRawMaxChairs) {
    return Fail("dealer chair is unknown or outside OpenHoldem chair range", error);
  }
  if (snapshot.hero_chair < -1 || snapshot.hero_chair >= kRawMaxChairs) {
    return Fail("hero chair is outside OpenHoldem chair range", error);
  }
  if (snapshot.hero_myturnbits < 0 ||
      (snapshot.hero_myturnbits & ~kRawMyTurnAllowedMask) != 0) {
    return Fail("hero myturnbits contain unknown OpenHoldem action bits", error);
  }
  if (!(snapshot.community_card_count == 0 ||
        snapshot.community_card_count == 3 ||
        snapshot.community_card_count == 4 ||
        snapshot.community_card_count == 5)) {
    return Fail("community card count is not a Holdem street boundary", error);
  }

  bool seen[15][4] = {};
  for (const RawCard& card : snapshot.board) {
    if (!ValidateKnownCard(card, seen, error)) {
      return false;
    }
  }
  for (const RawSeat& seat : snapshot.seats) {
    if (seat.chair < 0 || seat.chair >= kRawMaxChairs) {
      return Fail("seat chair is outside OpenHoldem chair range", error);
    }
    if (!IsValidMoney(seat.balance) || !IsValidMoney(seat.current_bet) ||
        !IsValidMoney(seat.stack_including_current_bet)) {
      return Fail("non-finite or negative money value in raw snapshot", error);
    }
    for (const RawCard& card : seat.hole_cards) {
      if (!ValidateKnownCard(card, seen, error)) {
        return false;
      }
    }
  }
  for (double pot : snapshot.pots) {
    if (!IsValidMoney(pot)) {
      return Fail("non-finite or negative pot value in raw snapshot", error);
    }
  }
  return true;
}

}  // namespace deepsix6plus
