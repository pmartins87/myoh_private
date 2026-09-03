//******************************************************************************
// OpenOFC PLAYABLE P3 Normal/Normal policy bridge (shadow-only).
//******************************************************************************

#ifndef DEEPOFC_P3_STANDALONE
#include "StdAfx.h"
#endif

#include "COFCP3Policy.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <utility>

using namespace std;

namespace {

const char kAuthority[] = "SHADOW_ONLY_NO_PHYSICAL_EXECUTION_AUTHORITY";
const char kNativeManifestSha256[] =
    "ff880a76bce9885f19b7297952a9d182d0ba2c54e10681baa74937f66b4691bc";
const char kNativeManifestFileSha256[] =
    "afe3161c6a944f761485742e37271a6079188fd7b258c79ad2740c36e6ca9381";
const char kP2ManifestSha256[] =
    "f10c079a61ba08832cfc334afb9c055e023dfc9c23a24140d02b2f7bd8413898";
const char kP2SourceCommit[] = "3d04fe96fa41e2eb2709b01dc7f8c02e709eb163";
const char kWeightMagic[] = "DOFCP3W1";
const uint32_t kWeightVersion = 1;
const uint32_t kInteractionBuckets = 65536;
const uint32_t kActionSize = 216;
const uint32_t kOffsetAction = 2060;
const uint32_t kPredictionDimension = 65753;
const size_t kWeightHeaderBytes = 152;
const uint64_t kMask64 = ~static_cast<uint64_t>(0);

struct ExpectedRoute {
  int button;
  const char *state;
  const char *source_file_sha256;
  const char *route_sha256;
  const char *snapshot_sha256;
  const char *model_sha256;
  const char *weight_file_sha256;
  size_t nonzero_weights;
};

const ExpectedRoute kExpectedRoutes[2] = {
  {
    0,
    "B0:P0F0:P1F0",
    "8ecf7a2dd6455e3022fab3e4c26100f5cbbd48508acd1fdebf694a8b30db714a",
    "5f8600bc035197f00de68969c8e0f025a10f1094888999f134f83586f8aa98e1",
    "c6f3f212189e03232345f7ae5dcf30ed0a89e00aa1928a6451d6aab23dcfc92d",
    "9cc5d4f09387bee64ea18e91677653e164e878c2153c2f12b232f777ca202f71",
    "52be780cda5b0e36da645e6ea36fc07dd445fcc6785281a769a91d8fce0d699c",
    63437
  },
  {
    1,
    "B1:P0F0:P1F0",
    "d47f45f09d266f295a8d62ca137ace58e1e26c2383c3484c978143b3d8cf9eac",
    "4d8d53adf077c0fe4759a7ed876261542adb60983f278bb3cd4de535eed27f0d",
    "31f745f80b9141f7e0dc41905ca57746a259e420ccee2314eb255a1b54fc7302",
    "5b65fc728c90c65cf17b4462140ea843d80085166e738cb0204460200d337779",
    "08e3b9d2523f092aee45fddc1170e9ffb7486595ea2f36f8c6db7296df27a0d3",
    63430
  }
};

bool Fail(string *error, const string &message) {
  if (error != NULL) *error = message;
  return false;
}

// Small dependency-free SHA-256 implementation used only for immutable policy
// files and decision receipts.  Keeping it local makes the standalone parity
// test exercise exactly the same integrity path as the Windows runtime.
class Sha256 {
 public:
  Sha256() : data_length_(0), bit_length_(0) {
    state_[0] = 0x6a09e667U;
    state_[1] = 0xbb67ae85U;
    state_[2] = 0x3c6ef372U;
    state_[3] = 0xa54ff53aU;
    state_[4] = 0x510e527fU;
    state_[5] = 0x9b05688cU;
    state_[6] = 0x1f83d9abU;
    state_[7] = 0x5be0cd19U;
  }

  void Update(const unsigned char *data, size_t length) {
    for (size_t i = 0; i < length; ++i) {
      data_[data_length_++] = data[i];
      if (data_length_ == 64) {
        Transform();
        bit_length_ += 512;
        data_length_ = 0;
      }
    }
  }

  string FinalHex() {
    size_t i = data_length_;
    data_[i++] = 0x80;
    if (i > 56) {
      while (i < 64) data_[i++] = 0;
      Transform();
      i = 0;
    }
    while (i < 56) data_[i++] = 0;
    bit_length_ += static_cast<uint64_t>(data_length_) * 8;
    for (int shift = 56; shift >= 0; shift -= 8) {
      data_[i++] = static_cast<unsigned char>((bit_length_ >> shift) & 0xffU);
    }
    Transform();
    ostringstream out;
    out << hex << setfill('0');
    for (int word = 0; word < 8; ++word) out << setw(8) << state_[word];
    return out.str();
  }

 private:
  static uint32_t RotateRight(uint32_t value, uint32_t count) {
    return (value >> count) | (value << (32U - count));
  }

