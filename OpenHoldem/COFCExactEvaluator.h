//******************************************************************************
//
// OpenOFC v5.6.0 exact terminal rules oracle.
//
// This module owns rules, not strategy.  It evaluates a complete 3/5/5 board,
// resolves up to two physical Jokers, detects fouls, computes royalties and
// scores an exact pairwise showdown.  Search/training code can therefore share
// one audited terminal utility instead of copying heuristic hand values.
//
//******************************************************************************

#ifndef INC_COFCEXACTEVALUATOR_H
#define INC_COFCEXACTEVALUATOR_H

#include <string>
#include <vector>

#include "COFCState.h"

enum EOFCExactCategory {
  kOFCExactHighCard = 0,
  kOFCExactPair = 1,
  kOFCExactTwoPair = 2,
  kOFCExactTrips = 3,
  kOFCExactStraight = 4,
  kOFCExactFlush = 5,
  kOFCExactFullHouse = 6,
  kOFCExactQuads = 7,
  kOFCExactStraightFlush = 8
};

struct COFCExactHandRank {
  int category;
  int tie[5];
  int length;

  COFCExactHandRank();
};

struct COFCExactBoardResult {
  bool complete;
  bool foul;
  COFCExactHandRank rows[3];
  int royalties;
  int fantasy_cards;
  bool refantasy;

  COFCExactBoardResult();
};

struct COFCExactMatchResult {
  bool valid;
  int row_points;
  int scoop_bonus;
  int base_points;
  int hero_royalties;
  int opponent_royalties;
  int total_points;

  COFCExactMatchResult();
};

class COFCExactEvaluator {
 public:
  // Returns -1/0/+1 for left weaker/equal/stronger than right.
  static int CompareHands(
      const COFCExactHandRank &left,
      const COFCExactHandRank &right);

  // Exact row candidates are exposed for exhaustive placement solvers.  The
  // vector is strongest-first and contains every distinct rank reachable by
  // assigning the physical Jokers in that row.  This keeps Joker semantics in
  // one rules module instead of duplicating them in each solver.
  static bool EvaluateRowCandidates(
      const std::vector<int> &physical_cards,
      bool top,
      std::vector<COFCExactHandRank> *candidates,
      std::string *error);

  // Resolves three pre-evaluated rows into the strongest legal 3/5/5 board,
  // then applies royalties, Fantasy entry and re-Fantasy rules.
  static bool ResolveBoardCandidates(
      const std::vector<COFCExactHandRank> &top,
      const std::vector<COFCExactHandRank> &middle,
      const std::vector<COFCExactHandRank> &bottom,
      COFCExactBoardResult *result,
      std::string *error);

  static int RoyaltyForRow(
      const COFCExactHandRank &rank,
      EOFCRow row);

  // Requires exactly 3/5/5 known, unique physical cards.  A complete but
  // mis-set board is a successful evaluation with result->foul=true.
  static bool EvaluateBoard(
      const COFCPlayerBoard &board,
      COFCExactBoardResult *result,
      std::string *error);

  // Standard OFC pairwise scoring: one point per row, three extra for a scoop,
  // plus royalty differential.  A lone foul loses six base points and earns no
  // royalties; two fouls tie at zero.
  static bool ScoreMatch(
      const COFCExactBoardResult &hero,
      const COFCExactBoardResult &opponent,
      COFCExactMatchResult *result,
      std::string *error);
};

#endif  // INC_COFCEXACTEVALUATOR_H
