//******************************************************************************
//
// DeepOFC read-only KKPoker Joker Ultimate scraper.
//
// This compilation unit is intentionally isolated from legacy Hold'em
// hole/common-card storage. It populates only COFCVisualObservation.
// Integration into the heartbeat/project file remains gated by replay and
// Windows-build validation.
//
//******************************************************************************

#include "StdAfx.h"
#include "CScraper.h"

#include <set>
#include <vector>

#include "CAutoOcr.h"
#include "CTableState.h"

using namespace std;

int CScraper::OFCString2CardNumber(CString card) {
  CString normalized = card;
  normalized.Trim();
  CString upper = normalized;
  upper.MakeUpper();

  if ((upper == "JK1") || (upper == "JOKER1") || (upper == "JOKER_1")) {
    return kOFCCardJoker1;
  }
  if ((upper == "JK2") || (upper == "JOKER2") || (upper == "JOKER_2")) {
    return kOFCCardJoker2;
  }
  if ((upper == "CARDBACK") || (upper == "BACK") || (upper == "CB")) {
    return kOFCCardBack;
  }
  if ((upper == "NOCARD") || (upper == "NO_CARD") || (upper == "FALSE")
      || upper.IsEmpty()) {
    return kOFCCardNoCard;
  }

  int legacy_card = CardString2CardNumber(normalized);
  if ((legacy_card >= 0) && (legacy_card <= 51)) {
    return legacy_card;
  }
  return kOFCCardUnknown;
}

int CScraper::ScrapeOFCAreaCards(CString area_name, COFCCard *cards,
    int max_cards, int *hidden_back_count) {
  if (hidden_back_count != NULL) {
    *hidden_back_count = 0;
  }
  if ((cards != NULL) && (max_cards > 0)) {
    for (int i = 0; i < max_cards; ++i) {
      cards[i].Clear();
    }
  }

  RMapCI r_iter = p_tablemap->r$()->find(area_name);
  if (r_iter == p_tablemap->r$()->end()) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing mandatory area: %s\n", area_name.GetString());
    return -1;
  }

  int r_width = r_iter->second.right - r_iter->second.left;
  int r_height = r_iter->second.bottom - r_iter->second.top;
  if ((r_width <= 0) || (r_height <= 0)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Invalid area geometry: %s\n", area_name.GetString());
    return -1;
  }

  vector<CString> detected = p_auto_ocr->GetDetectTemplatesResult(r_iter->second.name);
  int face_count = 0;
  for (vector<CString>::const_iterator it = detected.begin(); it != detected.end(); ++it) {
    int value = OFCString2CardNumber(*it);
    if (value == kOFCCardBack) {
      if (hidden_back_count != NULL) {
        ++(*hidden_back_count);
      }
      continue;
    }
    if (value == kOFCCardNoCard) {
      continue;
    }
    if (value == kOFCCardUnknown) {
      write_log(k_always_log_errors,
        "[DeepOFC] Unknown detector label [%s] in %s\n",
        it->GetString(), area_name.GetString());
      return -2;
    }
    if ((cards == NULL) || (face_count >= max_cards)) {
      write_log(k_always_log_errors,
        "[DeepOFC] Too many/unsupported face cards in %s\n",
        area_name.GetString());
      return -3;
    }
    cards[face_count].value = value;
    ++face_count;
  }
  return face_count;
}

static bool DeepOFCRegisterKnownCard(int value, set<int> *seen) {
  if ((value < 0) || (value > kOFCCardJoker2)) {
    return true;
  }
  if (seen->find(value) != seen->end()) {
    return false;
  }
  seen->insert(value);
  return true;
}

