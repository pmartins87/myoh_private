#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace deeppot_runtime {

struct Card {
  int rank;
  int suit;
};

struct QueryResult {
  bool ok;
  bool stay;
  int num_players;
  int actor_index;
  int scenario_dense_id;
  int global_scenario_code;
  int flop_index;
  int exact_hole_state_id;
  std::string error;

  QueryResult();
  int EncodedAction() const;
};

class Strategy {
 public:
  Strategy();
  bool Load(const std::string& package_root, std::string* error);
  bool loaded() const { return loaded_; }

  QueryResult Query(
      int num_players,
      int actor_index,
      std::uint32_t prior_stay_mask,
      const std::array<Card, 3>& flop,
      const std::array<Card, 2>& hole);

  static int ScenarioDenseId(int num_players, int actor_index, std::uint32_t prior_stay_mask);
  static int GlobalScenarioCode(int num_players, int scenario_dense_id);

 private:
  struct FlopRecord {
    int flop_index;
    std::array<std::uint8_t, 3> card_codes;
    int hole_state_count;
  };

  bool loaded_;
  std::vector<FlopRecord> flops_;
  std::unordered_map<std::uint32_t, std::size_t> slot_by_flop_;
  std::vector<std::uint8_t> mode_bits_[9];
  std::vector<std::uint64_t> mode_offsets_[9];
  std::vector<std::vector<std::uint16_t> > hole_key_cache_;

  static std::uint8_t EncodeCard(const Card& card);
  static Card DecodeCard(std::uint8_t code);
  static std::uint32_t EncodeFlopKey(const std::array<std::uint8_t, 3>& cards);
  static std::uint16_t EncodeHoleKey(const std::array<std::uint8_t, 2>& cards);
  bool EnsureHoleKeys(std::size_t slot, std::string* error);
};

}  // namespace deeppot_runtime
