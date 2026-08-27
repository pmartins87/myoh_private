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


def patch_reconstructor_identity_refinement():
    rel = "OpenHoldem/COFCReconstructor.cpp"
    path, text, eol, bom = read_source(rel)

    # Remove the old executor-driven behavior that deliberately converted a
    # newly recognized card back to UNKNOWN merely to keep an in-flight plan
    # stable. Perception is monotonic: when identity becomes known, keep it.
    helper_start = "bool ReplaceOneCurrentKnownWithUnknown(\n"
    helper_end = "void RepairSameRoundIncomingIdentity(\n"
    hs = text.find(helper_start)
    he = text.find(helper_end, hs)
    if hs >= 0:
        if he < 0:
            raise RuntimeError("identity refinement: obsolete helper terminal missing")
        text = text[:hs] + text[he:]
    elif "preserve=CURRENT_INCOMING_UNKNOWN" in text:
        raise RuntimeError("identity refinement: obsolete UNKNOWN preservation helper shape changed")

    old_branch = '''  } else if (previous_unknown == 1 && current_unknown == 0) {
    // Once a genuinely new later-round card was unread, the policy treats that
    // physical card as the safe unused card for the rest of this fixed turn.
    // If a later bitmap happens to classify it, preserve the semantic UNKNOWN
    // token so an in-flight plan cannot drift/re-solve around the same object.
    const set<int> extra = Difference(current_known, previous_known);
    if (extra.size() == 1) {
      ReplaceOneCurrentKnownWithUnknown(observation, *extra.begin());
#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
      write_log(true,
        "[OpenOFC UNKNOWN] preserve=CURRENT_INCOMING_UNKNOWN newly_read_value=%d\\n",
        *extra.begin());
#endif
    }
  }
'''
    new_branch = '''  } else if (previous_unknown == 1 && current_unknown == 0) {
    // OPENOFC_IDENTITY_REFINEMENT_V544E: newly recognized identity is stronger
    // information than the earlier UNKNOWN token. Preserve the new identity;
    // runtime will supersede any strategy plan that was based on less information.
    const set<int> extra = Difference(current_known, previous_known);
#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
    if (extra.size() == 1) {
      write_log(true,
        "[OpenOFC UNKNOWN] refinement=ACCEPTED newly_read_value=%d replan=REQUIRED\\n",
        *extra.begin());
    }
#endif
  }
'''
    if text.count(old_branch) != 1:
        raise RuntimeError(
            f"identity refinement: old same-round UNKNOWN preservation branch expected 1, got {text.count(old_branch)}")
    text = text.replace(old_branch, new_branch, 1)

    old_same_round = '''  if (previous != NULL && previous->valid
      && observation.round_index == previous->round_index) {
    const set<int> old_incoming = CardArraySet(
      previous->hero_incoming, previous->hero_incoming_count);
    const int old_unknown = UnknownCount(
      previous->hero_incoming, previous->hero_incoming_count);
    if (old_incoming != current_incoming || old_unknown != current_unknown) {
      return Fail(out, error,
        "same-round incoming physical set changed outside UNKNOWN lineage repair");
    }
  }
'''
    new_same_round = '''  if (previous != NULL && previous->valid
      && observation.round_index == previous->round_index) {
    const set<int> old_incoming = CardArraySet(
      previous->hero_incoming, previous->hero_incoming_count);
    const int old_unknown = UnknownCount(
      previous->hero_incoming, previous->hero_incoming_count);
    if (old_incoming != current_incoming || old_unknown != current_unknown) {
      const set<int> missing_old = Difference(old_incoming, current_incoming);
      const set<int> newly_known = Difference(current_incoming, old_incoming);
      const int resolved_unknown = old_unknown - current_unknown;
      // Identity may improve monotonically: every UNKNOWN that disappears must
      // be replaced by exactly one newly known physical identity, and no prior
      // known identity may disappear. A regression known->UNKNOWN still retries.
      if (resolved_unknown <= 0
          || !missing_old.empty()
          || static_cast<int>(newly_known.size()) != resolved_unknown) {
        return Fail(out, error,
          "same-round incoming physical set changed outside monotonic identity refinement");
      }
    }
  }
'''
    if text.count(old_same_round) != 1:
        raise RuntimeError(
            f"identity refinement: same-round incoming guard expected 1, got {text.count(old_same_round)}")
    text = text.replace(old_same_round, new_same_round, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}: monotonic UNKNOWN -> known identity refinement")


