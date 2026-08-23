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


def cpp_brace_owners_at_lines(text: str, needles):
    """Return active lexical brace owners before each landmark line is parsed."""
    lines = text.splitlines()
    hits = {needle: [] for needle in needles}
    stack = []
    state = "code"

    for line_number, source in enumerate(lines, 1):
        for needle in needles:
            if needle in source:
                hits[needle].append((line_number, list(stack), source.strip()))

        i = 0
        while i < len(source):
            ch = source[i]
            nxt = source[i + 1] if i + 1 < len(source) else ""

            if state == "block_comment":
                if ch == "*" and nxt == "/":
                    state = "code"
                    i += 2
                else:
                    i += 1
                continue
            if state == "string":
                if ch == "\\" and nxt:
                    i += 2
                else:
                    if ch == '"': state = "code"
                    i += 1
                continue
            if state == "char":
                if ch == "\\" and nxt:
                    i += 2
                else:
                    if ch == "'": state = "code"
                    i += 1
                continue

            if ch == "/" and nxt == "/":
                break
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch == '"':
                state = "string"
                i += 1
                continue
            if ch == "'":
                state = "char"
                i += 1
                continue
            if ch == "{":
                stack.append((line_number, source.strip()))
            elif ch == "}":
                if stack:
                    stack.pop()
            i += 1

    return hits


def owner_has(owners, marker: str) -> bool:
    return any(marker in source for _line, source in owners)


def require_unique_hit(hits, needle: str):
    found = hits.get(needle, [])
    if len(found) != 1:
        raise RuntimeError(
            "v5.4.5 Tick semantic guard expected one %r landmark, got %d"
            % (needle, len(found))
        )
    return found[0]


def assert_tick_semantics(text: str, repaired: bool):
    """Prove that normal decision landmarks are outside kReacquire.

    The v5.4.5 materialization bug dropped the inner closing brace of the
    kReacquire branch. A previous normalizer appended a brace at EOF, which made
    the translation unit compile but left every subsequent normal decision path
    nested under `if (phase_ == kReacquire)`. These structural assertions keep
    that class of liveness bug from ever becoming a green binary again.
    """
    keys = (
        "void COFCRuntimeController::Tick(",
        "if (phase_ == kReacquire) {",
        "if (phase_ == kWaitingFinalInfo) {",
        "if (phase_ == kIdle) {",
        "DecisionStabilized(state)",
        "COFCBaselinePolicy::Choose",
        "if (phase_ == kArranging)",
    )
    hits = cpp_brace_owners_at_lines(text, keys)
    tick = require_unique_hit(hits, keys[0])
    reacquire = require_unique_hit(hits, keys[1])
    waiting = require_unique_hit(hits, keys[2])
    idle = require_unique_hit(hits, keys[3])
    stabilized = require_unique_hit(hits, keys[4])
    policy = require_unique_hit(hits, keys[5])
    arranging = require_unique_hit(hits, keys[6])

    tick_line = tick[0]
    reacquire_line = reacquire[0]
    if not (tick_line < reacquire_line < waiting[0] < idle[0] < arranging[0]):
        raise RuntimeError("v5.4.5 Tick landmarks are not in expected execution order")

    if repaired:
        for label, hit in (
            ("kWaitingFinalInfo", waiting),
            ("kIdle", idle),
            ("DecisionStabilized", stabilized),
            ("COFCBaselinePolicy::Choose", policy),
            ("kArranging", arranging),
        ):
            if owner_has(hit[1], "if (phase_ == kReacquire) {"):
                raise RuntimeError(
                    "v5.4.5 semantic liveness failure: %s remains nested under kReacquire"
                    % label
                )
        if not owner_has(stabilized[1], "if (phase_ == kIdle) {"):
            raise RuntimeError(
                "v5.4.5 semantic liveness failure: DecisionStabilized escaped kIdle"
            )
        if not owner_has(policy[1], "if (phase_ == kIdle) {"):
            raise RuntimeError(
                "v5.4.5 semantic liveness failure: policy calculation escaped kIdle"
            )
        print(
            "OPENOFC_V545_TICK_SEMANTICS PASS "
            "waiting_idle_policy_arranging_outside_reacquire=1"
        )
        return

    # The unmatched lexical brace has already been separately proven to be
    # Tick's outer brace from its multi-line signature window.  Here we need only
    # prove the missing *inner* boundary: kWaitingFinalInfo is directly owned by
    # kReacquire instead of being Tick-level code.
    owners = waiting[1]
    if not owner_has(owners, "if (phase_ == kReacquire) {"):
        raise RuntimeError(
            "v5.4.5 unmatched Tick brace is not explained by kReacquire nesting"
        )
    if not owners or owners[-1][0] != reacquire_line:
        raise RuntimeError(
            "v5.4.5 kWaitingFinalInfo is not directly owned by kReacquire"
        )
    print(
        "OPENOFC_V545_TICK_SEMANTICS PRE_REPAIR_PROOF "
        "waiting_nested_directly_under_reacquire=1"
    )


