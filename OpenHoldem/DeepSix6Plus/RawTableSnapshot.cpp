#include "RawTableSnapshot.h"

#include "../Card.h"
#include "../CEngineContainer.h"
#include "../CPlayer.h"
#include "../CSymbolEngineDealerchair.h"
#include "../CSymbolengineUserchair.h"
#include "../CTableState.h"
#include "../../Shared/MagicNumbers/MagicNumbers.h"

namespace deepsix6plus {
namespace {

bool Fail(const char* message, std::string* error) {
  if (error != nullptr) {
    *error = message;
  }
  return false;
}

RawCard CaptureCard(Card* card) {
  RawCard result;
  if (card == nullptr) {
    return result;
  }
  result.any_card = card->IsAnyCard();
  result.known = card->IsKnownCard();
  result.card_back = card->IsCardBack();
  if (result.known) {
    result.openholdem_rank = card->GetOpenHoldemRank();
    result.suit = card->GetSuit();
  }
  return result;
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

}  // namespace

bool CaptureRawTableSnapshot(RawTableSnapshot* snapshot, std::string* error) {
  static_assert(kRawMaxChairs == kMaxNumberOfPlayers,
                "DeepSix raw chair count must match OpenHoldem");
  static_assert(kRawBoardCards == kNumberOfCommunityCards,
                "DeepSix raw board count must match OpenHoldem");
  static_assert(kRawPotSlots == kMaxNumberOfPots,
                "DeepSix raw pot count must match OpenHoldem");

  if (snapshot == nullptr) {
    return Fail("snapshot output pointer is null", error);
  }
  if (p_table_state == nullptr) {
    return Fail("OpenHoldem table state is unavailable", error);
  }
  if (p_engine_container == nullptr) {
    return Fail("OpenHoldem engine container is unavailable", error);
  }

  CSymbolEngineDealerchair* dealer_engine =
      p_engine_container->symbol_engine_dealerchair();
  CSymbolEngineUserchair* user_engine =
      p_engine_container->symbol_engine_userchair();
  if (dealer_engine == nullptr || user_engine == nullptr) {
    return Fail("required chair engines are unavailable", error);
  }

  RawTableSnapshot captured;
  captured.dealer_chair = dealer_engine->dealerchair();
  captured.hero_chair =
      user_engine->userchair_confirmed() ? user_engine->userchair() : -1;
  captured.community_card_count = p_table_state->NumberOfCommunityCards();

  for (int index = 0; index < kRawBoardCards; ++index) {
    captured.board[index] = CaptureCard(p_table_state->CommonCards(index));
  }

  for (int chair = 0; chair < kRawMaxChairs; ++chair) {
    CPlayer* player = p_table_state->Player(chair);
    if (player == nullptr) {
      return Fail("OpenHoldem returned a null player entry", error);
    }

    RawSeat seat;
    seat.chair = chair;
    seat.seated = player->seated();
    seat.active = player->active();
    seat.dealer = player->dealer();
    seat.all_in = player->IsAllin();
    seat.has_any_cards = player->HasAnyCards();
    seat.has_known_cards = player->HasKnownCards();
    seat.balance = player->_balance.GetValue();
    seat.current_bet = player->_bet.GetValue();
    seat.stack_including_current_bet = player->stack();
    for (int card_index = 0; card_index < kRawHoleCards; ++card_index) {
      seat.hole_cards[card_index] =
          CaptureCard(player->hole_cards(card_index));
    }
    captured.seats[chair] = seat;
  }

  for (int index = 0; index < kRawPotSlots; ++index) {
    captured.pots[index] = p_table_state->Pot(index);
  }

  *snapshot = captured;
  return true;
}

bool ValidateRawSnapshotForShortDeck(const RawTableSnapshot& snapshot,
                                     std::string* error) {
  if (snapshot.schema_version != 1) {
    return Fail("unsupported raw snapshot schema version", error);
  }
  if (snapshot.dealer_chair < 0 || snapshot.dealer_chair >= kRawMaxChairs) {
    return Fail("dealer chair is unknown or outside OpenHoldem chair range", error);
  }
  if (snapshot.hero_chair < -1 || snapshot.hero_chair >= kRawMaxChairs) {
    return Fail("hero chair is outside OpenHoldem chair range", error);
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
    if (seat.balance < 0.0 || seat.current_bet < 0.0 ||
        seat.stack_including_current_bet < 0.0) {
      return Fail("negative money value in raw snapshot", error);
    }
    for (const RawCard& card : seat.hole_cards) {
      if (!ValidateKnownCard(card, seen, error)) {
        return false;
      }
    }
  }
  for (double pot : snapshot.pots) {
    if (pot < 0.0) {
      return Fail("negative pot value in raw snapshot", error);
    }
  }
  return true;
}

}  // namespace deepsix6plus
