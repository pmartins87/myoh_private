#include "deeppot_live_recovery.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <sstream>
#include <tuple>

namespace deeppot_runtime {
namespace {

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
  return nchairs >= 32 ? std::numeric_limits<std::uint32_t>::max()
                       : ((static_cast<std::uint32_t>(1) << nchairs) - 1u);
}

int Hamming(std::uint32_t a, std::uint32_t b, int nchairs) {
  return BitCount((a ^ b) & SeatMask(nchairs));
}

std::string IntReason(const char* prefix, int value) {
  std::ostringstream out;
  out << prefix << value;
  return out.str();
}

struct CostReasons {
  int cost;
  std::vector<std::string> reasons;
  CostReasons() : cost(0), reasons() {}
};

CostReasons DealtCost(
    std::uint32_t mask,
    const LiveScrapeSnapshot& current,
    const std::vector<LiveScrapeSnapshot>& history) {
  CostReasons out;
  const int nchairs = current.nchairs;
  const std::uint32_t current_mask = current.playersdealtbits & SeatMask(nchairs);
  const int current_distance = Hamming(mask, current_mask, nchairs);
  out.cost = 4 * current_distance;
  if (current_distance != 0) {
    out.reasons.push_back(IntReason("dealt_current_hamming=", current_distance));
  }

  int best_history_distance = std::numeric_limits<int>::max();
  for (std::size_t i = 0; i < history.size(); ++i) {
    const LiveScrapeSnapshot& s = history[i];
    if (s.nchairs != nchairs || !ValidChair(s.userchair, nchairs)) continue;
    const std::uint32_t historical = s.playersdealtbits & SeatMask(nchairs);
    const int n = BitCount(historical);
    if (n < 2 || n > 8) continue;
    if ((historical & (static_cast<std::uint32_t>(1) << current.userchair)) == 0) continue;
    best_history_distance = std::min(best_history_distance, Hamming(mask, historical, nchairs));
  }
  if (best_history_distance != std::numeric_limits<int>::max()) {
    const int history_cost = 1 + 2 * best_history_distance;
    if (history_cost < out.cost) {
      out.cost = history_cost;
      out.reasons.clear();
      out.reasons.push_back(
          IntReason("dealt_from_same_hand_history_hamming=", best_history_distance));
    }
  }

  if (current.nplayersdealt >= 2 && current.nplayersdealt <= 8) {
    const int delta = std::abs(BitCount(mask) - current.nplayersdealt);
    if (delta != 0) {
      out.cost += 3 * delta;
      out.reasons.push_back(IntReason("nplayersdealt_delta=", delta));
    }
  }
  return out;
}

CostReasons DealerCost(
    int dealer,
    std::uint32_t dealt_mask,
    const LiveScrapeSnapshot& current,
    const std::vector<LiveScrapeSnapshot>& history) {
  CostReasons out;
  if ((dealt_mask & (static_cast<std::uint32_t>(1) << dealer)) == 0) {
    out.cost = std::numeric_limits<int>::max() / 4;
    return out;
  }
  if (dealer == current.dealerchair && ValidChair(current.dealerchair, current.nchairs)) {
    return out;
  }
  for (std::vector<LiveScrapeSnapshot>::const_reverse_iterator it = history.rbegin();
       it != history.rend(); ++it) {
    if (it->nchairs == current.nchairs && it->dealerchair == dealer &&
        ValidChair(it->dealerchair, current.nchairs)) {
      out.cost = 1;
      out.reasons.push_back("dealer_from_same_hand_history");
      return out;
    }
  }
  out.cost = 6;
  out.reasons.push_back("dealer_without_current_or_history_support");
  return out;
}

struct ActionAssignment {
  std::uint32_t stay_mask;
  int cost;
  std::vector<std::string> reasons;
  ActionAssignment() : stay_mask(0), cost(0), reasons() {}
};

std::vector<ActionAssignment> ActionAssignments(
    const std::vector<int>& order,
    int actor_index,
    const LiveScrapeSnapshot& snapshot) {
  std::vector<ActionAssignment> assignments(1);
  for (int i = 0; i < actor_index; ++i) {
    const int seat = order[static_cast<std::size_t>(i)];
    const std::uint32_t bit = static_cast<std::uint32_t>(1) << seat;
    const bool playing = (snapshot.playersplayingbits & bit) != 0;
    const bool folded = (snapshot.foldbits2 & bit) != 0;

    if (playing && !folded) {
      for (std::size_t j = 0; j < assignments.size(); ++j) {
        assignments[j].stay_mask |= static_cast<std::uint32_t>(1) << i;
      }
      continue;
    }
    if (folded && !playing) continue;

    if (!playing && !folded) {
      const std::string reason = IntReason("infer_prior_fold_seat=", seat);
      for (std::size_t j = 0; j < assignments.size(); ++j) {
        assignments[j].cost += 1;
        assignments[j].reasons.push_back(reason);
      }
      continue;
    }

    std::vector<ActionAssignment> branched;
    branched.reserve(assignments.size() * 2);
    for (std::size_t j = 0; j < assignments.size(); ++j) {
      ActionAssignment fold = assignments[j];
      fold.cost += 3;
      fold.reasons.push_back(
          IntReason("contradictory_playing_folded_seat=", seat) + ":FOLD");
      branched.push_back(fold);

      ActionAssignment stay = assignments[j];
      stay.stay_mask |= static_cast<std::uint32_t>(1) << i;
      stay.cost += 3;
      stay.reasons.push_back(
          IntReason("contradictory_playing_folded_seat=", seat) + ":STAY");
      branched.push_back(stay);
    }
    assignments.swap(branched);
  }
  return assignments;
}

bool CandidateLess(const PublicStateCandidate& a, const PublicStateCandidate& b) {
  if (a.cost != b.cost) return a.cost < b.cost;
  if (a.num_players != b.num_players) return a.num_players < b.num_players;
  if (a.actor_index != b.actor_index) return a.actor_index < b.actor_index;
  if (a.prior_stay_mask != b.prior_stay_mask) return a.prior_stay_mask < b.prior_stay_mask;
  return a.action_order < b.action_order;
}

bool CardsValidAndUnique(
    const std::array<Card, 3>& flop,
    const std::array<Card, 2>& hole) {
  bool seen[52] = {false};
  const Card cards[5] = {flop[0], flop[1], flop[2], hole[0], hole[1]};
  for (int i = 0; i < 5; ++i) {
    if (cards[i].rank < 2 || cards[i].rank > 14 || cards[i].suit < 0 || cards[i].suit > 3) {
      return false;
    }
    const int code = (cards[i].rank - 2) * 4 + cards[i].suit;
    if (seen[code]) return false;
    seen[code] = true;
  }
  return true;
}

}  // namespace

