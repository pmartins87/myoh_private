#include "deeppot_runtime_core.h"

#include <algorithm>
#include <cstring>
#include <fstream>
#include <iterator>

namespace deeppot_runtime {
namespace {

const char kMagic[8] = {'D','P','O','T','I','D','X','1'};
const std::uint32_t kIndexVersion = 1;

std::uint16_t ReadU16(const std::vector<std::uint8_t>& data, std::size_t pos) {
  return static_cast<std::uint16_t>(data[pos]) |
         (static_cast<std::uint16_t>(data[pos + 1]) << 8);
}

std::uint32_t ReadU32(const std::vector<std::uint8_t>& data, std::size_t pos) {
  return static_cast<std::uint32_t>(data[pos]) |
         (static_cast<std::uint32_t>(data[pos + 1]) << 8) |
         (static_cast<std::uint32_t>(data[pos + 2]) << 16) |
         (static_cast<std::uint32_t>(data[pos + 3]) << 24);
}

bool ReadWholeFile(const std::string& path, std::vector<std::uint8_t>* out) {
  std::ifstream in(path.c_str(), std::ios::binary);
  if (!in) return false;
  out->assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
  return in.good() || in.eof();
}

std::string JoinPath(const std::string& left, const std::string& right) {
  if (left.empty()) return right;
  const char last = left[left.size() - 1];
  if (last == '\\' || last == '/') return left + right;
  return left + "\\" + right;
}

int ScenarioCount(int n) { return (1 << n) - 2; }
int ScenarioOffset(int n) {
  int offset = 0;
  for (int k = 2; k < n; ++k) offset += ScenarioCount(k);
  return offset;
}

std::vector<std::array<int, 4> > SuitPermutations() {
  std::array<int, 4> p = {{0,1,2,3}};
  std::vector<std::array<int, 4> > out;
  do { out.push_back(p); } while (std::next_permutation(p.begin(), p.end()));
  return out;
}

std::array<std::uint8_t, 3> MapFlop(
    const std::array<Card, 3>& cards,
    const std::array<int, 4>& perm) {
  std::array<std::uint8_t, 3> out;
  for (std::size_t i = 0; i < 3; ++i) {
    out[i] = static_cast<std::uint8_t>((cards[i].rank - 2) * 4 + perm[cards[i].suit]);
  }
  std::sort(out.begin(), out.end());
  return out;
}

std::array<std::uint8_t, 2> MapHole(
    const std::array<Card, 2>& cards,
    const std::array<int, 4>& perm) {
  std::array<std::uint8_t, 2> out;
  for (std::size_t i = 0; i < 2; ++i) {
    out[i] = static_cast<std::uint8_t>((cards[i].rank - 2) * 4 + perm[cards[i].suit]);
  }
  std::sort(out.begin(), out.end());
  return out;
}

bool PairLess(
    const std::array<std::uint8_t, 3>& fa,
    const std::array<std::uint8_t, 2>& ha,
    const std::array<std::uint8_t, 3>& fb,
    const std::array<std::uint8_t, 2>& hb) {
  if (fa < fb) return true;
  if (fb < fa) return false;
  return ha < hb;
}

bool ValidAndUnique(const std::array<Card, 3>& flop, const std::array<Card, 2>& hole) {
  bool seen[52] = {false};
  const Card all[5] = {flop[0],flop[1],flop[2],hole[0],hole[1]};
  for (int i = 0; i < 5; ++i) {
    if (all[i].rank < 2 || all[i].rank > 14 || all[i].suit < 0 || all[i].suit > 3) return false;
    const int code = (all[i].rank - 2) * 4 + all[i].suit;
    if (seen[code]) return false;
    seen[code] = true;
  }
  return true;
}

void CanonicalState(
    const std::array<Card, 3>& flop,
    const std::array<Card, 2>& hole,
    std::array<std::uint8_t, 3>* best_flop,
    std::array<std::uint8_t, 2>* best_hole) {
  const std::vector<std::array<int, 4> > perms = SuitPermutations();
  bool first = true;
  for (std::size_t i = 0; i < perms.size(); ++i) {
    const std::array<std::uint8_t, 3> f = MapFlop(flop, perms[i]);
    const std::array<std::uint8_t, 2> h = MapHole(hole, perms[i]);
    if (first || PairLess(f, h, *best_flop, *best_hole)) {
      *best_flop = f;
      *best_hole = h;
      first = false;
    }
  }
}

std::array<std::uint8_t, 2> CanonicalHoleUnderStabilizer(
    const std::array<Card, 2>& hole,
    const std::vector<std::array<int, 4> >& stabilizer) {
  std::array<std::uint8_t, 2> best = {{255,255}};
  for (std::size_t i = 0; i < stabilizer.size(); ++i) {
    const std::array<std::uint8_t, 2> mapped = MapHole(hole, stabilizer[i]);
    if (mapped < best) best = mapped;
  }
  return best;
}

}  // namespace

QueryResult::QueryResult()
    : ok(false), stay(false), num_players(0), actor_index(-1),
      scenario_dense_id(-1), global_scenario_code(0), flop_index(-1),
      exact_hole_state_id(-1), error() {}

int QueryResult::EncodedAction() const {
  if (!ok || global_scenario_code <= 0) return 0;
  return stay ? global_scenario_code : -global_scenario_code;
}

Strategy::Strategy() : loaded_(false) {}

std::uint8_t Strategy::EncodeCard(const Card& card) {
  return static_cast<std::uint8_t>((card.rank - 2) * 4 + card.suit);
}

Card Strategy::DecodeCard(std::uint8_t code) {
  Card out;
  out.rank = 2 + static_cast<int>(code / 4);
  out.suit = static_cast<int>(code % 4);
  return out;
}

std::uint32_t Strategy::EncodeFlopKey(const std::array<std::uint8_t, 3>& cards) {
  return (static_cast<std::uint32_t>(cards[0]) << 12) |
         (static_cast<std::uint32_t>(cards[1]) << 6) |
         static_cast<std::uint32_t>(cards[2]);
}

std::uint16_t Strategy::EncodeHoleKey(const std::array<std::uint8_t, 2>& cards) {
  return static_cast<std::uint16_t>(
      (static_cast<std::uint16_t>(cards[0]) << 6) |
      static_cast<std::uint16_t>(cards[1]));
}

int Strategy::ScenarioDenseId(int num_players, int actor_index, std::uint32_t prior_stay_mask) {
  if (num_players < 2 || num_players > 8) return -1;
  if (actor_index < 0 || actor_index >= num_players) return -1;
  if (prior_stay_mask >= (static_cast<std::uint32_t>(1) << actor_index)) return -1;
  const int offset = (1 << actor_index) - 1;
  if (actor_index == num_players - 1) {
    if (prior_stay_mask == 0) return -1;
    return offset + static_cast<int>(prior_stay_mask) - 1;
  }
  return offset + static_cast<int>(prior_stay_mask);
}

int Strategy::GlobalScenarioCode(int num_players, int scenario_dense_id) {
  if (num_players < 2 || num_players > 8) return 0;
  const int count = ScenarioCount(num_players);
  if (scenario_dense_id < 0 || scenario_dense_id >= count) return 0;
  return ScenarioOffset(num_players) + scenario_dense_id + 1;
}

bool Strategy::Load(const std::string& package_root, std::string* error) {
  loaded_ = false;
  flops_.clear();
  slot_by_flop_.clear();
  hole_key_cache_.clear();
  for (int n = 0; n < 9; ++n) {
    mode_bits_[n].clear();
    mode_offsets_[n].clear();
  }

  std::vector<std::uint8_t> index;
  const std::string index_path = JoinPath(package_root, "deeppot_runtime_index.bin");
  if (!ReadWholeFile(index_path, &index)) {
    if (error) *error = "cannot read runtime index: " + index_path;
    return false;
  }
  if (index.size() < 16 || std::memcmp(&index[0], kMagic, 8) != 0) {
    if (error) *error = "invalid DeepPot runtime index magic";
    return false;
  }
  const std::uint32_t version = ReadU32(index, 8);
  const std::uint32_t count = ReadU32(index, 12);
  if (version != kIndexVersion) {
    if (error) *error = "unsupported DeepPot runtime index version";
    return false;
  }
  const std::uint64_t expected_index_size = 16u + static_cast<std::uint64_t>(count) * 7u;
  if (index.size() != expected_index_size || count == 0) {
    if (error) *error = "DeepPot runtime index length mismatch";
    return false;
  }

  std::size_t pos = 16;
  for (std::uint32_t i = 0; i < count; ++i) {
    FlopRecord row;
    row.flop_index = static_cast<int>(ReadU16(index, pos));
    row.card_codes[0] = index[pos + 2];
    row.card_codes[1] = index[pos + 3];
    row.card_codes[2] = index[pos + 4];
    row.hole_state_count = static_cast<int>(ReadU16(index, pos + 5));
    pos += 7;
    if (!(row.card_codes[0] < row.card_codes[1] && row.card_codes[1] < row.card_codes[2])) {
      if (error) *error = "runtime index contains non-sorted/duplicate flop cards";
      return false;
    }
    if (row.hole_state_count <= 0) {
      if (error) *error = "runtime index contains invalid hole-state count";
      return false;
    }
    const std::uint32_t key = EncodeFlopKey(row.card_codes);
    if (slot_by_flop_.find(key) != slot_by_flop_.end()) {
      if (error) *error = "runtime index contains duplicate canonical flop";
      return false;
    }
    slot_by_flop_[key] = flops_.size();
    flops_.push_back(row);
  }

  for (int n = 2; n <= 8; ++n) {
    const std::string filename = "N" + std::to_string(n) + "_final.bits";
    const std::string path = JoinPath(JoinPath(package_root, "strategy"), filename);
    if (!ReadWholeFile(path, &mode_bits_[n])) {
      if (error) *error = "cannot read strategy bitset: " + path;
      return false;
    }
    std::uint64_t cursor = 0;
    mode_offsets_[n].reserve(flops_.size());
    for (std::size_t slot = 0; slot < flops_.size(); ++slot) {
      mode_offsets_[n].push_back(cursor);
      const std::uint64_t bits = static_cast<std::uint64_t>(flops_[slot].hole_state_count) * ScenarioCount(n);
      cursor += (bits + 7u) / 8u;
    }
    if (mode_bits_[n].size() != cursor) {
      if (error) *error = "strategy bitset length mismatch for N=" + std::to_string(n);
      return false;
    }
  }

  hole_key_cache_.resize(flops_.size());
  loaded_ = true;
  if (error) error->clear();
  return true;
}

bool Strategy::EnsureHoleKeys(std::size_t slot, std::string* error) {
  if (slot >= flops_.size()) {
    if (error) *error = "flop slot out of range";
    return false;
  }
  if (!hole_key_cache_[slot].empty()) return true;

  const FlopRecord& row = flops_[slot];
  std::array<Card, 3> canonical_flop = {{
      DecodeCard(row.card_codes[0]), DecodeCard(row.card_codes[1]), DecodeCard(row.card_codes[2])}};
  const std::vector<std::array<int, 4> > perms = SuitPermutations();
  std::vector<std::array<int, 4> > stabilizer;
  for (std::size_t i = 0; i < perms.size(); ++i) {
    if (MapFlop(canonical_flop, perms[i]) == row.card_codes) stabilizer.push_back(perms[i]);
  }
  if (stabilizer.empty()) {
    if (error) *error = "canonical flop has empty suit stabilizer";
    return false;
  }

  bool excluded[52] = {false};
  excluded[row.card_codes[0]] = true;
  excluded[row.card_codes[1]] = true;
  excluded[row.card_codes[2]] = true;
  std::vector<Card> remaining;
  remaining.reserve(49);
  for (int code = 0; code < 52; ++code) {
    if (!excluded[code]) remaining.push_back(DecodeCard(static_cast<std::uint8_t>(code)));
  }

  std::vector<std::uint16_t> keys;
  keys.reserve(1176);
  for (std::size_t i = 0; i < remaining.size(); ++i) {
    for (std::size_t j = i + 1; j < remaining.size(); ++j) {
      const std::array<Card, 2> hole = {{remaining[i], remaining[j]}};
      keys.push_back(EncodeHoleKey(CanonicalHoleUnderStabilizer(hole, stabilizer)));
    }
  }
  std::sort(keys.begin(), keys.end());
  keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
  if (static_cast<int>(keys.size()) != row.hole_state_count) {
    if (error) *error = "C++ exact hole-state index disagrees with packaged count";
    return false;
  }
  hole_key_cache_[slot].swap(keys);
  return true;
}

QueryResult Strategy::Query(
    int num_players,
    int actor_index,
    std::uint32_t prior_stay_mask,
    const std::array<Card, 3>& flop,
    const std::array<Card, 2>& hole) {
  QueryResult result;
  result.num_players = num_players;
  result.actor_index = actor_index;
  if (!loaded_) { result.error = "runtime strategy is not loaded"; return result; }
  if (!ValidAndUnique(flop, hole)) { result.error = "invalid or duplicate cards"; return result; }

  const int scenario = ScenarioDenseId(num_players, actor_index, prior_stay_mask);
  if (scenario < 0) { result.error = "invalid/terminal public scenario"; return result; }
  result.scenario_dense_id = scenario;
  result.global_scenario_code = GlobalScenarioCode(num_players, scenario);
  if (result.global_scenario_code == 0) { result.error = "global scenario encoding failed"; return result; }

  std::array<std::uint8_t, 3> canonical_flop;
  std::array<std::uint8_t, 2> canonical_hole;
  CanonicalState(flop, hole, &canonical_flop, &canonical_hole);
  const std::unordered_map<std::uint32_t, std::size_t>::const_iterator found =
      slot_by_flop_.find(EncodeFlopKey(canonical_flop));
  if (found == slot_by_flop_.end()) { result.error = "canonical flop not present in runtime package"; return result; }
  const std::size_t slot = found->second;
  const FlopRecord& row = flops_[slot];
  result.flop_index = row.flop_index;

  std::string hole_error;
  if (!EnsureHoleKeys(slot, &hole_error)) { result.error = hole_error; return result; }
  const std::uint16_t target = EncodeHoleKey(canonical_hole);
  const std::vector<std::uint16_t>& keys = hole_key_cache_[slot];
  const std::vector<std::uint16_t>::const_iterator it = std::lower_bound(keys.begin(), keys.end(), target);
  if (it == keys.end() || *it != target) { result.error = "canonical hole state missing from exact runtime index"; return result; }
  const int hole_id = static_cast<int>(it - keys.begin());
  result.exact_hole_state_id = hole_id;

  const std::uint64_t key = static_cast<std::uint64_t>(scenario) * row.hole_state_count + hole_id;
  const std::uint64_t byte_index = mode_offsets_[num_players][slot] + (key >> 3);
  if (byte_index >= mode_bits_[num_players].size()) { result.error = "strategy bit address out of range"; return result; }
  result.stay = (mode_bits_[num_players][static_cast<std::size_t>(byte_index)] &
                 static_cast<std::uint8_t>(1u << (key & 7u))) != 0;
  result.ok = true;
  result.error.clear();
  return result;
}

}  // namespace deeppot_runtime
