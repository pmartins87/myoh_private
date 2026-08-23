from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def diagnose_cpp_delimiters(path: Path):
    """Fail early with useful source locations for malformed generated C++.

    This intentionally runs after the full v5.4.5 patch chain, so the diagnostic
    sees the exact materialized runtime source that MSVC will compile.  It is a
    small lexical scanner rather than a raw character count: braces inside
    comments, normal string literals and character literals are ignored.
    """
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    lines = text.splitlines()
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
                advance(ch)
                advance(nxt)
                i += 2
                state = "code"
            else:
                advance(ch)
                i += 1
            continue

        if state == "string":
            if ch == "\\" and nxt:
                advance(ch)
                advance(nxt)
                i += 2
            else:
                advance(ch)
                i += 1
                if ch == '"':
                    state = "code"
            continue

        if state == "char":
            if ch == "\\" and nxt:
                advance(ch)
                advance(nxt)
                i += 2
            else:
                advance(ch)
                i += 1
                if ch == "'":
                    state = "code"
            continue

        # code
        if ch == "/" and nxt == "/":
            advance(ch)
            advance(nxt)
            i += 2
            state = "line_comment"
            continue
        if ch == "/" and nxt == "*":
            advance(ch)
            advance(nxt)
            i += 2
            state = "block_comment"
            continue
        if ch == '"':
            advance(ch)
            i += 1
            state = "string"
            continue
        if ch == "'":
            advance(ch)
            i += 1
            state = "char"
            continue

        if ch in opening:
            stack.append((ch, line, col))
        elif ch in pairs:
            if not stack or stack[-1][0] != pairs[ch]:
                print(
                    "OPENOFC_V545_DELIMITER_DIAG unexpected_close=%s line=%d col=%d top=%s"
                    % (ch, line, col, stack[-1] if stack else "EMPTY")
                )
                raise RuntimeError("v5.4.5 materialized runtime delimiter mismatch")
            stack.pop()

        advance(ch)
        i += 1

    if state in ("block_comment", "string", "char"):
        raise RuntimeError(
            "v5.4.5 materialized runtime ended inside lexical state %s" % state
        )

    if stack:
        print("OPENOFC_V545_DELIMITER_DIAG unmatched_count=%d" % len(stack))
        for token, ln, column in stack[-12:]:
            snippet = lines[ln - 1] if 0 < ln <= len(lines) else ""
            print(
                "OPENOFC_V545_DELIMITER_DIAG unmatched_open=%s line=%d col=%d source=%s"
                % (token, ln, column, snippet)
            )
        # The compiler currently reports near the beginning of the affected
        # function.  Emit a bounded context window for the newest unmatched
        # delimiter so the next repair can be source-first rather than guessed.
        _token, focus, _column = stack[-1]
        lo = max(1, focus - 25)
        hi = min(len(lines), focus + 140)
        print("OPENOFC_V545_DELIMITER_CONTEXT begin=%d end=%d" % (lo, hi))
        for ln in range(lo, hi + 1):
            print("%05d: %s" % (ln, lines[ln - 1]))
        raise RuntimeError("v5.4.5 materialized runtime has unmatched delimiters")

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

    diagnose_cpp_delimiters(ROOT / "OpenHoldem" / "COFCRuntimeController.cpp")


if __name__ == "__main__":
    main()