  void Transform() {
    static const uint32_t k[64] = {
      0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
      0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
      0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
      0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
      0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
      0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
      0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
      0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
      0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
      0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
      0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
      0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
      0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
      0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
      0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
      0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U
    };
    uint32_t words[64];
    for (int i = 0; i < 16; ++i) {
      const int j = i * 4;
      words[i] = (static_cast<uint32_t>(data_[j]) << 24)
        | (static_cast<uint32_t>(data_[j + 1]) << 16)
        | (static_cast<uint32_t>(data_[j + 2]) << 8)
        | static_cast<uint32_t>(data_[j + 3]);
    }
    for (int i = 16; i < 64; ++i) {
      const uint32_t s0 = RotateRight(words[i - 15], 7)
        ^ RotateRight(words[i - 15], 18) ^ (words[i - 15] >> 3);
      const uint32_t s1 = RotateRight(words[i - 2], 17)
        ^ RotateRight(words[i - 2], 19) ^ (words[i - 2] >> 10);
      words[i] = words[i - 16] + s0 + words[i - 7] + s1;
    }
    uint32_t a = state_[0];
    uint32_t b = state_[1];
    uint32_t c = state_[2];
    uint32_t d = state_[3];
    uint32_t e = state_[4];
    uint32_t f = state_[5];
    uint32_t g = state_[6];
    uint32_t h = state_[7];
    for (int i = 0; i < 64; ++i) {
      const uint32_t s1 = RotateRight(e, 6) ^ RotateRight(e, 11)
        ^ RotateRight(e, 25);
      const uint32_t choice = (e & f) ^ ((~e) & g);
      const uint32_t temp1 = h + s1 + choice + k[i] + words[i];
      const uint32_t s0 = RotateRight(a, 2) ^ RotateRight(a, 13)
        ^ RotateRight(a, 22);
      const uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
      const uint32_t temp2 = s0 + majority;
      h = g;
      g = f;
      f = e;
      e = d + temp1;
      d = c;
      c = b;
      b = a;
      a = temp1 + temp2;
    }
    state_[0] += a;
    state_[1] += b;
    state_[2] += c;
    state_[3] += d;
    state_[4] += e;
    state_[5] += f;
    state_[6] += g;
    state_[7] += h;
  }

  unsigned char data_[64];
  size_t data_length_;
  uint64_t bit_length_;
  uint32_t state_[8];
};

string Sha256Hex(const unsigned char *data, size_t length) {
  Sha256 hash;
  hash.Update(data, length);
  return hash.FinalHex();
}

string Sha256Hex(const string &text) {
  return Sha256Hex(
      reinterpret_cast<const unsigned char *>(text.data()), text.size());
}

bool ReadFile(const string &path, vector<unsigned char> *out, string *error) {
  ifstream input(path.c_str(), ios::binary);
  if (!input) return Fail(error, "cannot open P3 policy file: " + path);
  input.seekg(0, ios::end);
  const streamoff length = input.tellg();
  if (length < 0) return Fail(error, "cannot size P3 policy file: " + path);
  input.seekg(0, ios::beg);
  out->assign(static_cast<size_t>(length), 0);
  if (length > 0) {
    input.read(
        reinterpret_cast<char *>(&(*out)[0]), static_cast<streamsize>(length));
  }
  if (!input || input.gcount() != static_cast<streamsize>(length)) {
    return Fail(error, "cannot read complete P3 policy file: " + path);
  }
  return true;
}

string HexBytes(const unsigned char *data, size_t length) {
  ostringstream out;
  out << hex << setfill('0');
  for (size_t i = 0; i < length; ++i) {
    out << setw(2) << static_cast<unsigned int>(data[i]);
  }
  return out.str();
}

uint32_t ReadU32LE(const unsigned char *data) {
  return static_cast<uint32_t>(data[0])
    | (static_cast<uint32_t>(data[1]) << 8)
    | (static_cast<uint32_t>(data[2]) << 16)
    | (static_cast<uint32_t>(data[3]) << 24);
}

uint64_t ReadU64LE(const unsigned char *data) {
  uint64_t value = 0;
  for (int i = 7; i >= 0; --i) value = (value << 8) | data[i];
  return value;
}

string JoinPath(const string &directory, const string &filename) {
  if (directory.empty()) return filename;
  const char last = directory[directory.size() - 1];
  if (last == '/' || last == '\\') return directory + filename;
#ifdef _WIN32
  return directory + "\\" + filename;
#else
  return directory + "/" + filename;
#endif
}

const COFCCard *RowCards(
    const COFCPlayerBoard &board, EOFCRow row, int *capacity) {
  switch (row) {
    case kOFCRowTop:
      *capacity = kOFCTopCards;
      return board.top;
    case kOFCRowMiddle:
      *capacity = kOFCMiddleCards;
      return board.middle;
    case kOFCRowBottom:
      *capacity = kOFCBottomCards;
      return board.bottom;
    default:
      *capacity = 0;
      return NULL;
  }
}

vector<int> KnownRowValues(const COFCPlayerBoard &board, EOFCRow row) {
  int capacity = 0;
  const COFCCard *cards = RowCards(board, row, &capacity);
  vector<int> values;
  for (int i = 0; i < capacity; ++i) {
    if (cards[i].IsKnownPhysicalCard()) values.push_back(cards[i].value);
  }
  sort(values.begin(), values.end());
  return values;
}

bool BoardDelta(
    const COFCPlayerBoard &before,
    const COFCPlayerBoard &after,
    vector<COFCP3PublicPlacement> *delta,
    string *error) {
  delta->clear();
  set<int> seen;
  for (int row = 0; row < 3; ++row) {
    const EOFCRow target = static_cast<EOFCRow>(row);
    const vector<int> old_values = KnownRowValues(before, target);
    const vector<int> new_values = KnownRowValues(after, target);
    for (size_t i = 0; i < new_values.size(); ++i) {
      if (!seen.insert(new_values[i]).second) {
        return Fail(error, "public board repeats a physical card");
      }
    }
    for (size_t i = 0; i < old_values.size(); ++i) {
      if (!binary_search(new_values.begin(), new_values.end(), old_values[i])) {
        return Fail(error, "public committed card moved or disappeared");
      }
    }
    for (size_t i = 0; i < new_values.size(); ++i) {
      if (!binary_search(old_values.begin(), old_values.end(), new_values[i])) {
        delta->push_back(COFCP3PublicPlacement(new_values[i], target));
      }
    }
  }
  return true;
}

bool SameBoard(
    const COFCPlayerBoard &left, const COFCPlayerBoard &right) {
  for (int row = 0; row < 3; ++row) {
    const EOFCRow target = static_cast<EOFCRow>(row);
    if (KnownRowValues(left, target) != KnownRowValues(right, target)) {
      return false;
    }
  }
  return true;
}

int BoardCount(const COFCPlayerBoard &board) {
  int count = 0;
  for (int row = 0; row < 3; ++row) {
    count += static_cast<int>(
        KnownRowValues(board, static_cast<EOFCRow>(row)).size());
  }
  return count;
}

bool IsPhysicalCard(int value) {
  return (value >= 0 && value <= 51)
    || value == kOFCCardJoker1 || value == kOFCCardJoker2;
}

string CardToken(int value, const array<int, 4> &suit_map) {
  if (value == kOFCCardJoker1) return "JK1";
  if (value == kOFCCardJoker2) return "JK2";
  if (value < 0 || value > 51) return "INVALID";
  static const char ranks[] = "23456789TJQKA";
  static const char suits[] = "cdhs";
  const int rank = value % 13;
  const int suit = value / 13;
  string token;
  token.push_back(ranks[rank]);
  token.push_back(suits[suit_map[suit]]);
  return token;
}

int CardFeatureIndex(int value, const array<int, 4> &suit_map) {
  if (value == kOFCCardJoker1) return 52;
  if (value == kOFCCardJoker2) return 53;
  if (value < 0 || value > 51) return -1;
  return (value % 13) * 4 + suit_map[value / 13];
}

string JsonStringArray(vector<string> values) {
  sort(values.begin(), values.end());
  ostringstream out;
  out << "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i != 0) out << ",";
    out << "\"" << values[i] << "\"";
  }
  out << "]";
  return out.str();
}

