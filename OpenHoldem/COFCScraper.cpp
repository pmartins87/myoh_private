//******************************************************************************
// DeepOFC read-only KKPoker Joker Ultimate scraper.
// Populates only COFCVisualObservation; legacy Hold'em cards are untouched.
//******************************************************************************

#include "StdAfx.h"
#include "CScraper.h"

#include <set>

#include "CTableState.h"

using namespace std;

static bool DeepOFCRegionExists(const CString &name) {
  return p_tablemap->r$()->find(name) != p_tablemap->r$()->end();
}

int CScraper::ScrapeOFCSlot(CString base_name, COFCCard *card,
    bool *is_back, bool *is_joker) {
  if ((card == NULL) || (is_back == NULL) || (is_joker == NULL)) return -1;
  card->Clear();
  *is_back = false;
  *is_joker = false;

  const CString empty_region = base_name + "empty";
  const CString back_region = base_name + "back";
  const CString joker_region = base_name + "joker";
  const CString rank_region = base_name + "rank";
  const CString suit_region = base_name + "suit";

  // Negative/background gate: faces and card-backs do not share one reliable
  // positive occupancy colour. If the background is not empty, classification
  // must succeed or the whole OFC observation is rejected.
  if (!DeepOFCRegionExists(empty_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing mandatory slot empty region: %s\n",
      empty_region.GetString());
    return -1;
  }
  bool empty = false;
  EvaluateTrueFalseRegion(&empty, empty_region);
  if (empty) return 0;

  if (!DeepOFCRegionExists(back_region)
      || !DeepOFCRegionExists(joker_region)
      || !DeepOFCRegionExists(rank_region)
      || !DeepOFCRegionExists(suit_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Non-empty slot lacks back/joker/rank/suit contract: %s\n",
      base_name.GetString());
    return -1;
  }

  bool back = false;
  bool joker = false;
  EvaluateTrueFalseRegion(&back, back_region);
  EvaluateTrueFalseRegion(&joker, joker_region);
  if (back && joker) {
    write_log(k_always_log_errors,
      "[DeepOFC] Slot classified as both cardback and Joker: %s\n",
      base_name.GetString());
    return -2;
  }
  if (back) {
    *is_back = true;
    return 0;
  }
  if (joker) {
    *is_joker = true;
    return 1;
  }

  const int legacy_card = ScrapeCardByRankAndSuit(base_name);
  if ((legacy_card >= 0) && (legacy_card <= 51)) {
    card->value = legacy_card;
    return 1;
  }

  write_log(k_always_log_errors,
    "[DeepOFC] Non-empty slot has no unambiguous standard/Joker face: %s\n",
    base_name.GetString());
  return -3;
}

static bool DeepOFCAssignFrameLocalJoker(COFCCard *card, int *joker_count) {
  if (*joker_count >= 2) return false;
  card->value = kOFCCardJoker1 + *joker_count;
  ++(*joker_count);
  return true;
}

static bool DeepOFCRegisterKnownCard(int value, set<int> *seen) {
  if ((value < 0) || (value > kOFCCardJoker2)) return true;
  if (seen->find(value) != seen->end()) return false;
  seen->insert(value);
  return true;
}

