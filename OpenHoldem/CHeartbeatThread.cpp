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
#include "CHeartbeatThread.h"

#include <process.h>
#include "CAutoconnector.h"
#include "CAutoplayer.h"
#include "CAutoplayerFunctions.h"
#include "CBetroundCalculator.h"
#include "CHeartbeatDelay.h"
#include "CEngineContainer.h"
#include "CIteratorThread.h"
#include "CLazyScraper.h"
#include "COpenHoldemHopperCommunication.h"
#include "COpenHoldemStarter.h"
#include "COpenHoldemStatusbar.h"
#include "COpenHoldemTitle.h"

#include "CScraper.h"
#include "CSymbolEngineAutoplayer.h"
#include "CSymbolEngineChipAmounts.h"
#include "CSymbolEngineUserchair.h"
#include "..\CTablemap\CTablemap.h"
#include "CTableMapLoader.h"
#include "CTablepointChecker.h"
#include "CTableTitle.h"
#include "CTablePositioner.h"
#include "CValidator.h"
#include "DialogScraperOutput.h"
#include "MainFrm.h"
#include "MemoryLogging.h"

#include "OpenHoldem.h"

CHeartbeatThread	 *p_heartbeat_thread = NULL;
CRITICAL_SECTION	 CHeartbeatThread::cs_update_in_progress;
long int			     CHeartbeatThread::_heartbeat_counter = 0;
CHeartbeatThread   *CHeartbeatThread::pParent = NULL;
CHeartbeatDelay    CHeartbeatThread::_heartbeat_delay;
COpenHoldemStarter CHeartbeatThread::_openholdem_starter;

namespace {
const int kOpenOFCContractVersion = 1;
}

CHeartbeatThread::CHeartbeatThread() {
	InitializeCriticalSectionAndSpinCount(&cs_update_in_progress, 4000);
  _heartbeat_counter = 0;
  // Create events
	_m_stop_thread = CreateEvent(0, TRUE, FALSE, 0);
	_m_wait_thread = CreateEvent(0, TRUE, FALSE, 0);
}

CHeartbeatThread::~CHeartbeatThread() {
	// Trigger thread to stop
	::SetEvent(_m_stop_thread);

	// Wait until thread finished
	::WaitForSingleObject(_m_wait_thread, k_max_time_to_wait_for_thread_to_shutdown);

	// Close handles
	::CloseHandle(_m_stop_thread);
	::CloseHandle(_m_wait_thread);

	DeleteCriticalSection(&cs_update_in_progress);
	p_heartbeat_thread = NULL;
}

void CHeartbeatThread::StartThread() {
	// Start thread
	write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] Starting heartbeat thread\n");
    assert(this != NULL);
	AfxBeginThread(HeartbeatThreadFunction, this);
}

UINT CHeartbeatThread::HeartbeatThreadFunction(LPVOID pParam) {
  CTablepointChecker tablepoint_checker;
	pParent = static_cast<CHeartbeatThread*>(pParam);
  assert(pParent != NULL);
	// Seed the RNG
	srand((unsigned)GetTickCount());

	while (true) {
		_heartbeat_counter++;
		write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] Starting next cycle\n");
		// Check event for stop thread
		if(::WaitForSingleObject(pParent->_m_stop_thread, 0) == WAIT_OBJECT_0) {
			// Set event
      write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] Ending heartbeat thread\n");
      LogMemoryUsage("Hc");
			::SetEvent(pParent->_m_wait_thread);
			AfxEndThread(0);
		}
    assert(p_tablemap_loader != NULL);
    LogMemoryUsage("H1");
		p_tablemap_loader->ReloadAllTablemapsIfChanged();
    LogMemoryUsage("H2");
    assert(p_autoconnector != NULL);
    write_log(Preferences()->debug_alltherest(), "[CHeartbeatThread] location Johnny_B\n");
    if (p_autoconnector->IsConnectedToGoneWindow()) {
      LogMemoryUsage("H3");
      p_autoconnector->Disconnect("table disappeared");
    }
    LogMemoryUsage("H4");
    if (!p_autoconnector->IsConnectedToAnything()) {
      // Not connected
      AutoConnect();
    }
    // No "else" here
    // We want one fast scrape immediately after connection
    // without any heartbeat-sleeping.
    LogMemoryUsage("H5");
    write_log(Preferences()->debug_alltherest(), "[CHeartbeatThread] location Johnny_C\n");
		if (p_autoconnector->IsConnectedToExistingWindow()) {
      if (tablepoint_checker.TablepointsMismatchedTheLastNHeartbeats()) {
        LogMemoryUsage("H6");
        p_autoconnector->Disconnect("table theme changed (tablepoints)");
      } else {
        LogMemoryUsage("H7");
        ScrapeEvaluateAct();
      } 		
		}
    assert(p_watchdog != NULL);
    LogMemoryUsage("H8");
    p_watchdog->HandleCrashedAndFrozenProcesses();
    if (Preferences()->use_auto_starter()) {
      LogMemoryUsage("H9");
      _openholdem_starter.StartNewInstanceIfNeeded();
    }
    LogMemoryUsage("Ha");
    if (Preferences()->use_auto_shutdown()) {
      _openholdem_starter.CloseThisInstanceIfNoLongerNeeded();
    }
    LogMemoryUsage("Hb");
    _heartbeat_delay.FlexibleSleep();
		write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] Heartbeat cycle ended\n");
    LogMemoryUsage("End of heartbeat cycle");
	}
}