string BoardJson(const COFCPlayerBoard &board, const array<int, 4> &suit_map) {
  ostringstream out;
  out << "[";
  for (int row = 0; row < 3; ++row) {
    if (row != 0) out << ",";
    const vector<int> cards = KnownRowValues(board, static_cast<EOFCRow>(row));
    vector<string> tokens;
    for (size_t i = 0; i < cards.size(); ++i) {
      tokens.push_back(CardToken(cards[i], suit_map));
    }
    out << JsonStringArray(tokens);
  }
  out << "]";
  return out.str();
}

string CardListJson(
    const COFCCard *cards, int count, const array<int, 4> &suit_map) {
  vector<string> tokens;
  for (int i = 0; i < count; ++i) {
    tokens.push_back(CardToken(cards[i].value, suit_map));
  }
  return JsonStringArray(tokens);
}

string HistoryJson(
    const vector<COFCP3PublicActionEvent> &events,
    const array<int, 4> &suit_map) {
  ostringstream out;
  out << "[";
  for (size_t i = 0; i < events.size(); ++i) {
    if (i != 0) out << ",";
    vector<pair<string, int> > placements;
    for (size_t j = 0; j < events[i].placements.size(); ++j) {
      placements.push_back(make_pair(
          CardToken(events[i].placements[j].card_value, suit_map),
          static_cast<int>(events[i].placements[j].row)));
    }
    sort(placements.begin(), placements.end());
    out << "[" << events[i].round_index << "," << events[i].player_role
        << ",[";
    for (size_t j = 0; j < placements.size(); ++j) {
      if (j != 0) out << ",";
      out << "[\"" << placements[j].first << "\"," << placements[j].second
          << "]";
    }
    out << "]]";
  }
  out << "]";
  return out.str();
}

