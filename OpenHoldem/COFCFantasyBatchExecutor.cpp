//******************************************************************************
// OpenOFC Fantasy row-batch click executor.
//******************************************************************************

#include "StdAfx.h"
#include "COFCFantasyBatchExecutor.h"

#include <algorithm>
#include <sstream>
#include <vector>

#include "CCasinoInterface.h"
#include "..\CTablemap\CTablemap.h"

using namespace std;

namespace {

const int kFantasyVerificationWaitCycles = 10;
const int kFantasyMaximumRebuildRetries = 1;

const char *RowName(EOFCRow row) {
  switch (row) {
    case kOFCRowTop: return "top";
    case kOFCRowMiddle: return "middle";
    case kOFCRowBottom: return "bottom";
    default: return "invalid";
  }
}

int RowCapacity(EOFCRow row) {
  switch (row) {
    case kOFCRowTop: return kOFCTopCards;
    case kOFCRowMiddle: return kOFCMiddleCards;
    case kOFCRowBottom: return kOFCBottomCards;
    default: return 0;
  }
}

bool IsCanonicalJoker(int value) {
  return value == kOFCCardJoker1 || value == kOFCCardJoker2;
}

long RectCenterX(const RECT &rect) {
  return rect.left + (rect.right - rect.left) / 2;
}

struct RectRightToLeft {
  bool operator()(const RECT &a, const RECT &b) const {
    return RectCenterX(a) > RectCenterX(b);
  }
};

vector<int> CurrentRowCards(const COFCState &state, EOFCRow row) {
  vector<int> values;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active || state.pending[i].row != row) continue;
    const int incoming_index = state.pending[i].incoming_index;
    if (incoming_index < 0 || incoming_index >= state.hero_incoming_count) continue;
    const int value = state.hero_incoming[incoming_index].value;
    if (value >= 0 && value <= kOFCCardJoker2) values.push_back(value);
  }
  sort(values.begin(), values.end());
  return values;
}

vector<int> TargetRowCards(const COFCTurnPlan &plan, EOFCRow row) {
  vector<int> values;
  for (int i = 0; i < plan.target_count; ++i) {
    if (plan.target[i].row == row) values.push_back(plan.target[i].card_value);
  }
  sort(values.begin(), values.end());
  return values;
}

string CardList(const vector<int> &cards) {
  ostringstream out;
  out << "[";
  for (size_t i = 0; i < cards.size(); ++i) {
    if (i != 0) out << ",";
    out << cards[i];
  }
  out << "]";
  return out.str();
}

}  // namespace

COFCFantasyBatchExecutor::COFCFantasyBatchExecutor() {
  Reset();
}

void COFCFantasyBatchExecutor::Reset() {
  phase_ = kIdle;
  plan_.Reset();
  waiting_row_ = kOFCRowUndefined;
  wait_cycles_ = 0;
  retry_count_[0] = retry_count_[1] = retry_count_[2] = 0;
  clear_consumes_retry_ = false;
}

bool COFCFantasyBatchExecutor::Fail(
    string *error, const string &message) {
  phase_ = kBlocked;
  if (error != NULL) *error = message;
  write_log(k_always_log_errors,
    "[OpenOFC FANTASY V5] BLOCKED reason=\"%s\"\n", message.c_str());
  return false;
}

bool COFCFantasyBatchExecutor::ResolveRowActionRect(
    EOFCRow row, RECT *out, string *error) const {
  if (out == NULL || p_tablemap == NULL) {
    if (error != NULL) *error = "Fantasy row-action rectangle output/tablemap is null";
    return false;
  }
  CString name;
  name.Format("ofc_fantasy_row_action_%s", RowName(row));
  RMapCI it = p_tablemap->r$()->find(name);
  if (it == p_tablemap->r$()->end()) {
    if (error != NULL) {
      *error = string("missing measured Fantasy row-action region: ")
        + name.GetString();
    }
    return false;
  }
  out->left = static_cast<LONG>(it->second.left);
  out->top = static_cast<LONG>(it->second.top);
  out->right = static_cast<LONG>(it->second.right);
  out->bottom = static_cast<LONG>(it->second.bottom);
  if (out->right <= out->left || out->bottom <= out->top) {
    if (error != NULL) *error = "Fantasy row-action rectangle is empty";
    return false;
  }
  return true;
}

