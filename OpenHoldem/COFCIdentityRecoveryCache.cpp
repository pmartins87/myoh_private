//******************************************************************************
// OpenOFC bounded identity-recovery cache.
//******************************************************************************

#ifndef DEEPOFC_IDENTITY_RECOVERY_STANDALONE
#include "StdAfx.h"
#endif
#include "COFCIdentityRecoveryCache.h"

#include <algorithm>
#include <cstddef>
#include <set>
#include <sstream>

#include "COFCState.h"

using namespace std;

COFCIdentityRecoveryCache g_openofc_identity_recovery_cache;

namespace {

bool IsPhysicalCard(int value) {
  return (value >= 0 && value <= 51)
    || value == kOFCCardJoker1 || value == kOFCCardJoker2;
}

bool Fail(string *error, const string &message) {
  if (error != NULL) *error = message;
  return false;
}

}  // namespace

COFCIdentityRecoveryCache::COFCIdentityRecoveryCache() {
  Reset();
}

void COFCIdentityRecoveryCache::Reset() {
  valid_ = false;
  fantasy_card_count_ = 0;
  recovered_card_ = kOFCCardNoCard;
  physical_cards_.clear();
}

bool COFCIdentityRecoveryCache::RememberFantasySet(
    int fantasy_card_count,
    const vector<int> &physical_cards,
    int recovered_card,
    string *error) {
  Reset();
  if (fantasy_card_count < 14 || fantasy_card_count > 17
      || static_cast<int>(physical_cards.size()) != fantasy_card_count
      || !IsPhysicalCard(recovered_card)) {
    return Fail(error, "invalid Fantasy recovery-set cardinality/identity");
  }
  set<int> unique;
  for (size_t i = 0; i < physical_cards.size(); ++i) {
    if (!IsPhysicalCard(physical_cards[i])
        || !unique.insert(physical_cards[i]).second) {
      return Fail(error, "Fantasy recovery-set is not physically unique");
    }
  }
  if (unique.find(recovered_card) == unique.end()) {
    return Fail(error, "recovered card is absent from proved Fantasy set");
  }
  physical_cards_ = physical_cards;
  sort(physical_cards_.begin(), physical_cards_.end());
  fantasy_card_count_ = fantasy_card_count;
  recovered_card_ = recovered_card;
  valid_ = true;
  if (error != NULL) error->clear();
  return true;
}

bool COFCIdentityRecoveryCache::CompleteOneUnknown(
    int fantasy_card_count,
    const vector<int> &observed,
    vector<int> *completed,
    int *recovered_card,
    string *error) const {
  if (completed != NULL) completed->clear();
  if (recovered_card != NULL) *recovered_card = kOFCCardNoCard;
  if (!valid_) return Fail(error, "Fantasy recovery cache is not armed");
  if (completed == NULL
      || fantasy_card_count != fantasy_card_count_
      || static_cast<int>(observed.size()) != fantasy_card_count_) {
    return Fail(error, "Fantasy recovery cache count mismatch");
  }

  int unknown_index = -1;
  set<int> known;
  for (size_t i = 0; i < observed.size(); ++i) {
    if (observed[i] == kOFCCardUnknown) {
      if (unknown_index >= 0)
        return Fail(error, "more than one unread Fantasy fan card");
      unknown_index = static_cast<int>(i);
      continue;
    }
    if (!IsPhysicalCard(observed[i]) || !known.insert(observed[i]).second)
      return Fail(error, "known Fantasy fan subset is invalid or duplicated");
  }
  if (unknown_index < 0)
    return Fail(error, "Fantasy fan has no single unknown to complete");

  set<int> expected(physical_cards_.begin(), physical_cards_.end());
  for (set<int>::const_iterator it = known.begin(); it != known.end(); ++it) {
    if (expected.erase(*it) != 1)
      return Fail(error, "current Fantasy fan is outside the proved recovery set");
  }
  if (expected.size() != 1)
    return Fail(error, "Fantasy set subtraction is not uniquely solvable");
  const int missing = *expected.begin();
  if (missing != recovered_card_)
    return Fail(error, "unique Fantasy complement disagrees with probed identity");

  *completed = observed;
  (*completed)[unknown_index] = missing;
  set<int> completed_unique(completed->begin(), completed->end());
  if (completed_unique.size() != physical_cards_.size()
      || !equal(completed_unique.begin(), completed_unique.end(),
                physical_cards_.begin())) {
    completed->clear();
    return Fail(error, "completed Fantasy fan failed exact-set equality");
  }
  if (recovered_card != NULL) *recovered_card = missing;
  if (error != NULL) error->clear();
  return true;
}

bool COFCIdentityRecoveryCache::SuggestProbedCardForSingleUnknownSubset(
    int fantasy_card_count,
    const vector<int> &observed_subset,
    int *recovered_card,
    string *error) const {
  if (recovered_card != NULL) *recovered_card = kOFCCardNoCard;
  if (!valid_ || fantasy_card_count != fantasy_card_count_)
    return Fail(error, "Fantasy recovery subset/cache count mismatch");
  int unknowns = 0;
  set<int> expected(physical_cards_.begin(), physical_cards_.end());
  set<int> known;
  for (size_t i = 0; i < observed_subset.size(); ++i) {
    const int value = observed_subset[i];
    if (value == kOFCCardUnknown) { ++unknowns; continue; }
    if (!IsPhysicalCard(value) || !known.insert(value).second
        || expected.find(value) == expected.end()) {
      return Fail(error, "Fantasy recovery subset is invalid/duplicated/off-set");
    }
  }
  if (unknowns != 1 || known.find(recovered_card_) != known.end())
    return Fail(error, "probed identity is not the unique eligible substitution");
  if (recovered_card != NULL) *recovered_card = recovered_card_;
  if (error != NULL) error->clear();
  return true;
}