string InformationKey(
    const COFCState &state,
    const COFCP3PublicHistory &history,
    int actor_role,
    const array<int, 4> &suit_map) {
  const int self_chair = history.ChairForRole(actor_role);
  const int opponent_chair = history.ChairForRole(1 - actor_role);
  ostringstream out;
  // json.dumps(sort_keys=True, separators=(",", ":")) field order.
  out << "{\"incoming\":"
      << CardListJson(
          state.hero_incoming, state.hero_incoming_count, suit_map)
      << ",\"opp_board\":"
      << BoardJson(state.players[opponent_chair].board, suit_map)
      << ",\"own_discards\":"
      << CardListJson(state.hero_discards, state.hero_discard_count, suit_map)
      << ",\"player\":" << actor_role
      << ",\"position\":\""
      << (actor_role == 0 ? "nondealer_first" : "dealer_button_second")
      << "\",\"public_history\":" << HistoryJson(history.events(), suit_map)
      << ",\"round\":" << state.round_index
      << ",\"self_board\":"
      << BoardJson(state.players[self_chair].board, suit_map)
      << ",\"symmetry\":\"suit24-exact\",\"v\":2}";
  return out.str();
}

struct NativeAction {
  int rows[5];
  int discard_index;
  string canonical_key;

  NativeAction() : discard_index(-1) {
    for (int i = 0; i < 5; ++i) rows[i] = -2;
  }
};

void EnumerateActionRows(
    int incoming_count,
    int index,
    int discard_index,
    int row_counts[3],
    NativeAction current,
    vector<NativeAction> *out) {
  if (index == incoming_count) {
    out->push_back(current);
    return;
  }
  if (index == discard_index) {
    current.rows[index] = -1;
    EnumerateActionRows(
        incoming_count, index + 1, discard_index, row_counts, current, out);
    return;
  }
  const int capacities[3] = {kOFCTopCards, kOFCMiddleCards, kOFCBottomCards};
  for (int row = 0; row < 3; ++row) {
    if (row_counts[row] >= capacities[row]) continue;
    ++row_counts[row];
    current.rows[index] = row;
    EnumerateActionRows(
        incoming_count, index + 1, discard_index, row_counts, current, out);
    --row_counts[row];
  }
}

string ActionKey(
    const COFCState &state,
    const NativeAction &action,
    const array<int, 4> &suit_map) {
  vector<pair<string, int> > placements;
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    if (i == action.discard_index) continue;
    placements.push_back(make_pair(
        CardToken(state.hero_incoming[i].value, suit_map), action.rows[i]));
  }
  sort(placements.begin(), placements.end());
  ostringstream out;
  out << "{\"d\":";
  if (action.discard_index < 0) {
    out << "null";
  } else {
    out << "\""
        << CardToken(state.hero_incoming[action.discard_index].value, suit_map)
        << "\"";
  }
  out << ",\"p\":[";
  for (size_t i = 0; i < placements.size(); ++i) {
    if (i != 0) out << ",";
    out << "[\"" << placements[i].first << "\"," << placements[i].second
        << "]";
  }
  out << "]}";
  return out.str();
}

bool EnumerateLegalActions(
    const COFCState &state,
    const array<int, 4> &suit_map,
    vector<NativeAction> *actions,
    string *error) {
  actions->clear();
  const int expected = state.round_index == 0 ? 5 : 3;
  if (state.hero_incoming_count != expected) {
    return Fail(error, "P3 incoming count disagrees with normal round");
  }
  int row_counts[3] = {
    static_cast<int>(KnownRowValues(
        state.players[state.hero_chair].board, kOFCRowTop).size()),
    static_cast<int>(KnownRowValues(
        state.players[state.hero_chair].board, kOFCRowMiddle).size()),
    static_cast<int>(KnownRowValues(
        state.players[state.hero_chair].board, kOFCRowBottom).size())
  };
  if (state.round_index == 0) {
    NativeAction action;
    EnumerateActionRows(expected, 0, -1, row_counts, action, actions);
  } else {
    for (int discard = 0; discard < expected; ++discard) {
      NativeAction action;
      action.discard_index = discard;
      EnumerateActionRows(
          expected, 0, discard, row_counts, action, actions);
    }
  }
  for (size_t i = 0; i < actions->size(); ++i) {
    (*actions)[i].canonical_key = ActionKey(state, (*actions)[i], suit_map);
  }
  sort(actions->begin(), actions->end(),
      [](const NativeAction &left, const NativeAction &right) {
        return left.canonical_key < right.canonical_key;
      });
  for (size_t i = 1; i < actions->size(); ++i) {
    if ((*actions)[i - 1].canonical_key == (*actions)[i].canonical_key) {
      return Fail(error, "P3 canonical legal action keys collided");
    }
  }
  if (actions->empty()) return Fail(error, "P3 state has no legal normal action");
  return true;
}

void AddBoardFeatures(
    set<int> *features,
    int offset,
    const COFCPlayerBoard &board,
    const array<int, 4> &suit_map) {
  for (int row = 0; row < 3; ++row) {
    const vector<int> cards = KnownRowValues(board, static_cast<EOFCRow>(row));
    for (size_t i = 0; i < cards.size(); ++i) {
      features->insert(offset + row * 54 + CardFeatureIndex(cards[i], suit_map));
    }
  }
}