bool COFCFantasyBatchExecutor::ResolveLooseSource(
    const COFCVisualObservation &observation,
    int card_value,
    RECT *out,
    string *error) const {
  if (out == NULL) {
    if (error != NULL) *error = "Fantasy loose-source output is null";
    return false;
  }
  SetRectEmpty(out);
  int exact = -1;
  int generic_joker = -1;
  int generic_joker_count = 0;
  for (int i = 0; i < observation.hero_loose_count; ++i) {
    const int observed = observation.hero_loose_cards[i].value;
    if (observed == card_value) {
      if (exact >= 0) {
        if (error != NULL) *error = "duplicate exact loose-card source in Fantasy";
        return false;
      }
      exact = i;
    }
#ifdef kOFCCardJokerGeneric
    if (IsCanonicalJoker(card_value) && observed == kOFCCardJokerGeneric) {
      generic_joker = i;
      ++generic_joker_count;
    }
#endif
  }
  int index = exact;
  if (index < 0 && IsCanonicalJoker(card_value)) {
#ifdef kOFCCardJokerGeneric
    if (generic_joker_count == 1) index = generic_joker;
#endif
  }
  if (index < 0 || index >= observation.hero_loose_count) {
    if (error != NULL) {
      ostringstream oss;
      oss << "Fantasy target card has no unique current loose source value="
          << card_value;
      *error = oss.str();
    }
    return false;
  }
  const COFCVisualCardSource &source = observation.hero_loose_sources[index];
  if (!source.valid || source.rect.right <= source.rect.left
      || source.rect.bottom <= source.rect.top) {
    if (error != NULL) *error = "Fantasy loose source has no click-safe fresh rectangle";
    return false;
  }
  *out = source.rect;
  return true;
}

bool COFCFantasyBatchExecutor::RowMatchesTarget(
    const COFCState &state, EOFCRow row) const {
  return CurrentRowCards(state, row) == TargetRowCards(plan_, row);
}

bool COFCFantasyBatchExecutor::RowEmpty(
    const COFCState &state, EOFCRow row) const {
  return CurrentRowCards(state, row).empty();
}

bool COFCFantasyBatchExecutor::SendClearRow(
    EOFCRow row, bool consumes_retry, string *error) {
  if (p_casino_interface == NULL) {
    return Fail(error, "casino interface unavailable for Fantasy row clear");
  }
  RECT action;
  string rect_error;
  if (!ResolveRowActionRect(row, &action, &rect_error)) {
    return Fail(error, rect_error);
  }
  write_log(true,
    "[OpenOFC FANTASY V5] action=CLEAR_ROW row=%s retry_after_clear=%d\n",
    RowName(row), consumes_retry ? 1 : 0);
  if (!p_casino_interface->ClickRectSafely(action)) {
    return Fail(error, "safe Fantasy row-clear click was refused");
  }
  waiting_row_ = row;
  phase_ = kAwaitRowClear;
  wait_cycles_ = 0;
  clear_consumes_retry_ = consumes_retry;
  return true;
}

bool COFCFantasyBatchExecutor::SendBuildRowBatch(
    const COFCState &state,
    const COFCVisualObservation &observation,
    EOFCRow row,
    string *error) {
  if (p_casino_interface == NULL) {
    return Fail(error, "casino interface unavailable for Fantasy row batch");
  }
  if (!RowEmpty(state, row)) {
    return Fail(error, "Fantasy row batch requires an empty destination row");
  }
  const vector<int> target = TargetRowCards(plan_, row);
  if (static_cast<int>(target.size()) != RowCapacity(row)) {
    return Fail(error, "Fantasy target row does not have exact 3/5/5 capacity");
  }

  vector<RECT> clicks;
  clicks.reserve(target.size() + 1);
  for (size_t i = 0; i < target.size(); ++i) {
    RECT source;
    string source_error;
    if (!ResolveLooseSource(observation, target[i], &source, &source_error)) {
      return Fail(error, source_error);
    }
    clicks.push_back(source);
  }
  // Selecting a card raises it. Right-to-left order minimizes the chance that a
  // raised card masks the still-visible rank/suit anchor of a later selection.
  sort(clicks.begin(), clicks.end(), RectRightToLeft());

  RECT action;
  string rect_error;
  if (!ResolveRowActionRect(row, &action, &rect_error)) {
    return Fail(error, rect_error);
  }
  clicks.push_back(action);

  const int gap_ms = p_tablemap == NULL
    ? 110 : max(60, p_tablemap->GetTMSymbol("ofc_fantasy_select_gap_ms", 110));
  write_log(true,
    "[OpenOFC FANTASY V5] action=SELECT_AND_CHECK row=%s cards=%s clicks=%d gap_ms=%d retry=%d\n",
    RowName(row), CardList(target).c_str(), static_cast<int>(clicks.size()),
    gap_ms, retry_count_[static_cast<int>(row)]);
  if (!p_casino_interface->ClickRectsSafely(clicks, gap_ms)) {
    return Fail(error, "atomic Fantasy select-and-check sequence was refused");
  }
  waiting_row_ = row;
  phase_ = kAwaitRowCommit;
  wait_cycles_ = 0;
  clear_consumes_retry_ = false;
  return true;
}