LiveScrapeSnapshot::LiveScrapeSnapshot()
    : nchairs(0), dealerchair(-1), userchair(-1), playersdealtbits(0),
      playersplayingbits(0), foldbits2(0), nplayersdealt(0) {}

PublicStateCandidate::PublicStateCandidate()
    : num_players(0), actor_index(-1), prior_stay_mask(0), scenario_dense_id(-1),
      global_scenario_code(0), action_order(), cost(0), reasons() {}

RecoveryConsensus::RecoveryConsensus()
    : resolved(false), stay(false), stay_weight(0.0), fold_weight(0.0),
      candidate_count(0), min_cost(-1) {}

std::vector<PublicStateCandidate> RecoverPublicStateCandidates(
    const LiveScrapeSnapshot& current,
    const std::vector<LiveScrapeSnapshot>& history,
    std::size_t max_candidates) {
  std::vector<PublicStateCandidate> empty;
  if (current.nchairs < 2 || current.nchairs > 10 ||
      !ValidChair(current.userchair, current.nchairs)) {
    return empty;
  }

  const std::uint32_t hero_bit = static_cast<std::uint32_t>(1) << current.userchair;
  const std::uint32_t playing = current.playersplayingbits & SeatMask(current.nchairs);
  const std::uint32_t folded = current.foldbits2 & SeatMask(current.nchairs);

  typedef std::tuple<int, int, std::uint32_t> CandidateKey;
  std::map<CandidateKey, PublicStateCandidate> best_by_key;
  const std::uint32_t max_mask = static_cast<std::uint32_t>(1) << current.nchairs;
  for (std::uint32_t dealt = 0; dealt < max_mask; ++dealt) {
    if ((dealt & hero_bit) == 0) continue;
    const int n = BitCount(dealt);
    if (n < 2 || n > 8) continue;

    const CostReasons dealt_score = DealtCost(dealt, current, history);
    int hero_cost = 0;
    std::vector<std::string> hero_reasons;
    if ((playing & hero_bit) == 0) {
      hero_cost += 4;
      hero_reasons.push_back("hero_missing_from_playing");
    }
    if ((folded & hero_bit) != 0) {
      hero_cost += 6;
      hero_reasons.push_back("hero_present_in_foldbits2");
    }

    for (int dealer = 0; dealer < current.nchairs; ++dealer) {
      const std::uint32_t dealer_bit = static_cast<std::uint32_t>(1) << dealer;
      if ((dealt & dealer_bit) == 0) continue;
      const CostReasons dealer_score = DealerCost(dealer, dealt, current, history);

      std::vector<int> order;
      order.reserve(static_cast<std::size_t>(n));
      for (int step = 1; step <= current.nchairs; ++step) {
        const int seat = (dealer + step) % current.nchairs;
        if ((dealt & (static_cast<std::uint32_t>(1) << seat)) != 0) order.push_back(seat);
      }
      if (static_cast<int>(order.size()) != n || order.back() != dealer) continue;
      const std::vector<int>::const_iterator actor_it =
          std::find(order.begin(), order.end(), current.userchair);
      if (actor_it == order.end()) continue;
      const int actor = static_cast<int>(actor_it - order.begin());

      const std::vector<ActionAssignment> assignments = ActionAssignments(order, actor, current);
      for (std::size_t i = 0; i < assignments.size(); ++i) {
        const ActionAssignment& assignment = assignments[i];
        const int dense = Strategy::ScenarioDenseId(n, actor, assignment.stay_mask);
        if (dense < 0) continue;
        const int global = Strategy::GlobalScenarioCode(n, dense);
        if (global <= 0) continue;

        PublicStateCandidate candidate;
        candidate.num_players = n;
        candidate.actor_index = actor;
        candidate.prior_stay_mask = assignment.stay_mask;
        candidate.scenario_dense_id = dense;
        candidate.global_scenario_code = global;
        candidate.action_order = order;
        candidate.cost = dealt_score.cost + dealer_score.cost + hero_cost + assignment.cost;
        candidate.reasons = dealt_score.reasons;
        candidate.reasons.insert(candidate.reasons.end(), dealer_score.reasons.begin(), dealer_score.reasons.end());
        candidate.reasons.insert(candidate.reasons.end(), hero_reasons.begin(), hero_reasons.end());
        candidate.reasons.insert(candidate.reasons.end(), assignment.reasons.begin(), assignment.reasons.end());

        const CandidateKey key(n, actor, assignment.stay_mask);
        std::map<CandidateKey, PublicStateCandidate>::iterator found = best_by_key.find(key);
        if (found == best_by_key.end() || CandidateLess(candidate, found->second)) {
          best_by_key[key] = candidate;
        }
      }
    }
  }

  std::vector<PublicStateCandidate> out;
  out.reserve(best_by_key.size());
  for (std::map<CandidateKey, PublicStateCandidate>::const_iterator it = best_by_key.begin();
       it != best_by_key.end(); ++it) {
    out.push_back(it->second);
  }
  std::sort(out.begin(), out.end(), CandidateLess);
  if (max_candidates == 0) max_candidates = 1;
  if (out.size() > max_candidates) out.resize(max_candidates);
  return out;
}

