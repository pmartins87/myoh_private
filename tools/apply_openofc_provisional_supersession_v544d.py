from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path, text, eol, bom):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel, old, new, label):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: {label}")


def patch_orchestrator_supersession():
    rel = "OpenHoldem/COFCTurnOrchestrator.h"
    old = '''  bool AdvanceAfterFreshScrape(
      const COFCState &fresh_state,
      const COFCVisualObservation &fresh_observation,
      int duration_ms,
      bool *placements_complete,
      bool *ready_for_confirm,
      std::string *error);

  bool active() const { return active_; }
'''
    new = '''  bool AdvanceAfterFreshScrape(
      const COFCState &fresh_state,
      const COFCVisualObservation &fresh_observation,
      int duration_ms,
      bool *placements_complete,
      bool *ready_for_confirm,
      std::string *error);

  // A dealer-side provisional solution may become strategically obsolete at
  // the instant the opponent's final placements are revealed. This method is
  // called only on a fresh scrape. It first certifies any drag that was already
  // sent, then releases the old fixed plan without treating new information as
  // an automation fault. Runtime may then solve again from the fresh state.
  bool SupersedeProvisionalPlanAfterFreshScrape(
      const COFCState &fresh_state,
      std::string *error);

  bool active() const { return active_; }
'''
    replace_once(rel, old, new, "declare provisional supersession")

    rel = "OpenHoldem/COFCTurnOrchestrator.cpp"
    anchor = '''bool COFCTurnOrchestrator::AdvanceAfterFreshScrape(
'''
    path, text, eol, bom = read_source(rel)
    if text.count(anchor) != 1:
        raise RuntimeError("provisional supersession cpp anchor is not unique")
    method = r'''bool COFCTurnOrchestrator::SupersedeProvisionalPlanAfterFreshScrape(
    const COFCState &fresh_state,
    string *error) {
  if (error != NULL) error->clear();
  if (blocked()) {
    if (error != NULL) *error =
      "turn orchestrator is blocked; provisional plan cannot be superseded";
    return false;
  }
  if (!fresh_state.valid) {
    if (error != NULL) *error =
      "fresh canonical state is invalid during provisional supersession";
    return false;
  }

  // The opponent can finish while one Hero drag is in flight. New strategic
  // information must not erase the transaction boundary: certify that already
  // attempted movement from the fresh scrape before dropping the old plan.
  if (placement_executor_.awaiting_verification()) {
    string verify_error;
    if (!placement_executor_.VerifyAfterFreshScrape(
          fresh_state, &verify_error)) {
      return FailAndBlock(error,
        "in-flight provisional drag could not be certified before replan: "
        + verify_error);
    }
  }

  active_ = false;
  baseline_.Reset();
  plan_.Reset();
  placement_executor_.ResetForKnownNewHand();
  int pending_now = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i)
    if (fresh_state.pending[i].active) ++pending_now;
  write_log(true,
    "[OpenOFC PROVISIONAL] old_plan_superseded=1 reason=OPPONENT_FINAL_INFO "
    "round=%d pending_now=%d replan=REQUIRED\n",
    fresh_state.round_index, pending_now);
  return true;
}

'''
    text = text.replace(anchor, method + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: implement provisional supersession")


def patch_runtime_replan_edge():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    old = '''  bool complete = false;
  bool ready = false;
  string error;
  const int duration = max(100,
'''
    new = '''  // OPENOFC_PROVISIONAL_SUPERSESSION_V544D: opponent final reveal is
  // expected strategic state drift, not corruption. If one provisional drag is
  // still unobserved, the wait fence above returns before this point. Once its
  // result is visible (or no drag is outstanding), certify it, abandon the old
  // provisional plan and re-solve from the complete opponent information.
  if (provisional_ && state.decision_finalizable) {
    string replan_error;
    if (!orchestrator_.SupersedeProvisionalPlanAfterFreshScrape(
          state, &replan_error)) {
      Recover("provisional plan supersession failed: " + replan_error);
      return false;
    }
    plan_.Reset();
    pending_before_drag_ = PendingCount(state);
    pending_signature_before_drag_ = PendingSignature(state);
    drag_wait_cycles_ = 0;
    drag_retry_count_ = 0;
    provisional_ = false;
    phase_ = kIdle;
    ArmDecisionStabilization(state, "OPPONENT_FINAL_INFO_REPLAN");
    write_log(true,
      "[OpenOFC PROVISIONAL] final_info_arrived_mid_arrangement=1 "
      "old_plan=ABANDONED final_replan=ARMED round=%d\\n",
      state.round_index);
    return true;
  }

  bool complete = false;
  bool ready = false;
  string error;
  const int duration = max(100,
'''
    # StartDecision contains a similar local-variable shape, so operate only on
    # the AdvanceArrangement function body.
    path, text, eol, bom = read_source(rel)
    fn_start = text.find("bool COFCRuntimeController::AdvanceArrangement(")
    if fn_start < 0:
        raise RuntimeError("AdvanceArrangement function missing")
    fn_end = text.find("\nbool COFCRuntimeController::HandlePostConfirm(", fn_start)
    if fn_end < 0:
        raise RuntimeError("AdvanceArrangement terminal boundary missing")
    body = text[fn_start:fn_end]
    if body.count(old) != 1:
        raise RuntimeError(
          f"AdvanceArrangement provisional replan anchor expected 1, got {body.count(old)}")
    body = body.replace(old, new, 1)
    text = text[:fn_start] + body + text[fn_end:]
    write_source(path, text, eol, bom)
    print(f"patched {rel}: replan when final info supersedes provisional plan")


def assert_contract():
    _, orch_h, _, _ = read_source("OpenHoldem/COFCTurnOrchestrator.h")
    _, orch_cpp, _, _ = read_source("OpenHoldem/COFCTurnOrchestrator.cpp")
    _, runtime, _, _ = read_source("OpenHoldem/COFCRuntimeController.cpp")
    required = [
        (orch_h, "SupersedeProvisionalPlanAfterFreshScrape"),
        (orch_cpp, "in-flight provisional drag could not be certified before replan"),
        (runtime, "OPPONENT_FINAL_INFO_REPLAN"),
        (runtime, "final_info_arrived_mid_arrangement=1"),
        (runtime, 'Recover("provisional plan supersession failed: " + replan_error)'),
    ]
    for text, token in required:
        if token not in text:
            raise RuntimeError(f"provisional supersession contract missing: {token}")
    if 'Block("provisional plan supersession failed:' in runtime:
        raise RuntimeError("absorbing Block survived provisional replan path")
    print("OpenOFC v5.4.4D provisional supersession source contract: PASS")


def main():
    patch_orchestrator_supersession()
    patch_runtime_replan_edge()
    assert_contract()
    print("OpenOFC v5.4.4D provisional supersession patch applied successfully")


if __name__ == "__main__":
    main()
