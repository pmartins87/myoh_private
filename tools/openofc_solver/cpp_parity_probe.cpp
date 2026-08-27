// M1 parity probe for the production OpenOFC C++ hand evaluator.
//
// This intentionally includes COFCBaselinePolicy.cpp into one standalone
// translation unit so the anonymous-namespace ranking/royalty primitives used
// by the live policy can be queried without exporting test-only APIs into the
// Windows runtime.

#define DEEPOFC_POLICY_STANDALONE
#include "../../OpenHoldem/COFCBaselinePolicy.cpp"

#include <array>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

void PrintRank(const HandRank &rank) {
  std::cout << rank.category << ',' << rank.length;
  for (int i = 0; i < 5; ++i) std::cout << ',' << rank.tie[i];
}

int RowRoyalty(const HandRank &rank, int row) {
  if (row == 0) return TopRoyalty(rank);
  if (row == 1) return MiddleRoyalty(rank);
  if (row == 2) return BottomRoyalty(rank);
  return -999999;
}

int FantasyCards(const HandRank &top) {
  if (top.category == kTrips) return 17;
  if (top.category == kPair) {
    if (top.tie[0] == 12) return 14;
    if (top.tie[0] == 13) return 15;
    if (top.tie[0] == 14) return 16;
  }
  return 0;
}

bool ReadValue(std::istringstream &in, int *out) {
  return out != NULL && static_cast<bool>(in >> *out);
}

}  // namespace

int main() {
  std::ios::sync_with_stdio(false);
  std::cin.tie(NULL);

  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) continue;
    std::istringstream in(line);
    std::string command;
    in >> command;

    if (command == "MAP") {
      int value = -999;
      if (!ReadValue(in, &value)) {
        std::cout << "ERR|MAP_PARSE\n";
        continue;
      }
      PolicyCard card = Convert(value);
      std::cout << "MAP|" << value << '|' << card.rank << '|'
                << card.suit << '|' << card.joker << "\n";
      continue;
    }

    if (command == "ROW") {
      int row = -1;
      int count = 0;
      if (!ReadValue(in, &row) || !ReadValue(in, &count)
          || row < 0 || row > 2 || (count != 3 && count != 5)) {
        std::cout << "ERR|ROW_HEADER\n";
        continue;
      }
      std::vector<PolicyCard> cards;
      for (int i = 0; i < count; ++i) {
        int value = -999;
        if (!ReadValue(in, &value)) {
          cards.clear();
          break;
        }
        cards.push_back(Convert(value));
      }
      if (static_cast<int>(cards.size()) != count) {
        std::cout << "ERR|ROW_PARSE\n";
        continue;
      }
      const bool top = row == 0;
      std::vector<HandRank> ranks = CandidateRanks(cards, top);
      if (ranks.empty()) {
        std::cout << "ROW|0\n";
        continue;
      }
      std::cout << "ROW|1|";
      PrintRank(ranks[0]);
      std::cout << '|' << RowRoyalty(ranks[0], row)
                << '|' << ranks.size() << "\n";
      continue;
    }

    if (command == "BOARD") {
      std::vector<PolicyCard> cards;
      for (int i = 0; i < 13; ++i) {
        int value = -999;
        if (!ReadValue(in, &value)) {
          cards.clear();
          break;
        }
        cards.push_back(Convert(value));
      }
      if (cards.size() != 13) {
        std::cout << "ERR|BOARD_PARSE\n";
        continue;
      }
      std::vector<PolicyCard> top(cards.begin(), cards.begin() + 3);
      std::vector<PolicyCard> middle(cards.begin() + 3, cards.begin() + 8);
      std::vector<PolicyCard> bottom(cards.begin() + 8, cards.end());
      std::array<HandRank, 3> resolved;
      if (!ResolveBoard(CandidateRanks(top, true),
                        CandidateRanks(middle, false),
                        CandidateRanks(bottom, false), &resolved)) {
        std::cout << "BOARD|0\n";
        continue;
      }
      std::cout << "BOARD|1|";
      PrintRank(resolved[0]);
      std::cout << '|';
      PrintRank(resolved[1]);
      std::cout << '|';
      PrintRank(resolved[2]);
      std::cout << '|' << Royalties(resolved)
                << '|' << FantasyCards(resolved[0]) << "\n";
      continue;
    }

    std::cout << "ERR|UNKNOWN_COMMAND\n";
  }
  return 0;
}