static bool DeepOFCObservationHasUniqueKnownCards(
    const COFCVisualObservation *observation) {
  set<int> seen;
  for (int p = 0; p < observation->player_count; ++p) {
    const COFCPlayerBoard &b = observation->players[p].visual_board;
    for (int i = 0; i < kOFCTopCards; ++i)
      if (b.top[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(b.top[i].value, &seen)) return false;
    for (int i = 0; i < kOFCMiddleCards; ++i)
      if (b.middle[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(b.middle[i].value, &seen)) return false;
    for (int i = 0; i < kOFCBottomCards; ++i)
      if (b.bottom[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(b.bottom[i].value, &seen)) return false;
  }
  for (int i = 0; i < observation->hero_loose_count; ++i)
    if (observation->hero_loose_cards[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_loose_cards[i].value, &seen)) return false;
  for (int i = 0; i < observation->hero_discard_tracker_count; ++i)
    if (observation->hero_discard_tracker[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_discard_tracker[i].value, &seen)) return false;
  return true;
}

static bool DeepOFCReadMandatoryBoolean(CScraper *scraper,
    const CString &region, bool *value) {
  if (!DeepOFCRegionExists(region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing mandatory boolean region: %s\n", region.GetString());
    return false;
  }
  *value = false;
  scraper->EvaluateTrueFalseRegion(value, region);
  return true;
}

bool CScraper::ScrapeOFCVisualObservation() {
  if (!p_tablemap->SupportsOFCJokerUltimate()) return false;

  COFCVisualObservation *obs = p_table_state->OFCVisualObservation();
  obs->Reset();

  const int player_count = p_tablemap->GetTMSymbol("ofc_players", 0);
  const int hero_chair = p_tablemap->GetTMSymbol("ofc_hero_chair", -1);
  if (((player_count != 2) && (player_count != 3))
      || (hero_chair < 0) || (hero_chair >= player_count)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Invalid ofc_players/ofc_hero_chair tablemap contract\n");
    return false;
  }
  obs->player_count = player_count;
  obs->hero_chair = hero_chair;

  // Joker artwork may not expose persistent physical identity. JK1/JK2 are
  // deterministic frame-local occurrence labels assigned in scan order.
  int joker_count = 0;

  for (int p = 0; p < player_count; ++p) {
    COFCVisualPlayerObservation *player = &obs->players[p];
    player->occupied = true;
    player->source_chair = p;
    CString base;

    for (int i = 0; i < kOFCTopCards; ++i) {
      base.Format("ofc_p%d_top%d", p, i);
      bool back = false, joker = false;
      int rc = ScrapeOFCSlot(base, &player->visual_board.top[i], &back, &joker);
      if (rc < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker && !DeepOFCAssignFrameLocalJoker(&player->visual_board.top[i], &joker_count)) return false;
    }
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      base.Format("ofc_p%d_middle%d", p, i);
      bool back = false, joker = false;
      int rc = ScrapeOFCSlot(base, &player->visual_board.middle[i], &back, &joker);
      if (rc < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker && !DeepOFCAssignFrameLocalJoker(&player->visual_board.middle[i], &joker_count)) return false;
    }
    for (int i = 0; i < kOFCBottomCards; ++i) {
      base.Format("ofc_p%d_bottom%d", p, i);
      bool back = false, joker = false;
      int rc = ScrapeOFCSlot(base, &player->visual_board.bottom[i], &back, &joker);
      if (rc < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker && !DeepOFCAssignFrameLocalJoker(&player->visual_board.bottom[i], &joker_count)) return false;
    }

    if (p == hero_chair) {
      if (player->hidden_incoming_count != 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Unexpected hidden Hero cardback in row source slots\n");
        return false;
      }
      continue;
    }

    for (int i = 0; i < kOFCMaxDiscards; ++i) {
      base.Format("ofc_p%d_discard%d", p, i);
      COFCCard discard_face;
      bool back = false, joker = false;
      int rc = ScrapeOFCSlot(base, &discard_face, &back, &joker);
      if (rc < 0) return false;
      if (back) {
        ++player->hidden_discard_count;
      } else if (rc > 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Opponent discard identity visible while R1 D1 unresolved: p=%d slot=%d\n",
          p, i);
        return false;
      }
    }
  }

  // Three later-round loose slots are mandatory in the current 450x830 replay
  // geometry. Slots 3/4 remain optional until five-loose-card first-round
  // evidence is captured; physical-card accounting fails closed if needed.
  for (int i = 0; i < 5; ++i) {
    CString base;
    base.Format("ofc_hero_in%d", i);
    if (!DeepOFCRegionExists(base + "empty")) {
      if (i < 3) {
        write_log(k_always_log_errors,
          "[DeepOFC] Missing mandatory Hero incoming slot: %s\n", base.GetString());
        return false;
      }
      continue;
    }
    COFCCard card;
    bool back = false, joker = false;
    int rc = ScrapeOFCSlot(base, &card, &back, &joker);
    if (rc < 0) return false;
    if (back) return false;
    if (joker && !DeepOFCAssignFrameLocalJoker(&card, &joker_count)) return false;
    if (rc > 0) obs->hero_loose_cards[obs->hero_loose_count++] = card;
  }

  for (int i = 0; i < kOFCMaxDiscards; ++i) {
    CString base;
    base.Format("ofc_hero_discard%d", i);
    COFCCard card;
    bool back = false, joker = false;
    int rc = ScrapeOFCSlot(base, &card, &back, &joker);
    if (rc < 0) return false;
    if (back) return false;
    if (joker && !DeepOFCAssignFrameLocalJoker(&card, &joker_count)) return false;
    if (rc > 0) obs->hero_discard_tracker[obs->hero_discard_tracker_count++] = card;
  }

  int dealer_count = 0, actor_count = 0;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool value = false;
    region.Format("ofc_p%d_dealer", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) { obs->dealer_chair = p; ++dealer_count; }

    value = false;
    region.Format("ofc_p%d_turn", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) { obs->acting_chair = p; ++actor_count; }
  }
  if ((dealer_count != 1) || (actor_count != 1)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Expected one dealer/actor; got dealer=%d actor=%d\n",
      dealer_count, actor_count);
    return false;
  }

  if (!DeepOFCReadMandatoryBoolean(this,
        "ofc_confirm_visible", &obs->confirm_visible)) return false;

  const int total_dealt = obs->players[hero_chair].visual_board.CountKnownCards()
    + obs->hero_loose_count + obs->hero_discard_tracker_count;
  switch (total_dealt) {
    case 5: obs->round_index = 0; break;
    case 8: obs->round_index = 1; break;
    case 11: obs->round_index = 2; break;
    case 14: obs->round_index = 3; break;
    case 17: obs->round_index = 4; break;
    default:
      write_log(k_always_log_errors,
        "[DeepOFC] Invalid normal Hero visible-card total: %d\n", total_dealt);
      return false;
  }
  obs->hero_can_prepare = true;

  if (!DeepOFCObservationHasUniqueKnownCards(obs)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Duplicate known physical card in raw observation\n");
    return false;
  }

  obs->valid = true;
  write_log(true,
    "[DeepOFC] raw valid players=%d hero=%d dealer=%d actor=%d round=%d confirm=%d loose=%d discards=%d jokers=%d\n",
    obs->player_count, obs->hero_chair, obs->dealer_chair,
    obs->acting_chair, obs->round_index, obs->confirm_visible ? 1 : 0,
    obs->hero_loose_count, obs->hero_discard_tracker_count, joker_count);
  return true;
}
