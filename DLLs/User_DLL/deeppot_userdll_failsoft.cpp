//******************************************************************************
// DeepPot OpenHoldem user.dll adapter — fail-soft recovery v3
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

const int kEmergencyStayCode = 495;
const std::size_t kMaxHandSnapshots = 32;
const int kHandresetGraceObservations = 4;
const char* kAdapterVersion = "failsoft-v4-anchor-evidence-20260909";

HMODULE g_module = NULL;
deeppot_runtime::Strategy g_strategy;

struct HandMemory {
  std::vector<deeppot_runtime::LiveScrapeSnapshot> snapshots;
  bool have_cards;
  std::array<deeppot_runtime::Card, 3> flop;
  std::array<deeppot_runtime::Card, 2> hole;
  bool have_anchor;
  deeppot_runtime::LiveScrapeSnapshot anchor;
  int pending_handreset_observations;
  int last_betround;
  int last_common_cards;

  HandMemory()
      : snapshots(),
        have_cards(false),
        flop(),
        hole(),
        have_anchor(false),
        anchor(),
        pending_handreset_observations(0),
        last_betround(-1),
        last_common_cards(-1) {}

  void ClearHandData() {
    snapshots.clear();
    have_cards = false;
    have_anchor = false;
    pending_handreset_observations = 0;
  }

  void FullReset() {
    ClearHandData();
    last_betround = -1;
    last_common_cards = -1;
  }
};

HandMemory g_hand;

int IntSymbol(const char* name) {
  return static_cast<int>(GetSymbol(name));
}

int BitCount(std::uint32_t value) {
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

std::uint32_t SeatMask(int nchairs) {
  if (nchairs <= 0) return 0;
  if (nchairs >= 32) return 0xFFFFFFFFu;
  return (static_cast<std::uint32_t>(1) << nchairs) - 1u;
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
  WriteLog(
      "[DeepPot] runtime loaded adapter=%s root=%s\n",
      const_cast<char*>(kAdapterVersion),
      const_cast<char*>(root.c_str()));
  if (error) error->clear();
  return true;
}

bool ReadCard(const char* rank_symbol, const char* suit_symbol, deeppot_runtime::Card* out) {
  const int rank = IntSymbol(rank_symbol);
  const int openholdem_suit = IntSymbol(suit_symbol);
  if (rank < 2 || rank > 14 || openholdem_suit < 0 || openholdem_suit > 3) return false;
  static const int kOpenHoldemSuitToDeepPot[4] = {2, 1, 0, 3};
  out->rank = rank;
  out->suit = kOpenHoldemSuitToDeepPot[openholdem_suit];
  return true;
}

int CardCode(const deeppot_runtime::Card& card) {
  return (card.rank - 2) * 4 + card.suit;
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
    const int code = CardCode(all[i]);
    if (seen[code]) return false;
    seen[code] = true;
  }
  return true;
}

