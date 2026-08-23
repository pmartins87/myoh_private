from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def scan_cpp_delimiters(text: str):
    """Return unmatched lexical delimiters, ignoring comments/quoted literals."""
    stack = []
    state = "code"
    i = 0
    line = 1
    col = 1
    pairs = {"}": "{", ")": "(", "]": "["}
    opening = set("{([")

    def advance(ch):
        nonlocal line, col
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if state == "line_comment":
            advance(ch)
            i += 1
            if ch == "\n":
                state = "code"
            continue
        if state == "block_comment":
            if ch == "*" and nxt == "/":
                advance(ch); advance(nxt); i += 2; state = "code"
            else:
                advance(ch); i += 1
            continue
        if state == "string":
            if ch == "\\" and nxt:
                advance(ch); advance(nxt); i += 2
            else:
                advance(ch); i += 1
                if ch == '"': state = "code"
            continue
        if state == "char":
            if ch == "\\" and nxt:
                advance(ch); advance(nxt); i += 2
            else:
                advance(ch); i += 1
                if ch == "'": state = "code"
            continue

        if ch == "/" and nxt == "/":
            advance(ch); advance(nxt); i += 2; state = "line_comment"; continue
        if ch == "/" and nxt == "*":
            advance(ch); advance(nxt); i += 2; state = "block_comment"; continue
        if ch == '"':
            advance(ch); i += 1; state = "string"; continue
        if ch == "'":
            advance(ch); i += 1; state = "char"; continue

        if ch in opening:
            stack.append((ch, line, col))
        elif ch in pairs:
            if not stack or stack[-1][0] != pairs[ch]:
                return stack, state, (ch, line, col)
            stack.pop()
        advance(ch)
        i += 1

    return stack, state, None


def diagnose_and_repair_terminal_tick_brace(path: Path):
    """Repair only the uniquely proven terminal Tick function brace loss.

    Several frozen patch generations rewrite Tick structurally.  The materialized
    v5.4.5 source showed exactly one unmatched delimiter: the opening brace of
    COFCRuntimeController::Tick, which is the final method in this translation
    unit.  Appending its closing brace is safe only when all of those facts are
    mechanically re-proven; every other imbalance remains fail-closed.
    """
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    lines = text.splitlines()
    stack, state, unexpected = scan_cpp_delimiters(text)

    if unexpected is not None:
        raise RuntimeError(
            "v5.4.5 materialized runtime unexpected closing delimiter %r" %
            (unexpected,)
        )
    if state in ("block_comment", "string", "char"):
        raise RuntimeError(
            "v5.4.5 materialized runtime ended inside lexical state %s" % state
        )
    if not stack:
        print("OpenOFC v5.4.5A materialized runtime delimiter balance: PASS")
        return

    print("OPENOFC_V545_DELIMITER_DIAG unmatched_count=%d" % len(stack))
    for token, ln, column in stack[-12:]:
        snippet = lines[ln - 1] if 0 < ln <= len(lines) else ""
        print(
            "OPENOFC_V545_DELIMITER_DIAG unmatched_open=%s line=%d col=%d source=%s"
            % (token, ln, column, snippet)
        )

    safe_tick_loss = False
    if len(stack) == 1 and stack[0][0] == "{":
        _token, focus, _column = stack[0]
        signature_window = "\n".join(lines[max(0, focus - 4):focus])
        suffix = "\n".join(lines[focus:])
        later_method = re.search(
            r"\n(?:bool|void|int|string|CString)\s+COFCRuntimeController::",
            "\n" + suffix,
        )
        safe_tick_loss = (
            "void COFCRuntimeController::Tick(" in signature_window
            and later_method is None
        )

    if not safe_tick_loss:
        raise RuntimeError("v5.4.5 materialized runtime has unmatched delimiters")

    if not text.endswith("\n"):
        text += "\n"
    text += "}\n"
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print(
        "OpenOFC v5.4.5A repaired terminal COFCRuntimeController::Tick closing brace"
    )

    verify = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    stack, state, unexpected = scan_cpp_delimiters(verify)
    if stack or unexpected is not None or state in ("block_comment", "string", "char"):
        raise RuntimeError("v5.4.5 terminal Tick brace repair did not restore balance")
    print("OpenOFC v5.4.5A materialized runtime delimiter balance: PASS")


def main():
    path = ROOT / "OpenHoldem" / "COFCScraper.cpp"
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    start_token = "// OPENOFC_EXACT_LINEAGE_DEGHOST_V545"
    end_token = "// OPENOFC_FANTASY_ENTRY_V544."
    start = text.find(start_token)
    end = text.find(end_token, start)
    if start < 0 or end < 0:
        raise RuntimeError("v5.4.5 deghost normalization bounds missing")

    prefix = text[:start]
    block = text[start:end]
    suffix = text[end:]
    count = block.count("kOFCCardEmpty")
    if count != 3:
        raise RuntimeError(
            f"v5.4.5 expected exactly 3 generated kOFCCardEmpty tokens, got {count}"
        )
    block = block.replace("kOFCCardEmpty", "kOFCCardNoCard")
    text = prefix + block + suffix

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)

    check = path.read_text(encoding="utf-8-sig")
    normalized = check[check.find(start_token):check.find(end_token, check.find(start_token))]
    if "kOFCCardEmpty" in normalized or normalized.count("kOFCCardNoCard") < 3:
        raise RuntimeError("v5.4.5 empty-sentinel normalization did not stick")
    print("OpenOFC v5.4.5A deghost empty sentinel normalization: PASS")

    diagnose_and_repair_terminal_tick_brace(
        ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
    )


if __name__ == "__main__":
    main()