def patch_generic_plan_supersession():
    rel = "OpenHoldem/COFCTurnOrchestrator.h"
    old = '''  bool SupersedeProvisionalPlanAfterFreshScrape(
      const COFCState &fresh_state,
      std::string *error);

  bool active() const { return active_; }
'''
    new = '''  bool SupersedeActivePlanAfterFreshScrape(
      const COFCState &fresh_state,
      const char *reason,
      std::string *error);
  bool SupersedeProvisionalPlanAfterFreshScrape(
      const COFCState &fresh_state,
      std::string *error);

  bool active() const { return active_; }
'''
    replace_once(rel, old, new, "declare generic active-plan supersession")

    rel = "OpenHoldem/COFCTurnOrchestrator.cpp"
    path, text, eol, bom = read_source(rel)
    start = text.find("bool COFCTurnOrchestrator::SupersedeProvisionalPlanAfterFreshScrape(\n")
    end = text.find("\nbool COFCTurnOrchestrator::AdvanceAfterFreshScrape(\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("identity refinement: provisional supersession method bounds missing")
    old_method = text[start:end]
    if "reason=OPPONENT_FINAL_INFO" not in old_method:
        raise RuntimeError("identity refinement: provisional supersession log contract changed")

    generic = r'''bool COFCTurnOrchestrator::SupersedeActivePlanAfterFreshScrape(
    const COFCState &fresh_state,
    const char *reason,
    string *error) {
  if (error != NULL) error->clear();
  if (blocked()) {
    if (error != NULL) *error =
      "turn orchestrator is blocked; active plan cannot be superseded";
    return false;
  }
  if (!fresh_state.valid) {
    if (error != NULL) *error =
      "fresh canonical state is invalid during plan supersession";
    return false;
  }

  // A semantic replan may arrive while one Hero drag is in flight. Certify the
  // already-sent physical transaction first; only then release the old solver
  // plan. Strategy changes never erase physical transaction boundaries.
  if (placement_executor_.awaiting_verification()) {
    string verify_error;
    if (!placement_executor_.VerifyAfterFreshScrape(
          fresh_state, &verify_error)) {
      return FailAndBlock(error,
        "in-flight drag could not be certified before semantic replan: "
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
    "[OpenOFC REPLAN] old_plan_superseded=1 reason=%s round=%d pending_now=%d replan=REQUIRED\n",
    reason == NULL ? "UNSPECIFIED" : reason,
    fresh_state.round_index, pending_now);
  return true;
}

bool COFCTurnOrchestrator::SupersedeProvisionalPlanAfterFreshScrape(
    const COFCState &fresh_state,
    string *error) {
  return SupersedeActivePlanAfterFreshScrape(
    fresh_state, "OPPONENT_FINAL_INFO", error);
}
'''
    text = text[:start] + generic + text[end:]
    write_source(path, text, eol, bom)
    print(f"patched {rel}: generic semantic plan supersession")


def patch_runtime_identity_replan():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)
    fn_start = text.find("bool COFCRuntimeController::AdvanceArrangement(\n")
    fn_end = text.find("\nbool COFCRuntimeController::HandlePostConfirm(\n", fn_start)
    if fn_start < 0 or fn_end < 0:
        raise RuntimeError("identity refinement: AdvanceArrangement bounds missing")
    body = text[fn_start:fn_end]

    anchor = '''  bool complete = false;
  bool ready = false;
  string error;
'''
    if body.count(anchor) != 1:
        raise RuntimeError(
            f"identity refinement: AdvanceArrangement final continuation anchor expected 1, got {body.count(anchor)}")
    identity_block = r'''  // OPENOFC_IDENTITY_REFINEMENT_V544E: a card that was previously
  // UNKNOWN may become readable while this decision is still being arranged.
  // That is new strategic information, not state corruption. The reconstructor
  // has already certified that the change is monotonic UNKNOWN->known.
  if (plan_.valid
      && state.round_index == plan_.decision_state.round_index
      && state.hero_incoming_count == plan_.decision_state.hero_incoming_count
      && UnknownIncomingCount(plan_.decision_state) > UnknownIncomingCount(state)) {
    string refinement_error;
    if (!orchestrator_.SupersedeActivePlanAfterFreshScrape(
          state, "INCOMING_IDENTITY_REFINED", &refinement_error)) {
      Block("identity-refinement plan supersession failed: " + refinement_error);
      return false;
    }
    plan_.Reset();
    pending_before_drag_ = PendingCount(state);
    pending_signature_before_drag_ = PendingSignature(state);
    drag_wait_cycles_ = 0;
    drag_retry_count_ = 0;
    provisional_ = false;
    phase_ = kIdle;
    ArmDecisionStabilization(state, "INCOMING_IDENTITY_REFINED");
    write_log(true,
      "[OpenOFC REPLAN] reason=INCOMING_IDENTITY_REFINED old_unknown=%d new_unknown=%d strategy=RECOMPUTE_FROM_FRESH_STATE\n",
      UnknownIncomingCount(plan_.decision_state), UnknownIncomingCount(state));
    return true;
  }

'''
    # Preserve old_unknown for logging before Reset().
    identity_block = identity_block.replace(
        '    plan_.Reset();\n',
        '    const int old_unknown = UnknownIncomingCount(plan_.decision_state);\n    plan_.Reset();\n')
    identity_block = identity_block.replace(
        '      UnknownIncomingCount(plan_.decision_state), UnknownIncomingCount(state));',
        '      old_unknown, UnknownIncomingCount(state));')
    body = body.replace(anchor, identity_block + anchor, 1)
    text = text[:fn_start] + body + text[fn_end:]
    write_source(path, text, eol, bom)
    print(f"patched {rel}: replan on monotonic incoming identity refinement")


