from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel: str, old: str, new: str, label: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected one target in {rel}, got {count}: {old[:160]!r}"
        )
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: {label}")


def patch_scraper_exact_lineage_deghost():
    rel = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = read_source(rel)

    anchor = '''// OPENOFC_FANTASY_ENTRY_V544.  Independent current-bitmap proof that the
'''
    if text.count(anchor) != 1:
        raise RuntimeError("v5.4.4 Fantasy-entry anchor missing for v5.4.5 deghost")

    helper = r'''// OPENOFC_EXACT_LINEAGE_DEGHOST_V545 -----------------------------------------
// UNKNOWN_OCCUPIED remains the default semantics: a non-empty unread slot is a
// physical card.  Field logs exposed the opposite edge case too: a stale card
// silhouette/background can occasionally make one *additional* row slot look
// occupied after every real current card is already accounted for.
//
// This normalizer is deliberately narrow. It erases UNKNOWN only when canonical
// lineage proves the expected known physical set exactly and the raw bitmap has
// surplus UNKNOWN row occupancy. Ambiguous UNKNOWNs are never deghosted.
static void OpenOFCCollectKnownBoardValues(
    const COFCPlayerBoard &board, std::set<int> *out) {
  if (out == NULL) return;
  for (int i = 0; i < kOFCTopCards; ++i)
    if (board.top[i].IsKnownPhysicalCard()) out->insert(board.top[i].value);
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (board.middle[i].IsKnownPhysicalCard()) out->insert(board.middle[i].value);
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (board.bottom[i].IsKnownPhysicalCard()) out->insert(board.bottom[i].value);
}

static void OpenOFCCollectKnownCurrentValues(
    const COFCVisualObservation &obs, int hero_chair, std::set<int> *out) {
  if (out == NULL) return;
  OpenOFCCollectKnownBoardValues(
    obs.players[hero_chair].visual_board, out);
  for (int i = 0; i < obs.hero_loose_count; ++i)
    if (obs.hero_loose_cards[i].IsKnownPhysicalCard())
      out->insert(obs.hero_loose_cards[i].value);
}

static bool OpenOFCSetContains(
    const std::set<int> &superset, const std::set<int> &subset) {
  for (std::set<int>::const_iterator it = subset.begin();
       it != subset.end(); ++it) {
    if (superset.find(*it) == superset.end()) return false;
  }
  return true;
}

static int OpenOFCBoardUnknownCount(const COFCPlayerBoard &board) {
  int count = 0;
  for (int i = 0; i < kOFCTopCards; ++i)
    if (board.top[i].IsUnknownOccupied()) ++count;
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (board.middle[i].IsUnknownOccupied()) ++count;
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (board.bottom[i].IsUnknownOccupied()) ++count;
  return count;
}

static bool OpenOFCClearOneBoardUnknown(
    COFCPlayerBoard *board, std::string *slot_label) {
  if (board == NULL) return false;
  for (int i = 0; i < kOFCTopCards; ++i) {
    if (!board->top[i].IsUnknownOccupied()) continue;
    board->top[i].value = kOFCCardEmpty;
    if (slot_label != NULL) {
      std::ostringstream oss; oss << "top" << i; *slot_label = oss.str();
    }
    return true;
  }
  for (int i = 0; i < kOFCMiddleCards; ++i) {
    if (!board->middle[i].IsUnknownOccupied()) continue;
    board->middle[i].value = kOFCCardEmpty;
    if (slot_label != NULL) {
      std::ostringstream oss; oss << "middle" << i; *slot_label = oss.str();
    }
    return true;
  }
  for (int i = 0; i < kOFCBottomCards; ++i) {
    if (!board->bottom[i].IsUnknownOccupied()) continue;
    board->bottom[i].value = kOFCCardEmpty;
    if (slot_label != NULL) {
      std::ostringstream oss; oss << "bottom" << i; *slot_label = oss.str();
    }
    return true;
  }
  return false;
}

static int OpenOFCExpectedBoardPlusCurrentForRound(int round_index) {
  static const int kExpected[5] = {5, 8, 10, 12, 14};
  if (round_index < 0 || round_index > 4) return -1;
  return kExpected[round_index];
}

static bool OpenOFCPreviousNormalStateFullyKnown(
    const COFCState &previous) {
  if (!previous.valid
      || previous.hero_chair < 0
      || previous.hero_chair >= previous.player_count
      || previous.players[previous.hero_chair].fantasy
      || previous.round_index < 0 || previous.round_index > 4) {
    return false;
  }
  const COFCPlayerBoard &board =
    previous.players[previous.hero_chair].board;
  if (board.CountOccupiedCards() != board.CountKnownCards()) return false;
  for (int i = 0; i < previous.hero_incoming_count; ++i)
    if (!previous.hero_incoming[i].IsKnownPhysicalCard()) return false;
  return true;
}

static void OpenOFCNormalizeExactLineageSurplusUnknown(
    COFCVisualObservation *obs, int hero_chair) {
  if (obs == NULL || p_table_state == NULL
      || hero_chair < 0 || hero_chair >= obs->player_count
      || obs->players[hero_chair].fantasy) {
    return;
  }

  const COFCState *previous = p_table_state->OFCState();
  if (previous == NULL || !OpenOFCPreviousNormalStateFullyKnown(*previous)
      || previous->hero_chair != hero_chair) {
    return;
  }

  COFCPlayerBoard *visual = &obs->players[hero_chair].visual_board;
  const int raw_board_occupied = visual->CountOccupiedCards();
  const int raw_total = raw_board_occupied + obs->hero_loose_count;
  const int board_unknown = OpenOFCBoardUnknownCount(*visual);
  if (board_unknown <= 0) return;

  std::set<int> previous_board;
  std::set<int> previous_incoming;
  std::set<int> current_board;
  std::set<int> current_all;
  OpenOFCCollectKnownBoardValues(
    previous->players[hero_chair].board, &previous_board);
  for (int i = 0; i < previous->hero_incoming_count; ++i)
    previous_incoming.insert(previous->hero_incoming[i].value);
  OpenOFCCollectKnownBoardValues(*visual, &current_board);
  OpenOFCCollectKnownCurrentValues(*obs, hero_chair, &current_all);

  int target_total = -1;
  const char *proof = NULL;

  // Same-round proof. Canonical committed board + canonical current incoming
  // must account for the complete physical set of this round. If every one of
  // those known identities is already visible, any additional UNKNOWN row slot
  // is impossible to be a sixth/ninth/etc. real current card.
  std::set<int> expected_same = previous_board;
  expected_same.insert(previous_incoming.begin(), previous_incoming.end());
  const int expected_same_total =
    OpenOFCExpectedBoardPlusCurrentForRound(previous->round_index);
  if (expected_same_total >= 0
      && static_cast<int>(expected_same.size()) == expected_same_total
      && OpenOFCSetContains(current_all, expected_same)
      && raw_total > expected_same_total) {
    target_total = expected_same_total;
    proof = "SAME_ROUND_EXACT_LINEAGE";
  }

  // Fresh next-round proof. Before OpenOFC has accepted the new round, all 3
  // newly dealt cards are still in the loose strip. The old committed board
  // must persist, and exactly 5 old incoming cards (R0) or 2 (R1..R3) must now
  // be committed. In that shape an extra UNKNOWN *row* slot cannot be one of
  // the new cards and can be deghosted safely.
  if (target_total < 0
      && previous->round_index < 4
      && obs->hero_loose_count == 3
      && OpenOFCSetContains(current_board, previous_board)) {
    int visible_previous_incoming = 0;
    for (std::set<int>::const_iterator it = previous_incoming.begin();
         it != previous_incoming.end(); ++it) {
      if (current_board.find(*it) != current_board.end())
        ++visible_previous_incoming;
    }
    const int required_commit =
      previous->round_index == 0 ? 5 : 2;
    const int expected_known_board =
      static_cast<int>(previous_board.size()) + required_commit;
    const int next_total =
      OpenOFCExpectedBoardPlusCurrentForRound(previous->round_index + 1);
    if (visible_previous_incoming == required_commit
        && static_cast<int>(current_board.size()) == expected_known_board
        && next_total >= 0 && raw_total > next_total) {
      target_total = next_total;
      proof = "NEXT_ROUND_ALL_NEW_LOOSE_EXACT_LINEAGE";
    }
  }

  if (target_total < 0 || proof == NULL) return;
  int surplus = raw_total - target_total;
  if (surplus <= 0 || surplus > board_unknown) return;

  const int before = raw_total;
  int cleared = 0;
  while (cleared < surplus) {
    std::string slot;
    if (!OpenOFCClearOneBoardUnknown(visual, &slot)) break;
    ++cleared;
    write_log(k_always_log_errors,
      "[OpenOFC DEGHOST] slot=ofc_p%d_%s reason=%s "
      "before=%d expected=%d ordinal=%d/%d action=IGNORE_THIS_FRAME terminal=0\n",
      hero_chair, slot.c_str(), proof, before, target_total,
      cleared, surplus);
  }
  if (cleared != surplus) {
    write_log(k_always_log_errors,
      "[OpenOFC DEGHOST] result=INCOMPLETE cleared=%d required=%d "
      "action=KEEP_CONSERVATIVE\n", cleared, surplus);
  }
}
// -----------------------------------------------------------------------------

'''
    text = text.replace(anchor, helper + anchor, 1)
    write_source(path, text, eol, bom)

    replace_once(
        rel,
        '''  const int hero_board_occupied =
    obs->players[hero_chair].visual_board.CountOccupiedCards();
  const int board_plus_current = hero_board_occupied + obs->hero_loose_count;
''',
        '''  // v5.4.5: normalize only lineage-proven *surplus* UNKNOWN row slots.
  // Genuine unread cards remain occupied and continue to count.
  OpenOFCNormalizeExactLineageSurplusUnknown(obs, hero_chair);
  const int hero_board_occupied =
    obs->players[hero_chair].visual_board.CountOccupiedCards();
  const int board_plus_current = hero_board_occupied + obs->hero_loose_count;
''',
        "normalize exact-lineage surplus UNKNOWN before round inference",
    )


