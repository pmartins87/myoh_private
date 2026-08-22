from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V544_PATH = ROOT / "tools" / "apply_openofc_field_recovery_v544.py"


def main():
    raw = V544_PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

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

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    V544_PATH.write_bytes(data)
    print("OpenOFC v5.4.4AA Tick new-hand stabilization hardening: PASS")


if __name__ == "__main__":
    main()
