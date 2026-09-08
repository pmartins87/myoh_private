//******************************************************************************
// DeepPot OpenHoldem user.dll adapter
// Dedicated branch: deeppot_runtime_v1
//******************************************************************************

#define USER_DLL

#include "user.h"
#include "OpenHoldemFunctions.h"
#include "deeppot_runtime_core.h"

#include <array>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <windows.h>

namespace {

HMODULE g_module = NULL;
deeppot_runtime::Strategy g_strategy;

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
  // OpenHoldem: clubs=1, diamonds=2, hearts=3, spades=4.
  // DeepPot:    clubs=0, diamonds=1, hearts=2, spades=3.
  if (rank < 2 || rank > 14 || oh_suit < 1 || oh_suit > 4) return false;
  out->rank = rank;
  out->suit = oh_suit - 1;
  return true;
}

bool BuildRuntimeQuery(
    int* num_players,
    int* actor_index,
    std::uint32_t* prior_stay_mask,
    std::array<deeppot_runtime::Card, 3>* flop,
    std::array<deeppot_runtime::Card, 2>* hole,
    std::string* error) {
  if (GetSymbol("ismyturn") <= 0.0) {
    if (error) *error = "not hero turn";
    return false;
  }
  if (IntSymbol("betround") != 2 || IntSymbol("ncommoncardsknown") != 3) {
    if (error) *error = "not a clean flop decision";
    return false;
  }

  const int nchairs = IntSymbol("nchairs");
  const int dealer = IntSymbol("dealerchair");
  const int user = IntSymbol("userchair");
  if (nchairs < 2 || nchairs > 10 || dealer < 0 || dealer >= nchairs || user < 0 || user >= nchairs) {
    if (error) *error = "invalid chair/dealer scrape";
    return false;
  }

  const unsigned int dealt = static_cast<unsigned int>(IntSymbol("playersdealtbits"));
  const unsigned int playing = static_cast<unsigned int>(IntSymbol("playersplayingbits"));
  const unsigned int folded = static_cast<unsigned int>(IntSymbol("foldbits2"));
  const int n = BitCount(dealt);
  if (n < 2 || n > 8 || n != IntSymbol("nplayersdealt")) {
    if (error) *error = "players-dealt count mismatch";
    return false;
  }
  if ((dealt & (1u << dealer)) == 0 || (dealt & (1u << user)) == 0) {
    if (error) *error = "dealer or hero absent from dealt mask";
    return false;
  }
  if ((playing & (1u << user)) == 0 || (folded & (1u << user)) != 0) {
    if (error) *error = "hero playing/fold state inconsistent";
    return false;
  }

  // Candidate live mapping to validate in shadow mode:
  // fixed Pot Fold postflop order = dealt seats clockwise after BTN, BTN last.
  std::vector<int> order;
  order.reserve(n);
  for (int step = 1; step <= nchairs; ++step) {
    const int chair = (dealer + step) % nchairs;
    if ((dealt & (1u << chair)) != 0) order.push_back(chair);
  }
  if (static_cast<int>(order.size()) != n || order.back() != dealer) {
    if (error) *error = "cannot reconstruct fixed Pot Fold action order";
    return false;
  }

  int actor = -1;
  for (int i = 0; i < n; ++i) {
    if (order[i] == user) {
      actor = i;
      break;
    }
  }
  if (actor < 0) {
    if (error) *error = "hero absent from action order";
    return false;
  }

  std::uint32_t stay_mask = 0;
  for (int i = 0; i < actor; ++i) {
    const unsigned int bit = 1u << order[i];
    const bool is_folded = (folded & bit) != 0;
    const bool is_playing = (playing & bit) != 0;
    if (is_folded == is_playing) {
      if (error) *error = "ambiguous prior FOLD/STAY scrape";
      return false;
    }
    if (is_playing) stay_mask |= (1u << i);
  }

  if (!ReadCard("$$pr0", "$$ps0", &(*hole)[0]) ||
      !ReadCard("$$pr1", "$$ps1", &(*hole)[1]) ||
      !ReadCard("$$cr0", "$$cs0", &(*flop)[0]) ||
      !ReadCard("$$cr1", "$$cs1", &(*flop)[1]) ||
      !ReadCard("$$cr2", "$$cs2", &(*flop)[2])) {
    if (error) *error = "hole/flop cards incomplete or invalid";
    return false;
  }

  *num_players = n;
  *actor_index = actor;
  *prior_stay_mask = stay_mask;
  if (error) error->clear();
  return true;
}

int DeepPotAction() {
  std::string error;
  if (!EnsureStrategyLoaded(&error)) {
    WriteLog("[DeepPot] MISS runtime-load: %s\n", const_cast<char*>(error.c_str()));
    return 0;
  }

  int n = 0;
  int actor = -1;
  std::uint32_t prior_stay_mask = 0;
  std::array<deeppot_runtime::Card, 3> flop;
  std::array<deeppot_runtime::Card, 2> hole;
  if (!BuildRuntimeQuery(&n, &actor, &prior_stay_mask, &flop, &hole, &error)) {
    WriteLog("[DeepPot] MISS state: %s\n", const_cast<char*>(error.c_str()));
    return 0;
  }

  deeppot_runtime::QueryResult result = g_strategy.Query(n, actor, prior_stay_mask, flop, hole);
  if (!result.ok) {
    WriteLog("[DeepPot] MISS lookup: %s\n", const_cast<char*>(result.error.c_str()));
    return 0;
  }
  const int encoded = result.EncodedAction();
  WriteLog(
      "[DeepPot] HIT N=%d actor=%d scenario=%d code=%d flop=%d hole=%d action=%s\n",
      n, actor, result.scenario_dense_id, encoded, result.flop_index,
      result.exact_hole_state_id, const_cast<char*>(result.stay ? "STAY" : "FOLD"));
  return encoded;
}

}  // namespace

void DLLOnLoad() {}
void DLLOnUnLoad() {}
void __stdcall DLLUpdateOnNewFormula() {}
void __stdcall DLLUpdateOnConnection() {}
void __stdcall DLLUpdateOnHandreset() {}
void __stdcall DLLUpdateOnNewRound() {}
void __stdcall DLLUpdateOnMyTurn() {}
void __stdcall DLLUpdateOnHeartbeat() {}

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