vector<int> StateFeatures(
    const COFCState &state,
    const COFCP3PublicHistory &history,
    int actor_role,
    const array<int, 4> &suit_map) {
  const int kOffsetPlayer = 1;
  const int kOffsetRound = 3;
  const int kOffsetSelfBoard = 8;
  const int kOffsetOpponentBoard = 170;
  const int kOffsetOwnDiscards = 332;
  const int kOffsetIncoming = 386;
  const int kOffsetPublicHistory = 440;
  set<int> features;
  features.insert(0);
  features.insert(kOffsetPlayer + actor_role);
  features.insert(kOffsetRound + state.round_index);
  AddBoardFeatures(
      &features, kOffsetSelfBoard,
      state.players[history.ChairForRole(actor_role)].board, suit_map);
  AddBoardFeatures(
      &features, kOffsetOpponentBoard,
      state.players[history.ChairForRole(1 - actor_role)].board, suit_map);
  for (int i = 0; i < state.hero_discard_count; ++i) {
    features.insert(kOffsetOwnDiscards
        + CardFeatureIndex(state.hero_discards[i].value, suit_map));
  }
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    features.insert(kOffsetIncoming
        + CardFeatureIndex(state.hero_incoming[i].value, suit_map));
  }
  const vector<COFCP3PublicActionEvent> &events = history.events();
  for (size_t i = 0; i < events.size(); ++i) {
    for (size_t j = 0; j < events[i].placements.size(); ++j) {
      const COFCP3PublicPlacement &placement = events[i].placements[j];
      const int base = (((events[i].round_index * 2 + events[i].player_role)
          * 3 + static_cast<int>(placement.row)) * 54);
      features.insert(kOffsetPublicHistory + base
          + CardFeatureIndex(placement.card_value, suit_map));
    }
  }
  return vector<int>(features.begin(), features.end());
}

vector<int> ActionFeatures(
    const COFCState &state,
    const NativeAction &action,
    const array<int, 4> &suit_map) {
  set<int> features;
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    const int card = CardFeatureIndex(state.hero_incoming[i].value, suit_map);
    if (i == action.discard_index) {
      features.insert(static_cast<int>(kOffsetAction) + 3 * 54 + card);
    } else {
      features.insert(static_cast<int>(kOffsetAction) + action.rows[i] * 54 + card);
    }
  }
  return vector<int>(features.begin(), features.end());
}

uint64_t Mix64(uint64_t value) {
  uint64_t x = value & kMask64;
  x ^= x >> 30;
  x = (x * UINT64_C(0xBF58476D1CE4E5B9)) & kMask64;
  x ^= x >> 27;
  x = (x * UINT64_C(0x94D049BB133111EB)) & kMask64;
  x ^= x >> 31;
  return x & kMask64;
}

double Predict(
    const vector<double> &weights,
    const vector<int> &state_features,
    const vector<int> &action_features) {
  map<int, double> terms;
  terms[0] = 1.0;
  const int interaction_offset = 1 + static_cast<int>(kActionSize);
  for (size_t a = 0; a < action_features.size(); ++a) {
    const int local_action = action_features[a] - static_cast<int>(kOffsetAction);
    terms[1 + local_action] += 1.0;
    for (size_t s = 0; s < state_features.size(); ++s) {
      const uint64_t seed =
          (static_cast<uint64_t>(state_features[s] + 1)
              * UINT64_C(0x9E3779B185EBCA87))
          ^ (static_cast<uint64_t>(local_action + 1)
              * UINT64_C(0xC2B2AE3D27D4EB4F));
      const uint64_t mixed = Mix64(seed);
      const int bucket = static_cast<int>(mixed & (kInteractionBuckets - 1));
      const double sign = (mixed >> 63) ? -1.0 : 1.0;
      terms[interaction_offset + bucket] += sign;
    }
  }
  double value = 0.0;
  for (map<int, double>::const_iterator it = terms.begin(); it != terms.end(); ++it) {
    if (it->second != 0.0) value += weights[it->first] * it->second;
  }
  return value;
}

bool ConvertAction(
    const COFCState &state,
    const NativeAction &selected,
    COFCStrategyAction *action,
    string *error) {
  action->Reset();
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    if (i == selected.discard_index) {
      action->unused_cards[action->unused_count++] = state.hero_incoming[i].value;
    } else {
      COFCStrategyPlacement &placement =
          action->placements[action->placement_count++];
      placement.card_value = state.hero_incoming[i].value;
      placement.row = static_cast<EOFCRow>(selected.rows[i]);
    }
  }
  const int expected_placements = state.round_index == 0 ? 5 : 2;
  const int expected_unused = state.round_index == 0 ? 0 : 1;
  action->valid = action->placement_count == expected_placements
    && action->unused_count == expected_unused;
  if (!action->valid) return Fail(error, "P3 selected action conversion failed");
  return true;
}

bool ValidateKnownUniqueness(const COFCState &state, string *error) {
  set<int> seen;
  for (int player = 0; player < state.player_count; ++player) {
    for (int row = 0; row < 3; ++row) {
      const vector<int> cards = KnownRowValues(
          state.players[player].board, static_cast<EOFCRow>(row));
      for (size_t i = 0; i < cards.size(); ++i) {
        if (!seen.insert(cards[i]).second) {
          return Fail(error, "P3 state repeats a public physical card");
        }
      }
    }
  }
  for (int i = 0; i < state.hero_discard_count; ++i) {
    if (!IsPhysicalCard(state.hero_discards[i].value)
        || !seen.insert(state.hero_discards[i].value).second) {
      return Fail(error, "P3 state has invalid/repeated Hero discard");
    }
  }
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    if (!IsPhysicalCard(state.hero_incoming[i].value)
        || !seen.insert(state.hero_incoming[i].value).second) {
      return Fail(error, "P3 state has invalid/repeated Hero incoming card");
    }
  }
  return true;
}

