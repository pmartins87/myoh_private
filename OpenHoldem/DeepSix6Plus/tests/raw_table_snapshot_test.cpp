#include "../RawTableSnapshot.h"
#include "../RawTableSnapshotJson.h"

#include <cassert>
#include <limits>
#include <string>

int main() {
  using namespace deepsix6plus;

  RawTableSnapshot snapshot;
  snapshot.dealer_chair = 5;
  snapshot.hero_chair = -1;  // observer mode is valid raw evidence.
  snapshot.hero_myturnbits = kRawMyTurnFold | kRawMyTurnCall | kRawMyTurnRaise;
  snapshot.hero_sitting_in = true;
  snapshot.community_card_count = 3;
  for (int chair = 0; chair < kRawMaxChairs; ++chair) {
    snapshot.seats[chair].chair = chair;
  }

  snapshot.board[0] = RawCard{true, true, false, 6, 0};
  snapshot.board[1] = RawCard{true, true, false, 14, 3};
  snapshot.board[2] = RawCard{true, true, false, 10, 1};
  snapshot.seats[5].seated = true;
  snapshot.seats[5].active = true;
  snapshot.seats[5].dealer = true;
  snapshot.seats[5].balance = 97.5;
  snapshot.seats[5].current_bet = 2.0;
  snapshot.seats[5].stack_including_current_bet = 99.5;
  snapshot.pots[0] = 12.5;

  std::string error;
  assert(ValidateRawSnapshotForShortDeck(snapshot, &error));

  const std::string json = RawTableSnapshotAuditJson(snapshot);
  assert(json.find("\"dealer_chair\":5") != std::string::npos);
  assert(json.find("\"hero_chair\":-1") != std::string::npos);
  assert(json.find("\"hero_myturnbits\":11") != std::string::npos);
  assert(json.find("\"hero_sitting_in\":true") != std::string::npos);
  assert(json.find("\"schema_version\":2") != std::string::npos);
  assert(json.find("\"community_card_count\":3") != std::string::npos);
  assert(json.find("\"balance\":\"97.5\"") != std::string::npos);
  assert(json.find("\"current_bet\":\"2\"") != std::string::npos);
  assert(json.find("\"pots\":[\"12.5\"") != std::string::npos);
  assert(json.find("\"openholdem_rank\":6,\"suit\":0") != std::string::npos);

  RawTableSnapshot removed_rank = snapshot;
  removed_rank.board[0].openholdem_rank = 5;
  assert(!ValidateRawSnapshotForShortDeck(removed_rank, &error));

  RawTableSnapshot duplicate = snapshot;
  duplicate.seats[0].hole_cards[0] = duplicate.board[0];
  assert(!ValidateRawSnapshotForShortDeck(duplicate, &error));

  RawTableSnapshot nan_money = snapshot;
  nan_money.seats[0].balance = std::numeric_limits<double>::quiet_NaN();
  assert(!ValidateRawSnapshotForShortDeck(nan_money, &error));

  RawTableSnapshot invalid_board_count = snapshot;
  invalid_board_count.community_card_count = 2;
  assert(!ValidateRawSnapshotForShortDeck(invalid_board_count, &error));

  RawTableSnapshot invalid_turn_bits = snapshot;
  invalid_turn_bits.hero_myturnbits = kRawMyTurnAllowedMask | 0x20;
  assert(!ValidateRawSnapshotForShortDeck(invalid_turn_bits, &error));

  RawTableSnapshot old_schema = snapshot;
  old_schema.schema_version = 1;
  assert(!ValidateRawSnapshotForShortDeck(old_schema, &error));

  return 0;
}