bool SameCardIdentity(
    const std::array<deeppot_runtime::Card, 3>& flop_a,
    const std::array<deeppot_runtime::Card, 2>& hole_a,
    const std::array<deeppot_runtime::Card, 3>& flop_b,
    const std::array<deeppot_runtime::Card, 2>& hole_b) {
  std::array<int, 3> fa = {{CardCode(flop_a[0]), CardCode(flop_a[1]), CardCode(flop_a[2])}};
  std::array<int, 3> fb = {{CardCode(flop_b[0]), CardCode(flop_b[1]), CardCode(flop_b[2])}};
  std::array<int, 2> ha = {{CardCode(hole_a[0]), CardCode(hole_a[1])}};
  std::array<int, 2> hb = {{CardCode(hole_b[0]), CardCode(hole_b[1])}};
  std::sort(fa.begin(), fa.end());
  std::sort(fb.begin(), fb.end());
  std::sort(ha.begin(), ha.end());
  std::sort(hb.begin(), hb.end());
  return fa == fb && ha == hb;
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

bool CoherentAnchorSnapshot(const deeppot_runtime::LiveScrapeSnapshot& s) {
  if (s.nchairs < 2 || s.nchairs > 10 ||
      !ValidChair(s.userchair, s.nchairs) ||
      !ValidChair(s.dealerchair, s.nchairs)) {
    return false;
  }
  const std::uint32_t dealt = s.playersdealtbits & SeatMask(s.nchairs);
  const int n = BitCount(dealt);
  if (n < 2 || n > 8 || n != s.nplayersdealt) return false;
  if ((dealt & (static_cast<std::uint32_t>(1) << s.userchair)) == 0) return false;
  if ((dealt & (static_cast<std::uint32_t>(1) << s.dealerchair)) == 0) return false;
  return true;
}

void ResetForNewHand(const char* reason) {
  if (g_hand.have_cards || g_hand.have_anchor || !g_hand.snapshots.empty()) {
    WriteLog(
        "[DeepPot] HAND_BOUNDARY reason=%s previous_snapshots=%d\n",
        const_cast<char*>(reason),
        static_cast<int>(g_hand.snapshots.size()));
  }
  g_hand.ClearHandData();
}

void SetHandAnchorIfMissing(const deeppot_runtime::LiveScrapeSnapshot& raw) {
  if (g_hand.have_anchor || !CoherentAnchorSnapshot(raw)) return;
  g_hand.anchor = raw;
  g_hand.anchor.playersdealtbits &= SeatMask(raw.nchairs);
  g_hand.anchor.nplayersdealt = BitCount(g_hand.anchor.playersdealtbits);
  g_hand.have_anchor = true;
  WriteLog(
      "[DeepPot] HAND_ANCHOR nchairs=%d dealer=%d hero=%d dealt=0x%X N=%d\n",
      g_hand.anchor.nchairs,
      g_hand.anchor.dealerchair,
      g_hand.anchor.userchair,
      g_hand.anchor.playersdealtbits,
      g_hand.anchor.nplayersdealt);
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

void ApplyHandAnchor(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {
  if (!g_hand.have_anchor) return;

  const deeppot_runtime::LiveScrapeSnapshot& a = g_hand.anchor;
  const std::uint32_t anchored_dealt = a.playersdealtbits & SeatMask(a.nchairs);

  // v4 live-safety rule: if current playing/fold evidence contains a seat that
  // the old frozen anchor says was never dealt, the anchor is incomplete/stale
  // and must not overwrite the live public geometry.
  const std::uint32_t live_action_evidence =
      (current->playersplayingbits | current->foldbits2) & SeatMask(a.nchairs);
  if ((live_action_evidence & ~anchored_dealt) != 0) {
    if (reasons) reasons->push_back("anchor_rejected_by_live_action_evidence");
    return;
  }

  if (current->nchairs != a.nchairs) {
    current->nchairs = a.nchairs;
    if (reasons) reasons->push_back("nchairs_from_hand_anchor");
  }
  if (current->userchair != a.userchair) {
    current->userchair = a.userchair;
    if (reasons) reasons->push_back("userchair_from_hand_anchor");
  }
  if (current->dealerchair != a.dealerchair) {
    current->dealerchair = a.dealerchair;
    if (reasons) reasons->push_back("dealer_from_hand_anchor");
  }
  if ((current->playersdealtbits & SeatMask(a.nchairs)) != anchored_dealt) {
    current->playersdealtbits = anchored_dealt;
    if (reasons) reasons->push_back("dealt_from_hand_anchor");
  } else {
    current->playersdealtbits = anchored_dealt;
  }
  const int anchored_n = BitCount(anchored_dealt);
  if (current->nplayersdealt != anchored_n) {
    current->nplayersdealt = anchored_n;
    if (reasons) reasons->push_back("nplayersdealt_from_hand_anchor");
  }
}

void ObserveLifecycle() {
  const int betround = IntSymbol("betround");
  const int common = IntSymbol("ncommoncardsknown");
  const bool backwards_to_new_hand =
      (g_hand.last_common_cards >= 3 && common >= 0 && common < 3) ||
      (g_hand.last_betround >= 2 && betround > 0 && betround <= 1);
  const bool reset_callback_confirmed =
      g_hand.pending_handreset_observations > 0 &&
      ((common >= 0 && common < 3) || (betround > 0 && betround <= 1));
  if (backwards_to_new_hand || reset_callback_confirmed) {
    ResetForNewHand(reset_callback_confirmed ? "handreset_confirmed_nonflop" : "street_transition_to_new_hand");
  }
  g_hand.last_betround = betround;
  g_hand.last_common_cards = common;
}

void CaptureLiveObservation() {
  ObserveLifecycle();
  deeppot_runtime::LiveScrapeSnapshot raw = ReadRawSnapshot();
  if (IntSymbol("ncommoncardsknown") == 3) {
    std::array<deeppot_runtime::Card, 3> flop;
    std::array<deeppot_runtime::Card, 2> hole;
    if (ReadCurrentCards(&flop, &hole)) {
      if (g_hand.have_cards && !SameCardIdentity(g_hand.flop, g_hand.hole, flop, hole)) {
        if (g_hand.pending_handreset_observations > 0 || CoherentAnchorSnapshot(raw)) {
          ResetForNewHand(
              g_hand.pending_handreset_observations > 0
                  ? "handreset_confirmed_card_identity_changed"
                  : "card_identity_changed_with_coherent_public_state");
        }
      }
      if (!g_hand.have_cards || SameCardIdentity(g_hand.flop, g_hand.hole, flop, hole)) {
        g_hand.flop = flop;
        g_hand.hole = hole;
        g_hand.have_cards = true;
      }
    }
  }
  SetHandAnchorIfMissing(raw);
  deeppot_runtime::LiveScrapeSnapshot historical = raw;
  ApplyHandAnchor(&historical, NULL);
  RememberSnapshot(historical);
  if (g_hand.pending_handreset_observations > 0) {
    --g_hand.pending_handreset_observations;
  }
}

bool GetDecisionCards(
    std::array<deeppot_runtime::Card, 3>* flop,
    std::array<deeppot_runtime::Card, 2>* hole,
    bool* from_cache) {
  std::array<deeppot_runtime::Card, 3> live_flop;
  std::array<deeppot_runtime::Card, 2> live_hole;
  if (ReadCurrentCards(&live_flop, &live_hole)) {
    if (!g_hand.have_cards || SameCardIdentity(g_hand.flop, g_hand.hole, live_flop, live_hole)) {
      g_hand.flop = live_flop;
      g_hand.hole = live_hole;
      g_hand.have_cards = true;
      *flop = live_flop;
      *hole = live_hole;
      if (from_cache) *from_cache = false;
      return true;
    }
    const deeppot_runtime::LiveScrapeSnapshot raw = ReadRawSnapshot();
    if (CoherentAnchorSnapshot(raw)) {
      ResetForNewHand("decision_card_identity_changed");
      g_hand.flop = live_flop;
      g_hand.hole = live_hole;
      g_hand.have_cards = true;
      SetHandAnchorIfMissing(raw);
      deeppot_runtime::LiveScrapeSnapshot historical = raw;
      ApplyHandAnchor(&historical, NULL);
      RememberSnapshot(historical);
      *flop = live_flop;
      *hole = live_hole;
      if (from_cache) *from_cache = false;
      return true;
    }
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
  ApplyHandAnchor(current, reasons);
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
  if (!ValidChair(current->dealerchair, current->nchairs)) {
    for (std::vector<deeppot_runtime::LiveScrapeSnapshot>::const_reverse_iterator it =
             g_hand.snapshots.rbegin();
         it != g_hand.snapshots.rend(); ++it) {
      if (it->nchairs == current->nchairs && ValidChair(it->dealerchair, current->nchairs)) {
        current->dealerchair = it->dealerchair;
        if (reasons) reasons->push_back("dealer_from_same_hand_history");
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
  const std::uint32_t seat_mask = SeatMask(s.nchairs);
  const std::uint32_t dealt = s.playersdealtbits & seat_mask;
  const std::uint32_t playing = s.playersplayingbits & seat_mask;
  const std::uint32_t folded = s.foldbits2 & seat_mask;
  const int n = BitCount(dealt);
  if (n < 2 || n > 8 || n != s.nplayersdealt) {
    if (error) *error = "players-dealt count mismatch";
    return false;
  }
  if ((dealt & (static_cast<std::uint32_t>(1) << s.dealerchair)) == 0 ||
      (dealt & (static_cast<std::uint32_t>(1) << s.userchair)) == 0) {
    if (error) *error = "dealer or hero absent from dealt mask";
    return false;
  }
  if ((playing & (static_cast<std::uint32_t>(1) << s.userchair)) == 0 ||
      (folded & (static_cast<std::uint32_t>(1) << s.userchair)) != 0) {
    if (error) *error = "hero playing/fold state inconsistent";
    return false;
  }
  std::vector<int> order;
  order.reserve(static_cast<std::size_t>(n));
  for (int step = 1; step <= s.nchairs; ++step) {
    const int chair = (s.dealerchair + step) % s.nchairs;
    if ((dealt & (static_cast<std::uint32_t>(1) << chair)) != 0) order.push_back(chair);
  }
  if (static_cast<int>(order.size()) != n || order.back() != s.dealerchair) {
    if (error) *error = "cannot reconstruct fixed Pot Fold action order";
    return false;
  }
  int actor = -1;
  for (int i = 0; i < n; ++i) {
    if (order[static_cast<std::size_t>(i)] == s.userchair) {
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
    const std::uint32_t bit = static_cast<std::uint32_t>(1) << order[static_cast<std::size_t>(i)];
    const bool is_folded = (folded & bit) != 0;
    const bool is_playing = (playing & bit) != 0;
    if (is_folded && is_playing) {
      if (error) *error = "prior actor simultaneously playing and folded";
      return false;
    }
    if (is_playing) {
      stay_mask |= static_cast<std::uint32_t>(1) << i;
    } else if (!is_folded) {
      inferred |= static_cast<std::uint32_t>(1) << i;
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
        if (inferred_fold_mask != 0) {
          std::ostringstream deferred;
          deferred << "primary_missing_action_evidence_actor_mask=0x" << std::hex
                   << inferred_fold_mask << " deferred_to_policy_recovery";
          error = deferred.str();
        } else {
          if (normalization_reasons.empty() && !cards_from_cache) {
            WriteLog(
                "[DeepPot] HIT EXACT N=%d actor=%d scenario=%d code=%d flop=%d hole=%d action=%s\n",
                n,
                actor,
                result.scenario_dense_id,
                encoded,
                result.flop_index,
                result.exact_hole_state_id,
                const_cast<char*>(result.stay ? "STAY" : "FOLD"));
          } else {
            std::vector<std::string> reasons = normalization_reasons;
            if (cards_from_cache) reasons.push_back("cards_from_same_hand_cache");
            const std::string reason_text = JoinReasons(reasons);
            WriteLog(
                "[DeepPot] HIT RECOVERED_PRIMARY reason=%s N=%d actor=%d scenario=%d code=%d flop=%d hole=%d action=%s\n",
                const_cast<char*>(reason_text.c_str()),
                n,
                actor,
                result.scenario_dense_id,
                encoded,
                result.flop_index,
                result.exact_hole_state_id,
                const_cast<char*>(result.stay ? "STAY" : "FOLD"));
          }
          return encoded;
        }
      } else {
        error = "primary lookup: " + result.error;
      }
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
          candidate.num_players,
          candidate.actor_index,
          candidate.prior_stay_mask,
          flop,
          hole);
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
      const char* resolution = NULL;
      if (consensus.resolved) {
        chosen_stay = consensus.stay;
        resolution = "CONSENSUS";
      } else {
        chosen_stay = stay_by_key.find(CandidateKey(valid_candidates.front()))->second;
        resolution = "NEAREST_TIEBREAK";
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
          const_cast<char*>(resolution),
          consensus.candidate_count,
          consensus.min_cost,
          consensus.stay_weight,
          consensus.fold_weight,
          chosen->cost,
          const_cast<char*>(reason_text.c_str()),
          chosen->num_players,
          chosen->actor_index,
          chosen->scenario_dense_id,
          encoded,
          const_cast<char*>(chosen_stay ? "STAY" : "FOLD"),
          const_cast<char*>(error.c_str()));
      return encoded;
    }
  }

  if (deeppot_runtime::IsTopPairOrBetter(flop, hole)) {
    WriteLog(
        "[DeepPot] EMERGENCY TP_PLUS -> STAY code=%d reason=public_state_unresolved primary_error=%s\n",
        kEmergencyStayCode,
        const_cast<char*>(error.c_str()));
    return kEmergencyStayCode;
  }
  WriteLog(
      "[DeepPot] MISS UNRECOVERABLE reason=public_state_unresolved_non_TP_plus primary_error=%s\n",
      const_cast<char*>(error.c_str()));
  return 0;
}

}  // namespace

void DLLOnLoad() {
  g_hand.FullReset();
  WriteLog("[DeepPot] adapter loaded version=%s\n", const_cast<char*>(kAdapterVersion));
}
void DLLOnUnLoad() {}
void __stdcall DLLUpdateOnNewFormula() {}
void __stdcall DLLUpdateOnConnection() { g_hand.FullReset(); }
void __stdcall DLLUpdateOnHandreset() {
  g_hand.pending_handreset_observations = kHandresetGraceObservations;
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