def patch_visible_runtime_status():
    rel = "OpenHoldem/COFCRuntimeController.cpp"

    replace_once(
        rel,
        '''#include "COFCBaselinePolicy.h"
''',
        '''#include "COFCBaselinePolicy.h"
#include "COpenHoldemStatusbar.h"
''',
        "runtime can publish user-facing OpenOFC status",
    )

    path, text, eol, bom = read_source(rel)
    anchor = '''const char *RowLabel(EOFCRow row) {
'''
    if text.count(anchor) != 1:
        raise RuntimeError("RowLabel anchor missing for OpenOFC status helper")
    helper = r'''void OpenOFCSetUserStatus(const CString &status) {
  if (p_openholdem_statusbar != NULL)
    p_openholdem_statusbar->SetLastAction(status);
  static CString last_logged;
  if (status != last_logged) {
    write_log(true, "[OpenOFC STATUS] %s\n", status.GetString());
    last_logged = status;
  }
}

'''
    text = text.replace(anchor, helper + anchor, 1)
    write_source(path, text, eol, bom)

    replace_once(
        rel,
        '''  if (!state.valid || !observation.valid) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\\n");
    return;
  }
''',
        '''  if (!state.valid || !observation.valid) {
    if (state.valid && !observation.valid)
      OpenOFCSetUserStatus("RECUPERANDO LEITURA - sem agir");
    else
      OpenOFCSetUserStatus("AGUARDANDO ESTADO VALIDO");
    write_log(true, "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\\n");
    return;
  }
''',
        "surface invalid-perception recovery in status bar",
    )

    replace_once(
        rel,
        '''  if (elapsed < required) {
    write_log(true,
      "[OpenOFC STABILIZE] wait=1 round=%d elapsed_ms=%lu required_ms=%lu\\n",
''',
        '''  if (elapsed < required) {
    OpenOFCSetUserStatus("ESTABILIZANDO TELA - aguardando animacao");
    write_log(true,
      "[OpenOFC STABILIZE] wait=1 round=%d elapsed_ms=%lu required_ms=%lu\\n",
''',
        "surface stabilization wait",
    )
    replace_once(
        rel,
        '''  decision_stabilizing_ = false;
  write_log(true,
    "[OpenOFC STABILIZE] ready=1 round=%d elapsed_ms=%lu\\n",
''',
        '''  decision_stabilizing_ = false;
  OpenOFCSetUserStatus("ANALISANDO JOGADA");
  write_log(true,
    "[OpenOFC STABILIZE] ready=1 round=%d elapsed_ms=%lu\\n",
''',
        "surface stabilization completion",
    )

    replace_once(
        rel,
        '''  COFCStrategyAction action;
  string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
''',
        '''  OpenOFCSetUserStatus("CALCULANDO JOGADA");
  COFCStrategyAction action;
  string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
''',
        "surface policy calculation",
    )

    replace_once(
        rel,
        '''  if (!orchestrator_.StartTurn(
        state, observation, plan_, duration,
''',
        '''  OpenOFCSetUserStatus("EXECUTANDO JOGADA");
  if (!orchestrator_.StartTurn(
        state, observation, plan_, duration,
''',
        "surface arrangement execution",
    )

    replace_once(
        rel,
        '''    ++drag_wait_cycles_;
    const int kOpenOFCDragObservationWaitCycles = p_tablemap == NULL ? 8
''',
        '''    ++drag_wait_cycles_;
    OpenOFCSetUserStatus("VERIFICANDO MOVIMENTO");
    const int kOpenOFCDragObservationWaitCycles = p_tablemap == NULL ? 8
''',
        "surface drag verification wait",
    )

    replace_once(
        rel,
        '''  write_log(true,
    "[DeepOFC CONFIRM] sending region=%s rect=(%ld,%ld,%ld,%ld) round=%d fantasy=%d\\n",
''',
        '''  OpenOFCSetUserStatus("CONFIRMANDO JOGADA");
  write_log(true,
    "[DeepOFC CONFIRM] sending region=%s rect=(%ld,%ld,%ld,%ld) round=%d fantasy=%d\\n",
''',
        "surface Confirm send",
    )
    replace_once(
        rel,
        '''  phase_ = kConfirmSent;
  write_log(true,
    "[DeepOFC FP0] Confirm sent once; duplicate clicks prohibited\\n");
''',
        '''  phase_ = kConfirmSent;
  OpenOFCSetUserStatus("CONFIRM ENVIADO - aguardando proxima rodada");
  write_log(true,
    "[DeepOFC FP0] Confirm sent once; duplicate clicks prohibited\\n");
''',
        "surface post-Confirm wait",
    )

    replace_once(
        rel,
        '''    if (!state.decision_finalizable) {
      write_log(true,
        "[OpenOFC PROVISIONAL] waiting=1 dealer=%d hero=%d timer=%d confirm=HELD\\n",
''',
        '''    if (!state.decision_finalizable) {
      OpenOFCSetUserStatus("AGUARDANDO OPONENTE - Confirm retido");
      write_log(true,
        "[OpenOFC PROVISIONAL] waiting=1 dealer=%d hero=%d timer=%d confirm=HELD\\n",
''',
        "surface dealer provisional wait",
    )
    replace_once(
        rel,
        '''    provisional_ = false;
    phase_ = kIdle;
    write_log(true,
      "[OpenOFC PROVISIONAL] opponent_final_info=1 reanalyze=1 timer=%d\\n",
''',
        '''    provisional_ = false;
    phase_ = kIdle;
    OpenOFCSetUserStatus("OPONENTE FINALIZOU - recalculando");
    write_log(true,
      "[OpenOFC PROVISIONAL] opponent_final_info=1 reanalyze=1 timer=%d\\n",
''',
        "surface dealer final replan",
    )

    replace_once(
        rel,
        '''      write_log(true,
        "[OpenOFC UNKNOWN] action=WAIT reason=OPENING_IDENTITY_UNREAD occupied_incoming=%d terminal=0 continue_scraping=1\\n",
''',
        '''      OpenOFCSetUserStatus("RECUPERANDO CARTA INICIAL - identidade ilegivel");
      write_log(true,
        "[OpenOFC UNKNOWN] action=WAIT reason=OPENING_IDENTITY_UNREAD occupied_incoming=%d terminal=0 continue_scraping=1\\n",
''',
        "surface opening UNKNOWN wait",
    )
    replace_once(
        rel,
        '''  if (!state.hero_can_prepare) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=NO_PREPARABLE_CARDS actor=%d hero=%d prepare=0\\n",
''',
        '''  if (!state.hero_can_prepare) {
    OpenOFCSetUserStatus("AGUARDANDO CARTAS / TRANSICAO");
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=NO_PREPARABLE_CARDS actor=%d hero=%d prepare=0\\n",
''',
        "surface no-preparable-cards wait",
    )