bool COFCFantasyBatchExecutor::StartNextStableAction(
    const COFCState &state,
    const COFCVisualObservation &observation,
    bool *arrangement_complete,
    string *error) {
  if (arrangement_complete != NULL) *arrangement_complete = false;
  if (!state.valid || !observation.valid || !plan_.valid) {
    return Fail(error, "Fantasy executor received invalid state/observation/plan");
  }
  if (state.hero_chair < 0 || state.hero_chair >= state.player_count
      || !state.players[state.hero_chair].fantasy
      || state.round_index != -1) {
    return Fail(error, "Fantasy executor received non-Fantasy canonical state");
  }

  // First remove any partially/wrongly built row. The contextual row button is
  // red X whenever the row contains cards and yellow check when it is empty.
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    const EOFCRow row = static_cast<EOFCRow>(r);
    if (!RowEmpty(state, row) && !RowMatchesTarget(state, row)) {
      return SendClearRow(row, false, error);
    }
  }

  // Build each row exactly once from a fresh loose-card geometry snapshot.
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    const EOFCRow row = static_cast<EOFCRow>(r);
    if (!RowMatchesTarget(state, row)) {
      return SendBuildRowBatch(state, observation, row, error);
    }
  }

  phase_ = kIdle;
  waiting_row_ = kOFCRowUndefined;
  if (arrangement_complete != NULL) *arrangement_complete = true;
  write_log(true,
    "[OpenOFC FANTASY V5] arrangement_complete=1 rows=3/5/5 confirm_next=1\n");
  return true;
}

bool COFCFantasyBatchExecutor::Start(
    const COFCState &state,
    const COFCVisualObservation &observation,
    const COFCTurnPlan &plan,
    bool *arrangement_complete,
    string *error) {
  Reset();
  if (error != NULL) error->clear();
  if (!plan.valid || !plan.decision_state.valid) {
    return Fail(error, "Fantasy executor received invalid/unbound turn plan");
  }
  if (plan.target_count != 13 || plan.unused_count < 1 || plan.unused_count > 4) {
    return Fail(error, "Fantasy executor requires 13 targets and 1..4 unused cards");
  }
  plan_ = plan;
  return StartNextStableAction(
    state, observation, arrangement_complete, error);
}

bool COFCFantasyBatchExecutor::AdvanceAfterFreshScrape(
    const COFCState &state,
    const COFCVisualObservation &observation,
    bool *arrangement_complete,
    string *error) {
  if (arrangement_complete != NULL) *arrangement_complete = false;
  if (error != NULL) error->clear();
  if (phase_ == kBlocked) {
    if (error != NULL) *error = "Fantasy executor remains blocked";
    return false;
  }
  if (!plan_.valid) {
    return Fail(error, "Fantasy executor has no active turn plan");
  }

  if (phase_ == kAwaitRowCommit) {
    if (RowMatchesTarget(state, waiting_row_)) {
      write_log(true,
        "[OpenOFC FANTASY V5] verify=ROW_COMMIT_OK row=%s\n",
        RowName(waiting_row_));
      phase_ = kIdle;
      waiting_row_ = kOFCRowUndefined;
      wait_cycles_ = 0;
      return StartNextStableAction(
        state, observation, arrangement_complete, error);
    }
    ++wait_cycles_;
    if (wait_cycles_ < kFantasyVerificationWaitCycles) {
      write_log(true,
        "[OpenOFC FANTASY V5] verify=WAIT_ROW_COMMIT row=%s wait=%d/%d\n",
        RowName(waiting_row_), wait_cycles_, kFantasyVerificationWaitCycles);
      return true;
    }

    const int row_index = static_cast<int>(waiting_row_);
    if (row_index < 0 || row_index > 2
        || retry_count_[row_index] >= kFantasyMaximumRebuildRetries) {
      return Fail(error, "Fantasy row did not match target after bounded retry");
    }
    if (RowEmpty(state, waiting_row_)) {
      ++retry_count_[row_index];
      write_log(true,
        "[OpenOFC FANTASY V5] verify=ROW_COMMIT_NOOP row=%s retry=%d\n",
        RowName(waiting_row_), retry_count_[row_index]);
      phase_ = kIdle;
      wait_cycles_ = 0;
      return StartNextStableAction(
        state, observation, arrangement_complete, error);
    }
    return SendClearRow(waiting_row_, true, error);
  }

  if (phase_ == kAwaitRowClear) {
    if (RowEmpty(state, waiting_row_)) {
      const int row_index = static_cast<int>(waiting_row_);
      if (clear_consumes_retry_ && row_index >= 0 && row_index <= 2) {
        ++retry_count_[row_index];
      }
      write_log(true,
        "[OpenOFC FANTASY V5] verify=ROW_CLEAR_OK row=%s retry=%d\n",
        RowName(waiting_row_),
        (row_index >= 0 && row_index <= 2) ? retry_count_[row_index] : -1);
      phase_ = kIdle;
      waiting_row_ = kOFCRowUndefined;
      wait_cycles_ = 0;
      clear_consumes_retry_ = false;
      return StartNextStableAction(
        state, observation, arrangement_complete, error);
    }
    ++wait_cycles_;
    if (wait_cycles_ >= kFantasyVerificationWaitCycles) {
      return Fail(error, "Fantasy row-clear action was not observed");
    }
    write_log(true,
      "[OpenOFC FANTASY V5] verify=WAIT_ROW_CLEAR row=%s wait=%d/%d\n",
      RowName(waiting_row_), wait_cycles_, kFantasyVerificationWaitCycles);
    return true;
  }

  return StartNextStableAction(
    state, observation, arrangement_complete, error);
}
