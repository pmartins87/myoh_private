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


def replace_once(rel: str, old: str, new: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{rel}: expected one target, got {count}: {old[:180]!r}"
        )
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_runtime_controller() -> None:
    rel = "OpenHoldem/COFCRuntimeController.cpp"

    replace_once(
        rel,
        '#include "COFCRuntimeController.h"\n',
        '#include "COFCRuntimeController.h"\n#include "COFCRecoveryLiveness.h"\n',
    )

    old = r'''  if (phase_ == kReacquire) {
    if (!state.valid || !observation.valid) {
      write_log(true,
        "[OpenOFC REACQUIRE] result=WAIT reason=INVALID_PERCEPTION terminal=0 continue_scraping=1\n");
      return;
    }
    const string now = StateFingerprint(state);
    const bool hero_state_changed = now != recovery_fingerprint_;
    if (!hero_state_changed && recovery_requires_change_) {
      write_log(true,
        "[OpenOFC REACQUIRE] result=WAIT reason=SAME_HERO_TRANSACTION_STATE terminal=0 duplicate_input_suppressed=1\n");
      return;
    }
    if (!hero_state_changed) {
      ++reacquire_stable_cycles_;
      if (reacquire_stable_cycles_ < 2) {
        write_log(true,
          "[OpenOFC REACQUIRE] result=WAIT stable=%d/2 reason=SAFE_RETRY_DEBOUNCE terminal=0\n",
          reacquire_stable_cycles_);
        return;
      }
    }

    orchestrator_.ResetForKnownNewHand();
    fantasy_executor_.Reset();
    plan_.Reset();
    confirm_before_.Reset();
    provisional_ = false;
    phase_ = kIdle;
    recovery_fingerprint_.clear();
    reacquire_stable_cycles_ = 0;
    recovery_requires_change_ = false;
    write_log(k_always_log_errors,
      "[OpenOFC REACQUIRE_ACCEPT] source=RUNTIME_CONTROLLER hero_state_changed=%d next=IDLE terminal=0\n",
      hero_state_changed ? 1 : 0);
  }'''

    new = r'''  if (phase_ == kReacquire) {
    // OPENOFC_BOUNDED_SAME_STATE_RETRY_V543D.  Recovery is a transient
    // observation phase, never an absorbing state.  Even when a drag/Confirm
    // may already have been dispatched, a valid unchanged Hero state receives
    // only a bounded debounce window.  Persistence through that window is
    // evidence that the action was not observed, so a fresh re-plan/retry is
    // authorized instead of waiting for a new hand forever.
    const bool perception_valid = state.valid && observation.valid;
    const string now = perception_valid ? StateFingerprint(state) : string();
    const bool hero_state_changed =
      perception_valid && now != recovery_fingerprint_;
    const COFCRecoveryLivenessDecision recovery =
      EvaluateOFCRecoveryLiveness(
        perception_valid,
        hero_state_changed,
        recovery_requires_change_,
        reacquire_stable_cycles_);
    reacquire_stable_cycles_ = recovery.stable_cycles;

    if (!recovery.release) {
      if (recovery.reason == kOFCRecoveryWaitInvalidPerception) {
        write_log(true,
          "[OpenOFC REACQUIRE] result=WAIT reason=%s terminal=0 continue_scraping=1 stable=%d\n",
          OFCRecoveryLivenessReasonLabel(recovery.reason),
          reacquire_stable_cycles_);
      } else {
        write_log(true,
          "[OpenOFC REACQUIRE] result=WAIT reason=%s terminal=0 duplicate_input_suppressed=1 stable=%d/%d continue_scraping=1\n",
          OFCRecoveryLivenessReasonLabel(recovery.reason),
          reacquire_stable_cycles_, recovery.required_cycles);
      }
      return;
    }

    const bool same_state_timeout =
      recovery.reason == kOFCRecoveryReleaseSameStateTimeout;
    if (same_state_timeout) {
      write_log(k_always_log_errors,
        "[OpenOFC REACQUIRE_TIMEOUT] hero_state_changed=0 stable=%d/%d terminal=0 action=FRESH_REPLAN retry_authorized=1 continue_scraping=1\n",
        recovery.stable_cycles, recovery.required_cycles);
    }

    orchestrator_.ResetForKnownNewHand();
    fantasy_executor_.Reset();
    plan_.Reset();
    confirm_before_.Reset();
    provisional_ = false;
    phase_ = kIdle;
    recovery_fingerprint_.clear();
    reacquire_stable_cycles_ = 0;
    recovery_requires_change_ = false;
    write_log(k_always_log_errors,
      "[OpenOFC REACQUIRE_ACCEPT] source=RUNTIME_CONTROLLER reason=%s hero_state_changed=%d same_state_retry=%d next=IDLE terminal=0\n",
      OFCRecoveryLivenessReasonLabel(recovery.reason),
      hero_state_changed ? 1 : 0,
      same_state_timeout ? 1 : 0);
  }'''

    replace_once(rel, old, new)


def assert_contract() -> None:
    _path, runtime, _eol, _bom = read_source(
        "OpenHoldem/COFCRuntimeController.cpp"
    )
    required = (
        "COFCRecoveryLiveness.h",
        "OPENOFC_BOUNDED_SAME_STATE_RETRY_V543D",
        "EvaluateOFCRecoveryLiveness",
        "[OpenOFC REACQUIRE_TIMEOUT]",
        "retry_authorized=1",
        "continue_scraping=1",
    )
    missing = [needle for needle in required if needle not in runtime]
    if missing:
        raise RuntimeError(
            "bounded recovery contract missing: " + ", ".join(missing)
        )

    forbidden = (
        "reason=SAME_HERO_TRANSACTION_STATE",
        "RUNTIME_BLOCKED",
        "AUTOMATION BLOCKED until a known new hand",
    )
    survived = [needle for needle in forbidden if needle in runtime]
    if survived:
        raise RuntimeError(
            "absorbing recovery sentinel survived v5.4.3D: "
            + ", ".join(survived)
        )

    print(
        "PASS: runtime faults remain nonterminal; same valid Hero state has a "
        "bounded 8-observation post-dispatch debounce and then fresh re-plan"
    )


def main() -> None:
    patch_runtime_controller()
    assert_contract()
    print("OpenOFC v5.4.3D bounded recovery patch applied successfully")


if __name__ == "__main__":
    main()