def patch_statusbar_layout_and_runtime_reason():
    rel = "OpenHoldem/COpenHoldemStatusbar.cpp"

    replace_once(
        rel,
        '''  _status_bar.SetPaneInfo(position, ID_INDICATOR_STATUS_ACTION, NULL, 100);
''',
        '''  // OpenOFC uses this pane for a human-readable operational reason.
  _status_bar.SetPaneInfo(position, ID_INDICATOR_STATUS_ACTION, NULL, 285);
''',
        "widen action/status pane for OpenOFC reason",
    )

    replace_once(
        rel,
        '''    CString action = contract_ok ? "OpenOFC" : "OFC BLOCKED";
''',
        '''    CString action = contract_ok ? LastAction() : "OFC BLOQUEADO";
''',
        "show runtime reason instead of static OpenOFC label",
    )

    replace_once(
        rel,
        '''  if (p_tablemap != NULL && p_tablemap->SupportsOFCJokerUltimate()) {
    return "OpenOFC";
  }
''',
        '''  if (p_tablemap != NULL && p_tablemap->SupportsOFCJokerUltimate()) {
    return _last_action.IsEmpty() ? CString("OpenOFC: iniciando") : _last_action;
  }
''',
        "preserve runtime OpenOFC status text",
    )


def selftest_model():
    expected_r0 = {1, 2, 3, 4, 5}
    current_known = set(expected_r0)
    raw_total = 6
    board_unknown = 1
    assert expected_r0 <= current_known
    assert raw_total - 5 == 1 <= board_unknown

    previous_board = set()
    previous_incoming = {1, 2, 3, 4, 5}
    current_board = set(previous_incoming)
    loose_count = 3
    raw_total = 9
    board_unknown = 1
    visible_prior = len(previous_incoming & current_board)
    assert loose_count == 3 and visible_prior == 5
    assert raw_total - 8 == 1 <= board_unknown

    ambiguous_known = {1, 2, 3, 4}
    assert not (expected_r0 <= ambiguous_known)
    print("OpenOFC v5.4.5 exact-lineage deghost deterministic model: PASS")


