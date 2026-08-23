from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "apply_openofc_identity_refinement_v544e.py"


def main():
    raw = PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    old_cpp = '''    plan_.Reset();
    pending_before_drag_ = PendingCount(state);
'''
    new_cpp = '''    const int old_unknown = UnknownIncomingCount(plan_.decision_state);
    plan_.Reset();
    pending_before_drag_ = PendingCount(state);
'''
    if text.count(old_cpp) == 1:
        text = text.replace(old_cpp, new_cpp, 1)
    elif text.count(new_cpp) != 1:
        raise RuntimeError("v5.4.4EA could not preserve old UNKNOWN count before plan reset")

    old_log = '''      UnknownIncomingCount(plan_.decision_state), UnknownIncomingCount(state));
'''
    new_log = '''      old_unknown, UnknownIncomingCount(state));
'''
    if text.count(old_log) == 1:
        text = text.replace(old_log, new_log, 1)
    elif text.count(new_log) != 1:
        raise RuntimeError("v5.4.4EA could not fix identity-refinement log")

    obsolete = '''    # Preserve old_unknown for logging before Reset().
    identity_block = identity_block.replace(
        '    plan_.Reset();\\n',
        '    const int old_unknown = UnknownIncomingCount(plan_.decision_state);\\n    plan_.Reset();\\n')
    identity_block = identity_block.replace(
        '      UnknownIncomingCount(plan_.decision_state), UnknownIncomingCount(state));',
        '      old_unknown, UnknownIncomingCount(state));')
'''
    if text.count(obsolete) == 1:
        text = text.replace(obsolete, "", 1)
    elif "# Preserve old_unknown for logging before Reset()." in text:
        raise RuntimeError("v5.4.4EA obsolete runtime postprocessor shape changed")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    PATH.write_bytes(data)
    print("OpenOFC v5.4.4EA identity-refinement hardening: PASS")


if __name__ == "__main__":
    main()