def repair_reacquire_closing_brace(path: Path):
    """Restore the uniquely proven missing inner kReacquire closing brace."""
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    lines = text.splitlines()
    stack, state, unexpected = scan_cpp_delimiters(text)

    if unexpected is not None:
        raise RuntimeError(
            "v5.4.5 materialized runtime unexpected closing delimiter %r"
            % (unexpected,)
        )
    if state in ("block_comment", "string", "char"):
        raise RuntimeError(
            "v5.4.5 materialized runtime ended inside lexical state %s" % state
        )

    if not stack:
        assert_tick_semantics(text, repaired=True)
        print("OpenOFC v5.4.5A runtime already structurally balanced: PASS")
        return

    print("OPENOFC_V545_DELIMITER_DIAG unmatched_count=%d" % len(stack))
    for token, ln, column in stack[-12:]:
        snippet = lines[ln - 1] if 0 < ln <= len(lines) else ""
        print(
            "OPENOFC_V545_DELIMITER_DIAG unmatched_open=%s line=%d col=%d source=%s"
            % (token, ln, column, snippet)
        )

    if len(stack) != 1 or stack[0][0] != "{":
        raise RuntimeError("v5.4.5 materialized runtime has unexpected delimiter shape")
    _token, focus, _column = stack[0]
    signature_window = "\n".join(lines[max(0, focus - 4):focus])
    suffix = "\n".join(lines[focus:])
    later_method = re.search(
        r"\n(?:bool|void|int|string|CString)\s+COFCRuntimeController::",
        "\n" + suffix,
    )
    if "void COFCRuntimeController::Tick(" not in signature_window or later_method is not None:
        raise RuntimeError(
            "v5.4.5 unmatched delimiter is not the proven final Tick outer brace"
        )

    assert_tick_semantics(text, repaired=False)

    waiting_token = "  if (phase_ == kWaitingFinalInfo) {\n"
    if text.count(waiting_token) != 1:
        raise RuntimeError(
            "v5.4.5 cannot uniquely locate kWaitingFinalInfo insertion boundary"
        )

    text = text.replace(
        waiting_token,
        "  }\n\n" + waiting_token,
        1,
    )

    verify_stack, verify_state, verify_unexpected = scan_cpp_delimiters(text)
    if (verify_stack or verify_unexpected is not None
            or verify_state in ("block_comment", "string", "char")):
        raise RuntimeError(
            "v5.4.5 kReacquire brace repair did not restore lexical balance"
        )
    assert_tick_semantics(text, repaired=True)

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print(
        "OpenOFC v5.4.5A repaired missing inner kReacquire closing brace; "
        "normal Tick decision path restored"
    )


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

    repair_reacquire_closing_brace(
        ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
    )


if __name__ == "__main__":
    main()
