// Parity probe for the v5.7 production COFCExactEvaluator.

#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "../../OpenHoldem/COFCExactEvaluator.h"

namespace {

void PrintRank(const COFCExactHandRank &rank) {
  std::cout << rank.category << ',' << rank.length;
  for (int i = 0; i < 5; ++i) std::cout << ',' << rank.tie[i];
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
      const bool joker = value == kOFCCardJoker1 || value == kOFCCardJoker2;
      const int rank = joker ? 0 : value % 13 + 2;
      const int suit = joker ? -1 : value / 13;
      const int joker_id = value == kOFCCardJoker1 ? 1
        : (value == kOFCCardJoker2 ? 2 : 0);
      std::cout << "MAP|" << value << '|' << rank << '|'
                << suit << '|' << joker_id << "\n";
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
      std::vector<int> cards;
      for (int i = 0; i < count; ++i) {
        int value = -999;
        if (!ReadValue(in, &value)) {
          cards.clear();
          break;
        }
        cards.push_back(value);
      }
      std::vector<COFCExactHandRank> ranks;
      std::string error;
      if (static_cast<int>(cards.size()) != count
          || !COFCExactEvaluator::EvaluateRowCandidates(
               cards, row == 0, &ranks, &error)
          || ranks.empty()) {
        std::cout << "ROW|0\n";
        continue;
      }
      std::cout << "ROW|1|";
      PrintRank(ranks[0]);
      std::cout << '|'
                << COFCExactEvaluator::RoyaltyForRow(
                     ranks[0], static_cast<EOFCRow>(row))
                << '|' << ranks.size() << "\n";
      continue;
    }

    if (command == "BOARD") {
      int values[13];
      bool parsed = true;
      for (int i = 0; i < 13; ++i) {
        if (!ReadValue(in, &values[i])) {
          parsed = false;
          break;
        }
      }
      if (!parsed) {
        std::cout << "ERR|BOARD_PARSE\n";
        continue;
      }
      COFCPlayerBoard board;
      for (int i = 0; i < 3; ++i) board.top[i].value = values[i];
      for (int i = 0; i < 5; ++i) board.middle[i].value = values[i + 3];
      for (int i = 0; i < 5; ++i) board.bottom[i].value = values[i + 8];
      COFCExactBoardResult result;
      std::string error;
      if (!COFCExactEvaluator::EvaluateBoard(board, &result, &error)
          || result.foul) {
        std::cout << "BOARD|0\n";
        continue;
      }
      std::cout << "BOARD|1|";
      PrintRank(result.rows[0]);
      std::cout << '|';
      PrintRank(result.rows[1]);
      std::cout << '|';
      PrintRank(result.rows[2]);
      std::cout << '|' << result.royalties
                << '|' << result.fantasy_cards << "\n";
      continue;
    }

    std::cout << "ERR|UNKNOWN_COMMAND\n";
  }
  return 0;
}