bool LoadRouteFile(
    const string &path,
    const ExpectedRoute &expected,
    COFCP3Policy::RouteWeights *route,
    string *error) {
  vector<unsigned char> raw;
  if (!ReadFile(path, &raw, error)) return false;
  if (Sha256Hex(&raw[0], raw.size()) != expected.weight_file_sha256) {
    return Fail(error, "P3 native weight-file SHA-256 mismatch");
  }
  if (raw.size() != kWeightHeaderBytes
      + static_cast<size_t>(kPredictionDimension) * 8) {
    return Fail(error, "P3 native weight-file length mismatch");
  }
  if (memcmp(&raw[0], kWeightMagic, 8) != 0
      || ReadU32LE(&raw[8]) != kWeightVersion
      || ReadU32LE(&raw[12]) != static_cast<uint32_t>(expected.button)
      || ReadU32LE(&raw[16]) != kInteractionBuckets
      || ReadU32LE(&raw[20]) != kPredictionDimension) {
    return Fail(error, "P3 native weight header format mismatch");
  }
  if (HexBytes(&raw[24], 32) != kP2ManifestSha256
      || HexBytes(&raw[56], 32) != expected.model_sha256
      || HexBytes(&raw[88], 32) != expected.snapshot_sha256
      || HexBytes(&raw[120], 32) != expected.route_sha256) {
    return Fail(error, "P3 native weight header identity mismatch");
  }
  COFCP3Policy::RouteWeights loaded;
  loaded.button = expected.button;
  loaded.route_sha256 = expected.route_sha256;
  loaded.snapshot_sha256 = expected.snapshot_sha256;
  loaded.model_sha256 = expected.model_sha256;
  loaded.file_sha256 = expected.weight_file_sha256;
  loaded.values.resize(kPredictionDimension);
  size_t nonzero = 0;
  for (size_t i = 0; i < loaded.values.size(); ++i) {
    const uint64_t bits = ReadU64LE(&raw[kWeightHeaderBytes + i * 8]);
    double value = 0.0;
    memcpy(&value, &bits, sizeof(value));
    if (!std::isfinite(value)) {
      return Fail(error, "P3 native weight file contains non-finite data");
    }
    loaded.values[i] = value;
    if (value != 0.0) ++nonzero;
  }
  if (nonzero != expected.nonzero_weights) {
    return Fail(error, "P3 native weight nonzero count mismatch");
  }
  *route = loaded;
  return true;
}

}  // namespace

COFCP3PublicHistory::COFCP3PublicHistory() { Invalidate(); }

void COFCP3PublicHistory::Invalidate() {
  valid_ = false;
  hero_chair_ = -1;
  button_identity_ = -1;
  role_chairs_[0] = -1;
  role_chairs_[1] = -1;
  observed_boards_[0].Reset();
  observed_boards_[1].Reset();
  events_.clear();
}

int COFCP3PublicHistory::RoleForChair(int chair) const {
  if (chair == role_chairs_[0]) return 0;
  if (chair == role_chairs_[1]) return 1;
  return -1;
}

int COFCP3PublicHistory::ChairForRole(int role) const {
  return role == 0 || role == 1 ? role_chairs_[role] : -1;
}

bool COFCP3PublicHistory::ValidateStableHand(
    const COFCState &state, string *error) const {
  if (!valid_) return Fail(error, "P3 public history is not initialized");
  if (!state.valid || state.schema_version != kOFCStateSchemaVersion) {
    return Fail(error, "P3 public history received invalid state/schema");
  }
  if (state.player_count != 2 || state.hero_chair != hero_chair_
      || state.dealer_chair != button_identity_) {
    return Fail(error, "P3 HU seat/dealer identity changed inside hand");
  }
  if (state.round_index < 0 || state.round_index > 4) {
    return Fail(error, "P3 public history requires normal round 0..4");
  }
  for (int chair = 0; chair < 2; ++chair) {
    if (!state.players[chair].occupied
        || state.players[chair].source_chair != chair
        || state.players[chair].fantasy
        || state.players[chair].sitting_out) {
      return Fail(error, "P3 supports stable occupied Normal/Normal HU seats only");
    }
  }
  return true;
}

bool COFCP3PublicHistory::ResetForKnownNewHand(
    const COFCState &state, string *error) {
  Invalidate();
  if (!state.valid || state.player_count != 2
      || state.hero_chair < 0 || state.hero_chair > 1
      || state.dealer_chair < 0 || state.dealer_chair > 1
      || state.round_index != 0) {
    return Fail(error, "P3 history reset requires a known HU normal round-0 hand");
  }
  hero_chair_ = state.hero_chair;
  button_identity_ = state.dealer_chair;
  role_chairs_[0] = 1 - button_identity_;
  role_chairs_[1] = button_identity_;
  observed_boards_[0].Reset();
  observed_boards_[1].Reset();
  events_.clear();
  valid_ = true;
  if (!ValidateStableHand(state, error) || !Observe(state, error)) {
    Invalidate();
    return false;
  }
  return true;
}