void CHeartbeatThread::ScrapeEvaluateAct() {
	p_table_positioner->AlwaysKeepPositionIfEnabled();
	// This critical section lets other threads know that the internal state is being updated
	EnterCriticalSection(&pParent->cs_update_in_progress);

	////////////////////////////////////////////////////////////////////////////////////////////
	// Scrape window
  p_table_title->UpdateTitle();
  write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] Calling DoScrape.\n");
  p_lazyscraper->DoScrape();

  // OpenOFC has its own perception, canonical state and action transaction.
  // Do not run the Hold'em symbol-engine graph for an OFC table. Besides being
  // strategically meaningless, that graph derives concepts such as blinds,
  // betting rounds, handrank/prwin, raise/call/check/fold and userchair from a
  // layout that does not contain those semantics. Keeping it out of the OFC
  // heartbeat is the architectural boundary between OpenHoldem compatibility
  // code and the OFC-native runtime.
  const bool openofc_mode = (p_tablemap != NULL)
    && p_tablemap->SupportsOFCJokerUltimate();
  const int openofc_contract = openofc_mode
    ? p_tablemap->GetTMSymbol("openofc_contract", 0)
    : 0;
  const bool openofc_contract_ok = !openofc_mode
    || (openofc_contract == kOpenOFCContractVersion);
  if (openofc_mode) {
    static CString last_logged_tablemap;
    static int last_logged_contract = -1;
    const CString current_tablemap = p_tablemap->filepath();
    if ((last_logged_tablemap != current_tablemap)
        || (last_logged_contract != openofc_contract)) {
      if (openofc_contract_ok) {
        write_log(true,
          "[OpenOFC MODE] ACTIVE tablemap=\"%s\" contract=%d formula_bypassed=1 "
          "holdem_engines_bypassed=1 holdem_validator_bypassed=1\n",
          current_tablemap.GetString(), openofc_contract);
      } else {
        write_log(k_always_log_errors,
          "[OpenOFC CONTRACT] BLOCKED tablemap=\"%s\" expected=%d got=%d "
          "autoplayer_blocked=1 legacy_holdem_fallback=0\n",
          current_tablemap.GetString(), kOpenOFCContractVersion,
          openofc_contract);
      }
      last_logged_tablemap = current_tablemap;
      last_logged_contract = openofc_contract;
    }
  } else {
    // Legacy OpenHoldem path, unchanged for non-OFC tablemaps.
    // We must not check if the scrape of the table changed, because:
    //   * some symbol-engines must be evaluated no matter what
    //   * we might need to act (sitout, ...) on empty/non-changing tables
    //   * auto-player needs stable frames too
    p_engine_container->EvaluateAll();
  }

	// Reply-frames no longer here in the heartbeat.
  // we have a "ReplayFrameController for that.
  LeaveCriticalSection(&pParent->cs_update_in_progress);
	p_openholdem_title->UpdateTitle();

	////////////////////////////////////////////////////////////////////////////////////////////
	// The legacy ScraperOutput dialog is a Hold'em view (SABDP, two hole cards,
	// bets/balances/community cards). Updating it in OpenOFC mode creates a
	// misleading empty display, so it is intentionally suppressed until the
	// dedicated OFC inspector replaces it.
	if (!openofc_mode && m_ScraperOutputDlg) {
		m_ScraperOutputDlg->UpdateDisplay();
	}
  
	////////////////////////////////////////////////////////////////////////////////////////////
	// OH-Validator validates Hold'em invariants. It must never veto or mutate an
	// OFC heartbeat; OFC validity is enforced by COFCScraper/COFCReconstructor.
	if (!openofc_mode) {
		write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] Calling Validator.\n");
    p_validator->Validate();
  }

	////////////////////////////////////////////////////////////////////////////////////////////
	// Autoplayer
	write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] autoplayer_engaged(): %s\n", 
		Bool2CString(p_autoplayer->autoplayer_engaged()));
  if (!openofc_mode) {
	  write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] p_engine_container->symbol_engine_userchair()->userchair()_confirmed(): %s\n", 
		  Bool2CString(p_engine_container->symbol_engine_userchair()->userchair_confirmed()));
  }
	// In OpenOFC the dedicated CAutoplayer branch invokes COFCRuntimeController
	// directly and never evaluates an OpenPPL betting formula. A stale or
	// unversioned OFC TableMap remains in OpenOFC isolation but is hard-blocked
	// from physical input, so it can never fall back to Hold'em action semantics.
	if (p_autoplayer->autoplayer_engaged()) {
    if (openofc_mode && !openofc_contract_ok) {
      write_log(k_always_log_errors,
        "[OpenOFC CONTRACT] Autoplayer suppressed until TableMap contract=%d\n",
        kOpenOFCContractVersion);
    } else {
		  write_log(Preferences()->debug_heartbeat(), "[HeartBeatThread] Calling DoAutoplayer.\n");
		  p_autoplayer->DoAutoplayer();
    }
	}
}

void CHeartbeatThread::AutoConnect() {
  write_log(Preferences()->debug_alltherest(), "[CHeartbeatThread] location Johnny_D\n");
	assert(!p_autoconnector->IsConnectedToAnything());
	if (Preferences()->autoconnector_when_to_connect() == k_AutoConnector_Connect_Permanent) {
		if (p_autoconnector->SecondsSinceLastFailedAttemptToConnect() > 1 /* seconds */) {
			write_log(Preferences()->debug_autoconnector(), "[CHeartbeatThread] going to call Connect()\n");
			p_autoconnector->Connect(NULL);
		}	else {
			write_log(Preferences()->debug_autoconnector(), "[CHeartbeatThread] Reconnection blocked. Other instance failed previously.\n");
		}
	}
}