RecoveryConsensus WeightedPolicyConsensus(
    const std::vector<PublicStateCandidate>& candidates,
    const std::function<bool(const PublicStateCandidate&)>& query_stay,
    int cost_window,
    double clear_threshold) {
  RecoveryConsensus out;
  if (candidates.empty()) return out;
  const int min_cost = candidates.front().cost;
  out.min_cost = min_cost;
  for (std::size_t i = 0; i < candidates.size(); ++i) {
    const PublicStateCandidate& candidate = candidates[i];
    if (candidate.cost > min_cost + cost_window) continue;
    const double weight = std::pow(0.5, candidate.cost - min_cost);
    if (query_stay(candidate)) out.stay_weight += weight;
    else out.fold_weight += weight;
    ++out.candidate_count;
  }
  const double total = out.stay_weight + out.fold_weight;
  if (total <= 0.0) return out;
  out.stay_weight /= total;
  out.fold_weight /= total;
  if (out.stay_weight >= clear_threshold) {
    out.resolved = true;
    out.stay = true;
  } else if (out.fold_weight >= clear_threshold) {
    out.resolved = true;
    out.stay = false;
  }
  return out;
}

bool IsTopPairOrBetter(
    const std::array<Card, 3>& flop,
    const std::array<Card, 2>& hole) {
  if (!CardsValidAndUnique(flop, hole)) return false;

  int rank_counts[15] = {0};
  int suit_counts[4] = {0};
  const Card cards[5] = {flop[0], flop[1], flop[2], hole[0], hole[1]};
  for (int i = 0; i < 5; ++i) {
    ++rank_counts[cards[i].rank];
    ++suit_counts[cards[i].suit];
  }
  int paired_ranks = 0;
  for (int rank = 2; rank <= 14; ++rank) {
    if (rank_counts[rank] >= 3) return true;
    if (rank_counts[rank] >= 2) ++paired_ranks;
  }
  if (paired_ranks >= 2) return true;

  bool present[15] = {false};
  for (int rank = 2; rank <= 14; ++rank) present[rank] = rank_counts[rank] > 0;
  if (present[14]) present[1] = true;
  for (int start = 1; start <= 10; ++start) {
    bool straight = true;
    for (int rank = start; rank < start + 5; ++rank) straight = straight && present[rank];
    if (straight) return true;
  }
  for (int suit = 0; suit < 4; ++suit) {
    if (suit_counts[suit] == 5) return true;
  }

  const int top_board_rank = std::max(flop[0].rank, std::max(flop[1].rank, flop[2].rank));
  if (hole[0].rank == hole[1].rank && hole[0].rank > top_board_rank) return true;
  if (hole[0].rank == top_board_rank || hole[1].rank == top_board_rank) return true;
  return false;
}

}  // namespace deeppot_runtime
