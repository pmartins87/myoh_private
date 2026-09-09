#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "deeppot_runtime_core.h"

namespace deeppot_runtime {

struct LiveScrapeSnapshot {
  int nchairs;
  int dealerchair;
  int userchair;
  std::uint32_t playersdealtbits;
  std::uint32_t playersplayingbits;
  std::uint32_t foldbits2;
  int nplayersdealt;

  LiveScrapeSnapshot();
};

struct PublicStateCandidate {
  int num_players;
  int actor_index;
  std::uint32_t prior_stay_mask;
  int scenario_dense_id;
  int global_scenario_code;
  std::vector<int> action_order;
  int cost;
  std::vector<std::string> reasons;

  PublicStateCandidate();
};

struct RecoveryConsensus {
  bool resolved;
  bool stay;
  double stay_weight;
  double fold_weight;
  int candidate_count;
  int min_cost;

  RecoveryConsensus();
};

std::vector<PublicStateCandidate> RecoverPublicStateCandidates(
    const LiveScrapeSnapshot& current,
    const std::vector<LiveScrapeSnapshot>& history,
    std::size_t max_candidates = 64);

RecoveryConsensus WeightedPolicyConsensus(
    const std::vector<PublicStateCandidate>& candidates,
    const std::function<bool(const PublicStateCandidate&)>& query_stay,
    int cost_window = 3,
    double clear_threshold = 0.65);

bool IsTopPairOrBetter(
    const std::array<Card, 3>& flop,
    const std::array<Card, 2>& hole);

}  // namespace deeppot_runtime
