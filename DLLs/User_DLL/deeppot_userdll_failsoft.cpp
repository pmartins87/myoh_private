//******************************************************************************
// DeepPot OpenHoldem user.dll adapter — fail-soft recovery v1
// Dedicated branch: deeppot_failsoft_recovery_v1
//******************************************************************************

#define USER_DLL

#include "user.h"
#include "OpenHoldemFunctions.h"
#include "deeppot_runtime_core.h"
#include "deeppot_live_recovery.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <map>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>
#include <windows.h>

namespace {

const int kEmergencyStayCode = 495;  // action transport only; not a trained scenario id
const std::size_t kMaxHandSnapshots = 32;

HMODULE g_module = NULL;
deeppot_runtime::Strategy g_strategy;

struct HandMemory {
  std::vector<deeppot_runtime::LiveScrapeSnapshot> snapshots;
  bool have_cards;
  std::array<deeppot_runtime::Card, 3> flop;
  std::array<deeppot_runtime::Card, 2> hole;

  HandMemory() : snapshots(), have_cards(false), flop(), hole() {}

  void Reset() {
    snapshots.clear();
    have_cards = false;
  }
};

HandMemory g_hand;

int IntSymbol(const char* name) {
  return static_cast<int>(GetSymbol(name));
}

int BitCount(unsigned int value) {
  int count = 0;
  while (value != 0) {
    value &= value - 1;
    ++count;
  }
  return count;
}

bool ValidChair(int chair, int nchairs) {
  return chair >= 0 && chair < nchairs;
}

std::string ModuleDirectory() {
  char path[MAX_PATH] = {0};
  const DWORD len = GetModuleFileNameA(g_module, path, MAX_PATH);
  if (len == 0 || len >= MAX_PATH) return std::string();
  std::string out(path, len);
  const std::string::size_type slash = out.find_last_of("\\/");
  if (slash == std::string::npos) return std::string();
  return out.substr(0, slash);
}

std::string RuntimeRoot() {
  const std::string base = ModuleDirectory();
  if (base.empty()) return std::string();
  return base + "\\DeepPotRuntime";
}

bool EnsureStrategyLoaded(std::string* error) {
  if (g_strategy.loaded()) return true;
  const std::string root = RuntimeRoot();
  if (root.empty()) {
    if (error) *error = "cannot resolve user.dll directory";
    return false;
  }
  std::string load_error;
  if (!g_strategy.Load(root, &load_error)) {
    if (error) *error = load_error;
    return false;
  }
  WriteLog("[DeepPot] runtime loaded from %s\n", const_cast<char*>(root.c_str()));
  if (error) error->clear();
  return true;
}

bool ReadCard(const char* rank_symbol, const char* suit_symbol, deeppot_runtime::Card* out) {
  const int rank = IntSymbol(rank_symbol);
  const int oh_suit = IntSymbol(suit_symbol);

  // OpenHoldem exposes PokerEval/StdDeck zero-based suit values:
  //   Hearts=0, Diamonds=1, Clubs=2, Spades=3.
  // DeepPot uses:
  //   Clubs=0, Diamonds=1, Hearts=2, Spades=3.
  if (rank < 2 || rank > 14 || oh_suit < 0 || oh_suit > 3) return false;

  static const int kOpenHoldemSuitToDeepPot[4] = {
      2,  // OH Hearts   -> DeepPot Hearts
      1,  // OH Diamonds -> DeepPot Diamonds
      0,  // OH Clubs    -> DeepPot Clubs
      3,  // OH Spades   -> DeepPot Spades
  };
  out->rank = rank;
  out->suit = kOpenHoldemSuitToDeepPot[oh_suit];
  return true;
}

bool CardsValidAndUnique(
    const std::array<deeppot_runtime::Card, 3>& flop,
    const std::array<deeppot_runtime::Card, 2>& hole) {
  bool seen[52] = {false};
  const deeppot_runtime::Card all[5] = {flop[0], flop[1], flop[2], hole[0], hole[1]};
  for (int i = 0; i < 5; ++i) {
    if (all[i].rank < 2 || all[i].rank > 14 || all[i].suit < 0 || all[i].suit > 3) {
      return false;
    }
    const int code = (all[i].rank - 2) * 4 + all[i].suit;
    if (seen[code]) return false;
    seen[code] = true;
  }
  return true;
}

bool ReadCurrentCards(
    std::array<deeppot_runtime::Card, 3>* flop,
    std::array<deeppot_runtime::Card, 2>* hole) {
  if (!ReadCard("$$pr0", "$$ps0", &(*hole)[0]) ||
      !ReadCard("$$pr1", "$$ps1", &(*hole)[1]) ||
      !ReadCard("$$cr0", "$$cs0", &(*flop)[0]) ||
      !ReadCard("$$cr1", "$$cs1", &(*flop)[1]) ||
      !ReadCard("$$cr2", "$$cs2", &(*flop)[2])) {
    return false;
  }
  return CardsValidAndUnique(*flop, *hole);
}

deeppot_runtime::LiveScrapeSnapshot ReadRawSnapshot() {
  deeppot_runtime::LiveScrapeSnapshot s;
  s.nchairs = IntSymbol("nchairs");
  s.dealerchair = IntSymbol("dealerchair");
  s.userchair = IntSymbol("userchair");
  s.playersdealtbits = static_cast<std::uint32_t>(IntSymbol("playersdealtbits"));
  s.playersplayingbits = static_cast<std::uint32_t>(IntSymbol("playersplayingbits"));
  s.foldbits2 = static_cast<std::uint32_t>(IntSymbol("foldbits2"));
  s.nplayersdealt = IntSymbol("nplayersdealt");
  return s;
}

bool SameSnapshot(
    const deeppot_runtime::LiveScrapeSnapshot& a,
    const deeppot_runtime::LiveScrapeSnapshot& b) {
  return a.nchairs == b.nchairs &&
         a.dealerchair == b.dealerchair &&
         a.userchair == b.userchair &&
         a.playersdealtbits == b.playersdealtbits &&
         a.playersplayingbits == b.playersplayingbits &&
         a.foldbits2 == b.foldbits2 &&
         a.nplayersdealt == b.nplayersdealt;
}

void RememberSnapshot(const deeppot_runtime::LiveScrapeSnapshot& s) {
  if (s.nchairs < 2 || s.nchairs > 10 || !ValidChair(s.userchair, s.nchairs)) return;
  if (!g_hand.snapshots.empty() && SameSnapshot(g_hand.snapshots.back(), s)) return;
  g_hand.snapshots.push_back(s);
  if (g_hand.snapshots.size() > kMaxHandSnapshots) {
    g_hand.snapshots.erase(g_hand.snapshots.begin());
  }
}

void CaptureLiveObservation() {
  const deeppot_runtime::LiveScrapeSnapshot raw = ReadRawSnapshot();
  RememberSnapshot(raw);

  // Only cache exact cards while exactly the flop is exposed. A later decision
  // may reuse these same-hand cards if a region flickers, but never substitutes
  // a different card state.
  if (IntSymbol("ncommoncardsknown") == 3) {
    std::array<deeppot_runtime::Card, 3> flop;
    std::array<deeppot_runtime::Card, 2> hole;
    if (ReadCurrentCards(&flop, &hole)) {
      g_hand.flop = flop;
      g_hand.hole = hole;
      g_hand.have_cards = true;
    }
  }
}

bool GetDecisionCards(
    std::array<deeppot_runtime::Card, 3>* flop,
    std::array<deeppot_runtime::Card, 2>* hole,
    bool* from_cache) {
  if (ReadCurrentCards(flop, hole)) {
    g_hand.flop = *flop;
    g_hand.hole = *hole;
    g_hand.have_cards = true;
    if (from_cache) *from_cache = false;
    return true;
  }
  if (g_hand.have_cards) {
    *flop = g_hand.flop;
    *hole = g_hand.hole;
    if (from_cache) *from_cache = true;
    return true;
  }
  return false;
}

bool NormalizeSnapshotForRecovery(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {
  if (current->nchairs < 2 || current->nchairs > 10) {
    bool restored = false;
    for (std::vector<deeppot_runtime::LiveScrapeSnapshot>::const_reverse_iterator it =
             g_hand.snapshots.rbegin();
         it != g_hand.snapshots.rend(); ++it) {
      if (it->nchairs >= 2 && it->nchairs <= 10) {
        current->nchairs = it->nchairs;
        restored = true;
        if (reasons) reasons->push_back("nchairs_from_same_hand_history");
        break;
      }
    }
    if (!restored) {
      current->nchairs = 8;
      if (reasons) reasons->push_back("nchairs_default_8");
    }
  }

  if (!ValidChair(current->userchair, current->nchairs)) {
    for (std::vector<deeppot_runtime::LiveScrapeSnapshot>::const_reverse_iterator it =
             g_hand.snapshots.rbegin();
         it != g_hand.snapshots.rend(); ++it) {
      if (it->nchairs == current->nchairs && ValidChair(it->userchair, current->nchairs)) {
        current->userchair = it->userchair;
        if (reasons) reasons->push_back("userchair_from_same_hand_history");
        break;
      }
    }
  }
  return ValidChair(current->userchair, current->nchairs);
}

bool BuildPrimaryPublicState(
    const deeppot_runtime::LiveScrapeSnapshot& s,
    int* num_players,
    int* actor_index,
    std::uint32_t* prior_stay_mask,
    std::uint32_t* inferred_fold_mask,
    std::string* error) {
  if (s.nchairs < 2 || s.nchairs > 10 ||
      !ValidChair(s.dealerchair, s.nchairs) ||
      !ValidChair(s.userchair, s.nchairs)) {
    if (error) *error = "invalid chair/dealer scrape";
    return false;
  }

  const unsigned int dealt = s.playersdealtbits;
  const unsigned int playing = s.playersplayingbits;
  const unsigned int folded = s.foldbits2;
  const int n = BitCount(dealt);
  if (n < 2 || n > 8 || n != s.nplayersdealt) {
    if (error) *error = "players-dealt count mismatch";
    return false;
  }
  if ((dealt & (1u << s.dealerchair)) == 0 || (dealt & (1u << s.userchair)) == 0) {
    if (error) *error = "dealer or hero absent from dealt mask";
    return false;
  }
  if ((playing & (1u << s.userchair)) == 0 || (folded & (1u << s.userchair)) != 0) {
    if (error) *error = "hero playing/fold state inconsistent";
    return false;
  }

  std::vector<int> order;
  order.reserve(n);
  for (int step = 1; step <= s.nchairs; ++step) {
    const int chair = (s.dealerchair + step) % s.nchairs;
    if ((dealt & (1u << chair)) != 0) order.push_back(chair);
  }
  if (static_cast<int>(order.size()) != n || order.back() != s.dealerchair) {
    if (error) *error = "cannot reconstruct fixed Pot Fold action order";
    return false;
  }

  int actor = -1;
  for (int i = 0; i < n; ++i) {
    if (order[i] == s.userchair) {
      actor = i;
      break;
    }
  }
  if (actor < 0) {
    if (error) *error = "hero absent from action order";
    return false;
  }

  std::uint32_t stay_mask = 0;
  std::uint32_t inferred = 0;
  for (int i = 0; i < actor; ++i) {
    const unsigned int bit = 1u << order[i];
    const bool is_folded = (folded & bit) != 0;
    const bool is_playing = (playing & bit) != 0;
    if (is_folded && is_playing) {
      if (error) *error = "prior actor simultaneously playing and folded";
      return false;
    }
    if (is_playing) {
      stay_mask |= (1u << i);
    } else if (!is_folded) {
      inferred |= (1u << i);
    }
  }

  if (deeppot_runtime::Strategy::ScenarioDenseId(n, actor, stay_mask) < 0) {
    if (error) *error = "primary public state is terminal/invalid";
    return false;
  }
  *num_players = n;
  *actor_index = actor;
  *prior_stay_mask = stay_mask;
  if (inferred_fold_mask) *inferred_fold_mask = inferred;
  if (error) error->clear();
  return true;
}

std::string JoinReasons(const std::vector<std::string>& reasons) {
  if (reasons.empty()) return "none";
  std::ostringstream out;
  for (std::size_t i = 0; i < reasons.size(); ++i) {
    if (i != 0) out << ",";
    out << reasons[i];
  }
  return out.str();
}

typedef std::tuple<int, int, std::uint32_t> PublicKey;

PublicKey CandidateKey(const deeppot_runtime::PublicStateCandidate& c) {
  return PublicKey(c.num_players, c.actor_index, c.prior_stay_mask);
}

int DeepPotAction() {
  if (GetSymbol("ismyturn") <= 0.0) return 0;

  std::string error;
  if (!EnsureStrategyLoaded(&error)) {
    WriteLog("[DeepPot] MISS UNRECOVERABLE runtime-load: %s\n", const_cast<char*>(error.c_str()));
    return 0;
  }

  CaptureLiveObservation();

  std::array<deeppot_runtime::Card, 3> flop;
  std::array<deeppot_runtime::Card, 2> hole;
  bool cards_from_cache = false;
  if (!GetDecisionCards(&flop, &hole, &cards_from_cache)) {
    WriteLog("[DeepPot] MISS UNRECOVERABLE reason=cards_unavailable_no_same_hand_cache\n");
    return 0;
  }

  deeppot_runtime::LiveScrapeSnapshot current = ReadRawSnapshot();
  std::vector<std::string> normalization_reasons;
  const bool normalized = NormalizeSnapshotForRecovery(&current, &normalization_reasons);

  if (normalized) {
    int n = 0;
    int actor = -1;
    std::uint32_t stay_mask = 0;
    std::uint32_t inferred_fold_mask = 0;
    std::string primary_error;
    if (BuildPrimaryPublicState(
            current, &n, &actor, &stay_mask, &inferred_fold_mask, &primary_error)) {
      deeppot_runtime::QueryResult result = g_strategy.Query(n, actor, stay_mask, flop, hole);
      if (result.ok) {
        const int encoded = result.EncodedAction();
        if (inferred_fold_mask == 0 && normalization_reasons.empty() && !cards_from_cache) {
          WriteLog(
              "[DeepPot] HIT EXACT N=%d actor=%d scenario=%d code=%d flop=%d hole=%d action=%s\n",
              n, actor, result.scenario_dense_id, encoded, result.flop_index,
              result.exact_hole_state_id, const_cast<char*>(result.stay ? "STAY" : "FOLD"));
        } else {
          std::vector<std::string> reasons = normalization_reasons;
          if (inferred_fold_mask != 0) {
            std::ostringstream inferred;
            inferred << "infer_missing_foldbits_actor_mask=0x" << std::hex << inferred_fold_mask;
            reasons.push_back(inferred.str());
          }
          if (cards_from_cache) reasons.push_back("cards_from_same_hand_cache");
          const std::string reason_text = JoinReasons(reasons);
          WriteLog(
              "[DeepPot] HIT RECOVERED cost=1 reason=%s N=%d actor=%d scenario=%d code=%d flop=%d hole=%d action=%s\n",
              const_cast<char*>(reason_text.c_str()), n, actor, result.scenario_dense_id, encoded,
              result.flop_index, result.exact_hole_state_id,
              const_cast<char*>(result.stay ? "STAY" : "FOLD"));
        }
        return encoded;
      }
      error = "primary lookup: " + result.error;
    } else {
      error = primary_error;
    }
  } else {
    error = "userchair unavailable with no same-hand recovery";
  }

  if (normalized) {
    std::vector<deeppot_runtime::PublicStateCandidate> candidates =
        deeppot_runtime::RecoverPublicStateCandidates(current, g_hand.snapshots, 64);
    std::vector<deeppot_runtime::PublicStateCandidate> valid_candidates;
    std::map<PublicKey, bool> stay_by_key;
    for (std::size_t i = 0; i < candidates.size(); ++i) {
      const deeppot_runtime::PublicStateCandidate& candidate = candidates[i];
      deeppot_runtime::QueryResult q = g_strategy.Query(
          candidate.num_players, candidate.actor_index, candidate.prior_stay_mask, flop, hole);
      if (!q.ok) continue;
      valid_candidates.push_back(candidate);
      stay_by_key[CandidateKey(candidate)] = q.stay;
    }

    if (!valid_candidates.empty()) {
      const deeppot_runtime::RecoveryConsensus consensus =
          deeppot_runtime::WeightedPolicyConsensus(
              valid_candidates,
              [&stay_by_key](const deeppot_runtime::PublicStateCandidate& candidate) {
                return stay_by_key.find(CandidateKey(candidate))->second;
              },
              1,
              0.65);

      bool chosen_stay = false;
      std::string resolution;
      if (consensus.resolved) {
        chosen_stay = consensus.stay;
        resolution = "consensus";
      } else {
        chosen_stay = stay_by_key.find(CandidateKey(valid_candidates.front()))->second;
        resolution = "nearest_tiebreak";
      }

      const deeppot_runtime::PublicStateCandidate* chosen = &valid_candidates.front();
      for (std::size_t i = 0; i < valid_candidates.size(); ++i) {
        if (stay_by_key.find(CandidateKey(valid_candidates[i]))->second == chosen_stay) {
          chosen = &valid_candidates[i];
          break;
        }
      }
      const int encoded = chosen_stay ? chosen->global_scenario_code : -chosen->global_scenario_code;
      const std::string reason_text = JoinReasons(chosen->reasons);
      WriteLog(
          "[DeepPot] HIT RECOVERED_%s candidates=%d min_cost=%d stay_weight=%.3f fold_weight=%.3f chosen_cost=%d reason=%s N=%d actor=%d scenario=%d code=%d action=%s primary_error=%s\n",
          const_cast<char*>(resolution.c_str()), consensus.candidate_count, consensus.min_cost,
          consensus.stay_weight, consensus.fold_weight, chosen->cost,
          const_cast<char*>(reason_text.c_str()), chosen->num_players, chosen->actor_index,
          chosen->scenario_dense_id, encoded, const_cast<char*>(chosen_stay ? "STAY" : "FOLD"),
          const_cast<char*>(error.c_str()));
      return encoded;
    }
  }

  if (deeppot_runtime::IsTopPairOrBetter(flop, hole)) {
    WriteLog(
        "[DeepPot] EMERGENCY TP_PLUS -> STAY code=%d reason=public_state_unresolved primary_error=%s\n",
        kEmergencyStayCode, const_cast<char*>(error.c_str()));
    return kEmergencyStayCode;
  }

  WriteLog(
      "[DeepPot] MISS UNRECOVERABLE reason=public_state_unresolved_non_TP_plus primary_error=%s\n",
      const_cast<char*>(error.c_str()));
  return 0;
}

}  // namespace

void DLLOnLoad() { g_hand.Reset(); }
void DLLOnUnLoad() {}
void __stdcall DLLUpdateOnNewFormula() {}
void __stdcall DLLUpdateOnConnection() { g_hand.Reset(); }
void __stdcall DLLUpdateOnHandreset() {
  g_hand.Reset();
  CaptureLiveObservation();
}
void __stdcall DLLUpdateOnNewRound() { CaptureLiveObservation(); }
void __stdcall DLLUpdateOnMyTurn() { CaptureLiveObservation(); }
void __stdcall DLLUpdateOnHeartbeat() { CaptureLiveObservation(); }

DLL_IMPLEMENTS double __stdcall ProcessQuery(const char* pquery) {
  if (pquery == NULL) return 0.0;
  if (std::strcmp(pquery, "dll$deeppot_action") == 0) {
    return static_cast<double>(DeepPotAction());
  }
  return 0.0;
}

BOOL APIENTRY DllMain(HANDLE hModule, DWORD reason, LPVOID) {
  switch (reason) {
    case DLL_PROCESS_ATTACH:
      g_module = static_cast<HMODULE>(hModule);
      InitializeOpenHoldemFunctionInterface();
      DLLOnLoad();
      break;
    case DLL_PROCESS_DETACH:
      DLLOnUnLoad();
      break;
    default:
      break;
  }
  return TRUE;
}
