#include "RawTableSnapshotJson.h"

#include <iomanip>
#include <limits>
#include <locale>
#include <sstream>
#include <string>

namespace deepsix6plus {
namespace {

void AppendBool(bool value, std::string* out) {
  *out += value ? "true" : "false";
}

void AppendMoney(double value, std::string* out) {
  std::ostringstream stream;
  stream.imbue(std::locale::classic());
  stream << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
  out->push_back('"');
  *out += stream.str();
  out->push_back('"');
}

void AppendCard(const RawCard& card, std::string* out) {
  *out += "{\"any_card\":";
  AppendBool(card.any_card, out);
  *out += ",\"card_back\":";
  AppendBool(card.card_back, out);
  *out += ",\"known\":";
  AppendBool(card.known, out);
  *out += ",\"openholdem_rank\":" + std::to_string(card.openholdem_rank);
  *out += ",\"suit\":" + std::to_string(card.suit);
  out->push_back('}');
}

void AppendSeat(const RawSeat& seat, std::string* out) {
  *out += "{\"active\":";
  AppendBool(seat.active, out);
  *out += ",\"all_in\":";
  AppendBool(seat.all_in, out);
  *out += ",\"balance\":";
  AppendMoney(seat.balance, out);
  *out += ",\"chair\":" + std::to_string(seat.chair);
  *out += ",\"current_bet\":";
  AppendMoney(seat.current_bet, out);
  *out += ",\"dealer\":";
  AppendBool(seat.dealer, out);
  *out += ",\"has_any_cards\":";
  AppendBool(seat.has_any_cards, out);
  *out += ",\"has_known_cards\":";
  AppendBool(seat.has_known_cards, out);
  *out += ",\"hole_cards\":[";
  for (std::size_t index = 0; index < seat.hole_cards.size(); ++index) {
    if (index != 0) out->push_back(',');
    AppendCard(seat.hole_cards[index], out);
  }
  *out += "],\"seated\":";
  AppendBool(seat.seated, out);
  *out += ",\"stack_including_current_bet\":";
  AppendMoney(seat.stack_including_current_bet, out);
  out->push_back('}');
}

}  // namespace

std::string RawTableSnapshotAuditJson(const RawTableSnapshot& snapshot) {
  std::string out;
  out.reserve(4096);
  out += "{\"board\":[";
  for (std::size_t index = 0; index < snapshot.board.size(); ++index) {
    if (index != 0) out.push_back(',');
    AppendCard(snapshot.board[index], &out);
  }
  out += "],\"community_card_count\":" +
         std::to_string(snapshot.community_card_count);
  out += ",\"dealer_chair\":" + std::to_string(snapshot.dealer_chair);
  out += ",\"hero_chair\":" + std::to_string(snapshot.hero_chair);
  out += ",\"hero_myturnbits\":" + std::to_string(snapshot.hero_myturnbits);
  out += ",\"hero_sitting_in\":";
  AppendBool(snapshot.hero_sitting_in, &out);
  out += ",\"pots\":[";
  for (std::size_t index = 0; index < snapshot.pots.size(); ++index) {
    if (index != 0) out.push_back(',');
    AppendMoney(snapshot.pots[index], &out);
  }
  out += "],\"schema_version\":" + std::to_string(snapshot.schema_version);
  out += ",\"seats\":[";
  for (std::size_t index = 0; index < snapshot.seats.size(); ++index) {
    if (index != 0) out.push_back(',');
    AppendSeat(snapshot.seats[index], &out);
  }
  out += "]}";
  return out;
}

}  // namespace deepsix6plus
