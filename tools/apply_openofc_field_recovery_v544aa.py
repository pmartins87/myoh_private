from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V544_PATH = ROOT / "tools" / "apply_openofc_field_recovery_v544.py"


def main():
    raw = V544_PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    # The v5.4.4 runtime patch originally staged the stabilization methods only
    # in its in-memory `text`, then called regex_once(), which re-read the file
    # from disk before those staged changes had been persisted. The subsequent
    # re-read therefore discarded ArmDecisionStabilization(),
    # DecisionStabilized(), and the TableMap timing symbol. Persist that staged
    # source before the post-Confirm regex patch so both edits compose.
    regex_call = '''    regex_once(rel, pattern, replacement, "post-Confirm round edge stabilization")
    path, text, eol, bom = read_source(rel)
'''
    regex_fixed = '''    write_source(path, text, eol, bom)
    regex_once(rel, pattern, replacement, "post-Confirm round edge stabilization")
    path, text, eol, bom = read_source(rel)
'''
    if text.count(regex_call) == 1:
        text = text.replace(regex_call, regex_fixed, 1)
    elif text.count(regex_fixed) != 1:
        raise RuntimeError("v5.4.4AA could not persist stabilization source before regex patch")

    # Keep every continuation line of the generated C++ header annotation a
    # real comment. The previous generator emitted two bare English lines in
    # class scope, which MSVC correctly parsed as invalid declarations.
    bad_comment = '''        + "  // OPENOFC_ROUND_STABILIZATION_V544: no drag is emitted until the\\n"
          "  Hero semantic fingerprint has remained unchanged for the configured\\n"
          "  post-deal animation interval.\\n"
'''
    good_comment = '''        + "  // OPENOFC_ROUND_STABILIZATION_V544: no drag is emitted until the\\n"
          "  // Hero semantic fingerprint has remained unchanged for the configured\\n"
          "  // post-deal animation interval.\\n"
'''
    if text.count(bad_comment) == 1:
        text = text.replace(bad_comment, good_comment, 1)
    elif text.count(good_comment) != 1:
        raise RuntimeError("v5.4.4AA stabilization header-comment shape is unknown")

    old = r"""    # New hand edge in Tick.
    old = '''    ResetForKnownNewHand(state);
    g_openofc_flow_phase = kOpenOFCFlowRoundActive;
'''
    if text.count(old) != 1:
        raise RuntimeError("Tick known-new-hand block missing")
    text = text.replace(
        old,
        '''    ResetForKnownNewHand(state);
    ArmDecisionStabilization(state, "NEW_HAND_EDGE");
    g_openofc_flow_phase = kOpenOFCFlowRoundActive;
''',
        1)
"""

    new = r'''    # New-hand resets exist in more than one Tick path after v4.4 and
    # v5.4.3H (ordinary recovery edge plus post-Confirm/Fantasy edge). They are
    # semantically equivalent for the first-drag stabilization fence. Scope the
    # insertion to Tick and arm after every reset there instead of relying on a
    # formatting-specific Reset+flow-marker adjacency.
    tick_start = text.find("void COFCRuntimeController::Tick(")
    if tick_start < 0:
        raise RuntimeError("Tick function missing for new-hand stabilization")
    tick_body = text[tick_start:]
    reset_call = "        ResetForKnownNewHand(state);\n"
    reset_call_shallow = "    ResetForKnownNewHand(state);\n"
    total_resets = tick_body.count(reset_call) + tick_body.count(reset_call_shallow)
    if total_resets < 1:
        raise RuntimeError("Tick has no known-new-hand reset to stabilize")
    tick_body = tick_body.replace(
        reset_call,
        reset_call
        + "        ArmDecisionStabilization(state, \"NEW_HAND_EDGE\");\n")
    tick_body = tick_body.replace(
        reset_call_shallow,
        reset_call_shallow
        + "    ArmDecisionStabilization(state, \"NEW_HAND_EDGE\");\n")
    text = text[:tick_start] + tick_body
'''

    count = text.count(old)
    if count == 1:
        text = text.replace(old, new, 1)
    elif text.count(new) != 1:
        raise RuntimeError(
            f"v5.4.4AA could not replace brittle Tick new-hand patch; old_count={count}")

    # Source-contract spelling must match the runtime log marker exactly.
    # The implementation writes "[OpenOFC STABILIZE]"; the original assertion
    # accidentally required uppercase "OPENOFC", creating a false-negative CI.
    wrong_marker = '            "OPENOFC STABILIZE",\n'
    right_marker = '            "OpenOFC STABILIZE",\n'
    if text.count(wrong_marker) == 1:
        text = text.replace(wrong_marker, right_marker, 1)
    elif text.count(right_marker) != 1:
        raise RuntimeError("v5.4.4AA stabilization contract marker shape is unknown")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    V544_PATH.write_bytes(data)

    # v5.4.4E is itself a source-generating patch. Harden that generator in the
    # same ephemeral materialization workspace before it is executed later in
    # the chain. This keeps the actual C++ payload deterministic and avoids
    # source-shape/runtime-API regressions in the identity-refinement path.
    from apply_openofc_identity_refinement_v544ea import main as harden_v544e
    harden_v544e()

    print("OpenOFC v5.4.4AA runtime/identity-refinement hardening: PASS")


if __name__ == "__main__":
    main()