bool COFCP3PublicHistory::Observe(const COFCState &state, string *error) {
  if (!ValidateStableHand(state, error)) {
    Invalidate();
    return false;
  }
  vector<COFCP3PublicPlacement> deltas[2];
  for (int role = 0; role < 2; ++role) {
    if (!BoardDelta(
          observed_boards_[role], state.players[role_chairs_[role]].board,
          &deltas[role], error)) {
      Invalidate();
      return false;
    }
  }

  while (events_.size() < 10) {
    const int expected_round = static_cast<int>(events_.size() / 2);
    const int expected_role = static_cast<int>(events_.size() % 2);
    if (deltas[expected_role].empty()) break;
    const size_t expected_count = expected_round == 0 ? 5U : 2U;
    if (deltas[expected_role].size() != expected_count
        || expected_round > state.round_index) {
      Invalidate();
      return Fail(error, "P3 public board delta cannot be one exact next action");
    }
    COFCP3PublicActionEvent event;
    event.round_index = expected_round;
    event.player_role = expected_role;
    event.placements = deltas[expected_role];
    events_.push_back(event);
    observed_boards_[expected_role] =
        state.players[role_chairs_[expected_role]].board;
    deltas[expected_role].clear();
  }
  if (!deltas[0].empty() || !deltas[1].empty()) {
    Invalidate();
    return Fail(error, "P3 public board delta violated nondealer/dealer order");
  }
  if (events_.size() > static_cast<size_t>((state.round_index + 1) * 2)) {
    Invalidate();
    return Fail(error, "P3 public history is ahead of runtime round");
  }
  return true;
}

bool COFCP3PublicHistory::ValidateForDecision(
    const COFCState &state, string *error) const {
  if (!ValidateStableHand(state, error)) return false;
  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare) {
    return Fail(error, "P3 policy requires the actionable acting Hero");
  }
  const int actor_role = RoleForChair(state.acting_chair);
  if (actor_role < 0) return Fail(error, "P3 acting chair has no HU role");
  const size_t expected_events =
      static_cast<size_t>(state.round_index * 2 + actor_role);
  if (events_.size() != expected_events) {
    return Fail(error, "P3 public history is not the complete ordered prefix");
  }
  const int expected_incoming = state.round_index == 0 ? 5 : 3;
  const int expected_discards = max(0, state.round_index - 1);
  if (state.hero_incoming_count != expected_incoming
      || state.hero_discard_count != expected_discards) {
    return Fail(error, "P3 Hero private-card cardinality is inconsistent");
  }
  for (int role = 0; role < 2; ++role) {
    const int chair = role_chairs_[role];
    if (!SameBoard(observed_boards_[role], state.players[chair].board)) {
      return Fail(error, "P3 public history does not reconcile to current boards");
    }
    const int completed_before_round = state.round_index == 0
      ? 0 : 5 + 2 * (state.round_index - 1);
    const int current_round_placements = state.round_index == 0 ? 5 : 2;
    const int expected_board_count = completed_before_round
      + (role < actor_role ? current_round_placements : 0);
    if (BoardCount(state.players[chair].board) != expected_board_count) {
      return Fail(error, "P3 board cardinality disagrees with ordered progress");
    }
    if (chair == state.hero_chair) {
      if (state.players[chair].hidden_incoming_count != 0
          || state.players[chair].hidden_discard_count != 0) {
        return Fail(error, "P3 Hero private cards cannot be represented as hidden");
      }
      continue;
    }
    const bool acted_current_round = role < actor_role;
    const int opponent_packet = acted_current_round ? 0 : expected_incoming;
    const int opponent_discards = expected_discards
      + ((acted_current_round && state.round_index > 0) ? 1 : 0);
    if (state.players[chair].hidden_incoming_count != opponent_packet
        || state.players[chair].hidden_discard_count != opponent_discards) {
      return Fail(error, "P3 hidden opponent counts contradict ordered progress");
    }
  }
  return ValidateKnownUniqueness(state, error);
}

void COFCP3PolicyReceipt::Reset() {
  valid = false;
  physical_execution_authorized = false;
  button_identity = -1;
  actor_role = -1;
  authority = kAuthority;
  native_manifest_sha256 = kNativeManifestSha256;
  p2_manifest_sha256 = kP2ManifestSha256;
  p2_source_commit = kP2SourceCommit;
  route_sha256.clear();
  model_sha256.clear();
  canonical_information_key.clear();
  canonical_information_key_sha256.clear();
  canonical_action_key.clear();
  selected_probability = 0.0;
}

COFCP3Policy::COFCP3Policy() : loaded_(false) {}

const char *COFCP3Policy::Authority() { return kAuthority; }
const char *COFCP3Policy::NativeManifestSha256() {
  return kNativeManifestSha256;
}
const char *COFCP3Policy::P2ManifestSha256() { return kP2ManifestSha256; }
const char *COFCP3Policy::P2SourceCommit() { return kP2SourceCommit; }