static bool DeepOFCObservationHasUniqueKnownCards(
    const COFCVisualObservation *observation) {
  set<int> seen;
  for (int p = 0; p < observation->player_count; ++p) {
    const COFCPlayerBoard &board = observation->players[p].visual_board;
    for (int i = 0; i < kOFCTopCards; ++i) {
      if (board.top[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(board.top[i].value, &seen)) return false;
    }
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      if (board.middle[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(board.middle[i].value, &seen)) return false;
    }
    for (int i = 0; i < kOFCBottomCards; ++i) {
      if (board.bottom[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(board.bottom[i].value, &seen)) return false;
    }
  }
  for (int i = 0; i < observation->hero_loose_count; ++i) {
    if (observation->hero_loose_cards[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_loose_cards[i].value, &seen)) return false;
  }
  for (int i = 0; i < observation->hero_discard_tracker_count; ++i) {
    if (observation->hero_discard_tracker[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_discard_tracker[i].value, &seen)) return false;
  }
  return true;
}

bool CScraper::ScrapeOFCVisualObservation() {
  if (!p_tablemap->SupportsOFCJokerUltimate()) {
    return false;
  }

  COFCVisualObservation *observation = p_table_state->OFCVisualObservation();
  observation->Reset();

  const int player_count = p_tablemap->GetTMSymbol("ofc_players", 0);
  const int hero_chair = p_tablemap->GetTMSymbol("ofc_hero_chair", -1);
  if (((player_count != 2) && (player_count != 3))
      || (hero_chair < 0) || (hero_chair >= player_count)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Invalid ofc_players/ofc_hero_chair tablemap contract\n");
    return false;
  }
  observation->player_count = player_count;
  observation->hero_chair = hero_chair;

  for (int p = 0; p < player_count; ++p) {
    COFCVisualPlayerObservation *player = &observation->players[p];
    player->occupied = true;
    player->source_chair = p;

    CString area;
    int backs_top = 0;
    int backs_middle = 0;
    int backs_bottom = 0;

    area.Format("area_ofc_p%d_top", p);
    if (ScrapeOFCAreaCards(area, player->visual_board.top,
          kOFCTopCards, &backs_top) < 0) return false;
    area.Format("area_ofc_p%d_middle", p);
    if (ScrapeOFCAreaCards(area, player->visual_board.middle,
          kOFCMiddleCards, &backs_middle) < 0) return false;
    area.Format("area_ofc_p%d_bottom", p);
    if (ScrapeOFCAreaCards(area, player->visual_board.bottom,
          kOFCBottomCards, &backs_bottom) < 0) return false;

    player->hidden_incoming_count = backs_top + backs_middle + backs_bottom;

    if (p != hero_chair) {
      int discard_backs = 0;
      area.Format("area_ofc_p%d_discards", p);
      if (ScrapeOFCAreaCards(area, NULL, 0, &discard_backs) < 0) return false;
      player->hidden_discard_count = discard_backs;
    } else {
      // Hero must never have hidden backs in row areas in normal play.
      if (player->hidden_incoming_count != 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Unexpected hidden Hero cardback in visual board\n");
        return false;
      }
    }
  }

  int hero_loose_backs = 0;
  if (ScrapeOFCAreaCards("area_ofc_hero_incoming",
        observation->hero_loose_cards, kOFCMaxIncomingCards,
        &hero_loose_backs) < 0) return false;
  if (hero_loose_backs != 0) {
    write_log(k_always_log_errors,
      "[DeepOFC] Hero incoming area contains hidden cardbacks\n");
    return false;
  }
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (observation->hero_loose_cards[i].IsKnownPhysicalCard()) {
      ++observation->hero_loose_count;
    }
  }

  int hero_discard_backs = 0;
  if (ScrapeOFCAreaCards("area_ofc_hero_discards",
        observation->hero_discard_tracker, kOFCMaxDiscards,
        &hero_discard_backs) < 0) return false;
  if (hero_discard_backs != 0) {
    write_log(k_always_log_errors,
      "[DeepOFC] Hero discard tracker unexpectedly contains cardbacks\n");
    return false;
  }
  for (int i = 0; i < kOFCMaxDiscards; ++i) {
    if (observation->hero_discard_tracker[i].IsKnownPhysicalCard()) {
      ++observation->hero_discard_tracker_count;
    }
  }

  int dealer_count = 0;
  int actor_count = 0;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool dealer = false;
    region.Format("ofc_p%d_dealer", p);
    EvaluateTrueFalseRegion(&dealer, region);
    if (dealer) {
      observation->dealer_chair = p;
      ++dealer_count;
    }

    bool acting = false;
    region.Format("ofc_p%d_turn", p);
    EvaluateTrueFalseRegion(&acting, region);
    if (acting) {
      observation->acting_chair = p;
      ++actor_count;
    }
  }
  if ((dealer_count != 1) || (actor_count != 1)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Expected exactly one dealer and one acting player; got dealer=%d actor=%d\n",
      dealer_count, actor_count);
    return false;
  }

  observation->confirm_visible = false;
  EvaluateTrueFalseRegion(&observation->confirm_visible, "ofc_confirm_visible");

  const COFCPlayerBoard &hero_visual = observation->players[hero_chair].visual_board;
  const int total_dealt = hero_visual.CountKnownCards()
    + observation->hero_loose_count
    + observation->hero_discard_tracker_count;
  switch (total_dealt) {
    case 5:  observation->round_index = 0; break;
    case 8:  observation->round_index = 1; break;
    case 11: observation->round_index = 2; break;
    case 14: observation->round_index = 3; break;
    case 17: observation->round_index = 4; break;
    default:
      write_log(k_always_log_errors,
        "[DeepOFC] Invalid normal-play Hero visible-card total: %d\n", total_dealt);
      return false;
  }
  observation->hero_can_prepare = true;

  if (!DeepOFCObservationHasUniqueKnownCards(observation)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Duplicate known physical card in raw visual observation\n");
    return false;
  }

  observation->valid = true;
  write_log(true,
    "[DeepOFC] raw observation valid players=%d hero=%d dealer=%d actor=%d round=%d confirm_visible=%d loose=%d discards=%d\n",
    observation->player_count,
    observation->hero_chair,
    observation->dealer_chair,
    observation->acting_chair,
    observation->round_index,
    observation->confirm_visible ? 1 : 0,
    observation->hero_loose_count,
    observation->hero_discard_tracker_count);
  return true;
}
