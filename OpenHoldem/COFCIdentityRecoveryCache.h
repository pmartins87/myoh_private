//******************************************************************************
// OpenOFC bounded identity-recovery cache.
//******************************************************************************

#ifndef INC_COFCIDENTITYRECOVERYCACHE_H
#define INC_COFCIDENTITYRECOVERYCACHE_H

#include <string>
#include <vector>

// The cache is deliberately narrower than a general OCR override.  It is armed
// only after a physical card was read in a board slot and stores the complete
// Fantasy physical set proved by that fresh post-action observation.  It may
// repair exactly one unread fan slot, and only when set subtraction has one
// mathematical solution.  Duplicates and multi-card uncertainty remain closed.
class COFCIdentityRecoveryCache {
 public:
  COFCIdentityRecoveryCache();

  void Reset();
  bool RememberFantasySet(
      int fantasy_card_count,
      const std::vector<int> &physical_cards,
      int recovered_card,
      std::string *error);
  bool CompleteOneUnknown(
      int fantasy_card_count,
      const std::vector<int> &observed,
      std::vector<int> *completed,
      int *recovered_card,
      std::string *error) const;
  bool SuggestProbedCardForSingleUnknownSubset(
      int fantasy_card_count,
      const std::vector<int> &observed_subset,
      int *recovered_card,
      std::string *error) const;

  bool valid() const { return valid_; }
  int fantasy_card_count() const { return fantasy_card_count_; }
  int recovered_card() const { return recovered_card_; }

 private:
  bool valid_;
  int fantasy_card_count_;
  int recovered_card_;
  std::vector<int> physical_cards_;
};

extern COFCIdentityRecoveryCache g_openofc_identity_recovery_cache;

#endif  // INC_COFCIDENTITYRECOVERYCACHE_H