bool COFCP3Policy::LoadDirectory(const string &directory, string *error) {
  return LoadFiles(
      JoinPath(directory, "playable_p3_native_manifest.json"),
      JoinPath(directory, "playable_p3_b0_weights.f64le"),
      JoinPath(directory, "playable_p3_b1_weights.f64le"),
      error);
}

bool COFCP3Policy::LoadFiles(
    const string &manifest_path,
    const string &b0_path,
    const string &b1_path,
    string *error) {
  loaded_ = false;
  if (error != NULL) error->clear();
  vector<unsigned char> manifest;
  if (!ReadFile(manifest_path, &manifest, error)) return false;
  if (manifest.empty()
      || Sha256Hex(&manifest[0], manifest.size()) != kNativeManifestFileSha256) {
    return Fail(error, "P3 native manifest file SHA-256 mismatch");
  }
  const string manifest_text(manifest.begin(), manifest.end());
  if (manifest_text.find(kNativeManifestSha256) == string::npos
      || manifest_text.find(kP2ManifestSha256) == string::npos
      || manifest_text.find(kAuthority) == string::npos) {
    return Fail(error, "P3 native manifest content identity mismatch");
  }
  RouteWeights loaded_routes[2];
  if (!LoadRouteFile(b0_path, kExpectedRoutes[0], &loaded_routes[0], error)
      || !LoadRouteFile(b1_path, kExpectedRoutes[1], &loaded_routes[1], error)) {
    return false;
  }
  routes_[0] = loaded_routes[0];
  routes_[1] = loaded_routes[1];
  loaded_ = true;
  return true;
}

bool COFCP3Policy::Choose(
    const COFCState &state,
    const COFCP3PublicHistory &history,
    COFCStrategyAction *action,
    COFCP3PolicyReceipt *receipt,
    string *error) const {
  if (action == NULL || receipt == NULL) {
    return Fail(error, "P3 policy requires action and receipt outputs");
  }
  if (error != NULL) error->clear();
  action->Reset();
  receipt->Reset();
  if (!loaded_) return Fail(error, "P3 native policy is not loaded");
  if (!history.ValidateForDecision(state, error)) return false;
  const int actor_role = history.RoleForChair(state.acting_chair);

  array<int, 4> suit_map = {{0, 1, 2, 3}};
  array<int, 4> best_map = suit_map;
  string best_key;
  bool have_key = false;
  do {
    const string candidate = InformationKey(state, history, actor_role, suit_map);
    if (!have_key || candidate < best_key
        || (candidate == best_key && suit_map < best_map)) {
      best_key = candidate;
      best_map = suit_map;
      have_key = true;
    }
  } while (next_permutation(suit_map.begin(), suit_map.end()));
  if (!have_key) return Fail(error, "P3 suit canonicalization produced no key");

  vector<NativeAction> actions;
  if (!EnumerateLegalActions(state, best_map, &actions, error)) return false;
  const vector<int> state_features =
      StateFeatures(state, history, actor_role, best_map);
  const int button = history.button_identity();
  if (button < 0 || button > 1 || routes_[button].button != button) {
    return Fail(error, "P3 policy has no route for persistent button identity");
  }
  vector<double> probabilities(actions.size(), 0.0);
  double score_total = 0.0;
  for (size_t i = 0; i < actions.size(); ++i) {
    const vector<int> action_features =
        ActionFeatures(state, actions[i], best_map);
    probabilities[i] = max(
        0.0, Predict(routes_[button].values, state_features, action_features));
    score_total += probabilities[i];
  }
  if (score_total <= 0.0) {
    const double uniform = 1.0 / static_cast<double>(actions.size());
    for (size_t i = 0; i < probabilities.size(); ++i) probabilities[i] = uniform;
  } else {
    for (size_t i = 0; i < probabilities.size(); ++i) {
      probabilities[i] /= score_total;
    }
  }
  double normalized_total = 0.0;
  for (size_t i = 0; i < probabilities.size(); ++i) {
    normalized_total += probabilities[i];
  }
  if (normalized_total <= 0.0) {
    return Fail(error, "P3 policy returned zero probability mass");
  }
  for (size_t i = 0; i < probabilities.size(); ++i) {
    probabilities[i] /= normalized_total;
  }

  size_t selected = 0;
  for (size_t i = 1; i < probabilities.size(); ++i) {
    if (probabilities[i] > probabilities[selected]
        || (probabilities[i] == probabilities[selected]
            && actions[i].canonical_key < actions[selected].canonical_key)) {
      selected = i;
    }
  }
  if (!ConvertAction(state, actions[selected], action, error)) return false;
  receipt->valid = true;
  receipt->physical_execution_authorized = false;
  receipt->button_identity = button;
  receipt->actor_role = actor_role;
  receipt->route_sha256 = routes_[button].route_sha256;
  receipt->model_sha256 = routes_[button].model_sha256;
  receipt->canonical_information_key = best_key;
  receipt->canonical_information_key_sha256 = Sha256Hex(best_key);
  receipt->canonical_action_key = actions[selected].canonical_key;
  receipt->selected_probability = probabilities[selected];
  return true;
}
