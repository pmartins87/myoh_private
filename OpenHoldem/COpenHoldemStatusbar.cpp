//******************************************************************************
//
// This file is part of the OpenHoldem project
//    Source code:           https://github.com/OpenHoldem/openholdembot/
//    Forums:                http://www.maxinmontreal.com/forums/index.php
//    Licensed under GPL v3: http://www.gnu.org/licenses/gpl.html
//
//******************************************************************************
//
// Purpose:
//
//******************************************************************************

#include "stdafx.h"
#include "CopenHoldemStatusbar.h"

#include "CAutoplayerFunctions.h"
#include "CAutoplayerTrace.h"
#include "CEngineContainer.h"
#include "CFunctionCollection.h"
#include "CIteratorThread.h"
#include "COFCInspectorSnapshot.h"
#include "CScraper.h"
#include "CSymbolEngineAutoplayer.h"
#include "CSymbolEngineHandrank.h"
#include "CSymbolEngineIsOmaha.h"
#include "CSymbolEnginePrwin.h"
#include "CSymbolEngineTime.h"
#include "CSymbolEngineUserchair.h"
#include "CTableState.h"
#include "resource.h"
#include "..\CTablemap\CTablemap.h"
#include "..\DLLs\StringFunctions_DLL\string_functions.h"

COpenHoldemStatusbar *p_openholdem_statusbar = NULL;

COpenHoldemStatusbar::COpenHoldemStatusbar(CWnd *main_window) {
  _main_window = main_window;
  InitStatusbar();
  SetLastAction("");
  SetPrWin(0, 0, 0);
  SetHandrank(0);
}

COpenHoldemStatusbar::~COpenHoldemStatusbar() {
}

void COpenHoldemStatusbar::InitStatusbar() {
  _status_bar.Create(_main_window);
  static UINT indicators[] = {
    ID_INDICATOR_STATUS_ACTION,
    ID_INDICATOR_STATUS_DUMMY,
    ID_INDICATOR_STATUS_HANDRANK,
    ID_INDICATOR_STATUS_PRWIN,
  };
  _status_bar.SetIndicators(indicators, sizeof(indicators) / sizeof(UINT));
  int position = 0;
  _status_bar.SetPaneInfo(position, ID_INDICATOR_STATUS_ACTION, NULL, 100);
  ++position;
  _status_bar.SetPaneInfo(position, ID_INDICATOR_STATUS_HANDRANK, NULL, 100);
  ++position;
  _status_bar.SetPaneInfo(position, ID_INDICATOR_STATUS_PRWIN, NULL, 100);
  ++position;
  _status_bar.SetPaneInfo(position, ID_INDICATOR_STATUS_DUMMY, SBPS_STRETCH, 280);
  ++position;
}

void COpenHoldemStatusbar::GetWindowRect(RECT *statusbar_position) {
  _status_bar.GetWindowRect(statusbar_position);
}

void COpenHoldemStatusbar::OnUpdateStatusbar() {
  if (p_tablemap != NULL && p_tablemap->SupportsOFCJokerUltimate()) {
    const COFCState *state = p_table_state == NULL ? NULL : p_table_state->OFCState();
    const COFCVisualObservation *raw = p_table_state == NULL
      ? NULL : p_table_state->OFCVisualObservation();
    const int contract = p_tablemap->GetTMSymbol("openofc_contract", 0);
    const bool contract_ok = contract == 1;

    CString round = "Round: ?";
    CString actor = contract_ok ? "Actor: ?" : "TM BLOCKED";
    CString action = contract_ok ? "OpenOFC" : "OFC BLOCKED";

    const bool canonical_ready = state != NULL && state->valid
      && state->hero_chair >= 0 && state->hero_chair < state->player_count;
    if (canonical_ready) {
      if (state->players[state->hero_chair].fantasy) {
        round.Format("Fantasy | in=%d", state->hero_incoming_count);
      } else {
        round.Format("Round %d/5 | in=%d", state->round_index + 1,
          state->hero_incoming_count);
      }
      if (contract_ok) {
        if (state->acting_chair == state->hero_chair) {
          actor = state->hero_can_confirm ? "Hero: CONFIRM" : "Hero: ARRANGE";
        } else if (state->acting_chair >= 0) {
          actor.Format("Waiting P%d", state->acting_chair);
        } else {
          actor = "Waiting actor";
        }
        if (!state->action_required) actor = "Waiting transition";
      }
    }

    // The inspector has two views over one source of truth. Compact goes to the
    // visible status bar. Full is logged only when something changes, making a
    // diagnostic capture readable while preserving exact rows/incoming/discards.
    const CString compact = COFCInspectorSnapshot::Compact(raw, state, contract);
    const CString full = COFCInspectorSnapshot::Full(raw, state, contract);
    static CString last_full_snapshot;
    if (full != last_full_snapshot) {
      write_log(true, "[OpenOFC INSPECTOR] %s\n", full.GetString());
      last_full_snapshot = full;
    }

    _status_bar.SetPaneText(
      _status_bar.CommandToIndex(ID_INDICATOR_STATUS_ACTION), action);
    _status_bar.SetPaneText(
      _status_bar.CommandToIndex(ID_INDICATOR_STATUS_HANDRANK), round);
    _status_bar.SetPaneText(
      _status_bar.CommandToIndex(ID_INDICATOR_STATUS_PRWIN), actor);
    _status_bar.SetPaneText(
      _status_bar.CommandToIndex(ID_INDICATOR_STATUS_DUMMY), compact);
    return;
  }

  if (p_table_state->User()->HasKnownCards()){
    // Format data for display
    // Handrank
    _status_handrank.Format("%i/169", _handrank);
    // PrWin: percentages instead of probabilities
    _status_prwin.Format("PrWin %3.1f/%3.1f/%3.1f",
      100 * _prwin, 100 * _prtie, 100 * _prlos);
  } else if (p_engine_container->symbol_engine_time()->elapsedauto() > 5) {
    // Reset display 5 seconds after last action
    SetPrWin(0, 0, 0);
    SetHandrank(0);
    _status_handrank = "";
    _status_prwin = "";
    _last_action = "";
  } else {
    // No cards, but shortly after last action
    // Don't change anything, keep information
  }
  // Display data
  _status_bar.SetPaneText(_status_bar.CommandToIndex(ID_INDICATOR_STATUS_ACTION), LastAction());
	_status_bar.SetPaneText(_status_bar.CommandToIndex(ID_INDICATOR_STATUS_HANDRANK), _status_handrank);
	_status_bar.SetPaneText(_status_bar.CommandToIndex(ID_INDICATOR_STATUS_PRWIN), _status_prwin);
}

CString COpenHoldemStatusbar::LastAction() {
  if (p_tablemap != NULL && p_tablemap->SupportsOFCJokerUltimate()) {
    return "OpenOFC";
  }
  if (p_engine_container->symbol_engine_userchair() == NULL)	{
		// Very early phase of initialization
		// Can't continue here.
		return "Not playing";
	}
	if (!p_engine_container->symbol_engine_userchair()->userchair_confirmed()) 	{
		return "Not playing";
	}
  // Return the last saved action.
  // This value should get set exactly once after autoplayer/actions
  // to avoid multiple evaluations of the autoplayer-functions,
  // especially at different heartbeats.
  return _last_action;
}

void COpenHoldemStatusbar::SetPrWin(double prwin, double prtie, double prlos) {
  _prwin = prwin;
  _prtie = prtie;
  _prlos = prlos;
}