def patch_selftest():
    rel = "OpenHoldem/COFCUnknownToleranceSelftest.cpp"
    path, text, eol, bom = read_source(rel)
    anchor = "bool UnknownUnusedDoesNotBlockNextRound(const COFCState &round1) {\n"
    if text.count(anchor) != 1:
        raise RuntimeError("identity refinement selftest anchor missing")
    test = r'''bool PreviouslyUnknownIdentityCanRefine(const COFCState &round1) {
  COFCVisualObservation obs;
  InitPlayers(&obs, 1);
  PutOpeningBoard(&obs.players[1].visual_board);
  PutLoose(&obs, 0, 5);
  PutLoose(&obs, 1, 6);
  PutLoose(&obs, 2, 7);
  obs.hero_loose_count = 3;

  COFCState refined;
  std::string error;
  if (!Require(COFCReconstructor::Reconstruct(obs, &round1, &refined, &error),
        "same-round UNKNOWN must be allowed to refine into a newly recognized card")) {
    std::cerr << error << "\n";
    return false;
  }
  if (!Require(refined.valid && refined.hero_incoming_count == 3
        && UnknownIncoming(refined) == 0,
        "identity refinement must keep the newly known identity instead of restoring UNKNOWN")) {
    return false;
  }
  bool found7 = false;
  for (int i = 0; i < refined.hero_incoming_count; ++i)
    if (refined.hero_incoming[i].value == 7) found7 = true;
  if (!Require(found7, "refined canonical incoming set contains the newly read card"))
    return false;

  COFCStrategyAction action;
  if (!Require(COFCBaselinePolicy::Choose(refined, &action, &error),
        "refined all-known state must be solved from complete information")) {
    std::cerr << error << "\n";
    return false;
  }
  return Require(action.valid && action.unused_count == 1
      && action.unused_cards[0] != kOFCCardUnknown,
      "refined strategy must no longer be constrained to UNKNOWN as discard");
}

'''
    text = text.replace(anchor, test + anchor, 1)

    old_main = '''  if (!TransientSameRoundUnknownRecoversIdentity()) return 1;
  if (!UnknownUnusedDoesNotBlockNextRound(r1)) return 1;
'''
    new_main = '''  if (!TransientSameRoundUnknownRecoversIdentity()) return 1;
  if (!PreviouslyUnknownIdentityCanRefine(r1)) return 1;
  if (!UnknownUnusedDoesNotBlockNextRound(r1)) return 1;
'''
    if text.count(old_main) != 1:
        raise RuntimeError("identity refinement selftest main anchor missing")
    text = text.replace(old_main, new_main, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}: add monotonic identity-refinement regression")


def assert_contract():
    checks = {
        "OpenHoldem/COFCReconstructor.cpp": [
            "OPENOFC_IDENTITY_REFINEMENT_V544E",
            "monotonic identity refinement",
            "refinement=ACCEPTED",
        ],
        "OpenHoldem/COFCTurnOrchestrator.cpp": [
            "SupersedeActivePlanAfterFreshScrape",
            "INCOMING_IDENTITY_REFINED" if False else "old_plan_superseded=1 reason=%s",
        ],
        "OpenHoldem/COFCRuntimeController.cpp": [
            "OPENOFC_IDENTITY_REFINEMENT_V544E",
            "INCOMING_IDENTITY_REFINED",
            "strategy=RECOMPUTE_FROM_FRESH_STATE",
        ],
    }
    for rel, tokens in checks.items():
        _, text, _, _ = read_source(rel)
        for token in tokens:
            if token not in text:
                raise RuntimeError(f"identity-refinement contract missing {token} in {rel}")
    _, recon, _, _ = read_source("OpenHoldem/COFCReconstructor.cpp")
    if "preserve=CURRENT_INCOMING_UNKNOWN" in recon:
        raise RuntimeError("obsolete executor-driven UNKNOWN preservation survived")
    if "ReplaceOneCurrentKnownWithUnknown" in recon:
        raise RuntimeError("obsolete known->UNKNOWN downgrade helper survived")
    print("OpenOFC v5.4.4E identity-refinement source contract: PASS")


def main():
    patch_reconstructor_identity_refinement()
    patch_generic_plan_supersession()
    patch_runtime_identity_replan()
    patch_selftest()
    assert_contract()
    print("OpenOFC v5.4.4E monotonic identity refinement patch applied successfully")


if __name__ == "__main__":
    main()