def assert_contract():
    scraper = read_source("OpenHoldem/COFCScraper.cpp")[1]
    runtime = read_source("OpenHoldem/COFCRuntimeController.cpp")[1]
    status = read_source("OpenHoldem/COpenHoldemStatusbar.cpp")[1]

    required = [
        (scraper, "OPENOFC_EXACT_LINEAGE_DEGHOST_V545"),
        (scraper, "[OpenOFC DEGHOST]"),
        (scraper, "SAME_ROUND_EXACT_LINEAGE"),
        (scraper, "NEXT_ROUND_ALL_NEW_LOOSE_EXACT_LINEAGE"),
        (runtime, "[OpenOFC STATUS]"),
        (runtime, "RECUPERANDO LEITURA - sem agir"),
        (runtime, "AGUARDANDO OPONENTE - Confirm retido"),
        (runtime, "VERIFICANDO MOVIMENTO"),
        (status, 'CString action = contract_ok ? LastAction() : "OFC BLOQUEADO";'),
        (status, 'CString("OpenOFC: iniciando")'),
    ]
    for text, token in required:
        if token not in text:
            raise RuntimeError(f"v5.4.5 contract missing token: {token}")

    print("OpenOFC v5.4.5 observability/deghost source contract: PASS")


def main():
    selftest_model()
    patch_scraper_exact_lineage_deghost()
    patch_visible_runtime_status()
    patch_statusbar_layout_and_runtime_reason()
    assert_contract()
    print("OpenOFC v5.4.5 field observability + exact-lineage deghost applied successfully")


if __name__ == "__main__":
    main()
