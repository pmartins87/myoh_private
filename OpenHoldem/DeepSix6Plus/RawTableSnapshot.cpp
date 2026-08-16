#include "RawTableSnapshot.h"

#include "../Card.h"
#include "../CEngineContainer.h"
#include "../CPlayer.h"
#include "../CSymbolEngineAutoplayer.h"
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

}  // namespace

bool CaptureRawTableSnapshot(RawTableSnapshot* snapshot, std::string* error) {
  static_assert(kRawMaxChairs == kMaxNumberOfPlayers,
                "DeepSix raw chair count must match OpenHoldem");
  static_assert(kRawBoardCards == kNumberOfCommunityCards,
                "DeepSix raw board count must match OpenHoldem");
  static_assert(kRawPotSlots == kMaxNumberOfPots,
                "DeepSix raw pot count must match OpenHoldem");
  static_assert(kRawMyTurnFold == kMyTurnBitsFold,
                "DeepSix fold bit must match OpenHoldem");
  static_assert(kRawMyTurnCall == kMyTurnBitsCall,
                "DeepSix call bit must match OpenHoldem");
  static_assert(kRawMyTurnCheck == kMyTurnBitsCheck,
                "DeepSix check bit must match OpenHoldem");
  static_assert(kRawMyTurnRaise == kMyTurnBitsRaise,
                "DeepSix raise bit must match OpenHoldem");
  static_assert(kRawMyTurnAllin == kMyTurnBitsAllin,
                "DeepSix all-in bit must match OpenHoldem");

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
  CSymbolEngineAutoplayer* autoplayer_engine =
      p_engine_container->symbol_engine_autoplayer();
  if (dealer_engine == nullptr || user_engine == nullptr ||
      autoplayer_engine == nullptr) {
    return Fail("required chair/autoplayer engines are unavailable", error);
  }

  RawTableSnapshot captured;
  captured.dealer_chair = dealer_engine->dealerchair();
  captured.hero_chair =
      user_engine->userchair_confirmed() ? user_engine->userchair() : -1;
  captured.hero_myturnbits = autoplayer_engine->myturnbits();
  captured.hero_sitting_in = autoplayer_engine->issittingin();
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

}  // namespace deepsix6plus
