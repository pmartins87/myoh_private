from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem" / "COFCState.h"
V544_PATH = ROOT / "tools" / "apply_openofc_field_recovery_v544.py"


def normalize_state_source():
    raw = PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    one_line = '''  bool IsKnownPhysicalCard() const { return IsKnownStandardCard() || IsJoker(); }
  bool IsCardBack() const { return value == kOFCCardBack; }
'''
    multi_line = '''  bool IsKnownPhysicalCard() const {
    return IsKnownStandardCard() || IsJoker();
  }
  bool IsCardBack() const { return value == kOFCCardBack; }
'''
    if text.count(one_line) == 1:
        text = text.replace(one_line, multi_line, 1)
    elif text.count(multi_line) != 1:
        raise RuntimeError("v5.4.4A could not normalize IsKnownPhysicalCard source shape")

    count_result = '''  int CountKnownCards() const {
    int result = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsKnownPhysicalCard()) ++result;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsKnownPhysicalCard()) ++result;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsKnownPhysicalCard()) ++result;
    return result;
  }
'''
    count_count = '''  int CountKnownCards() const {
    int count = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsKnownPhysicalCard()) ++count;
    return count;
  }
'''
    if text.count(count_result) == 1:
        text = text.replace(count_result, count_count, 1)
    elif text.count(count_count) != 1:
        raise RuntimeError("v5.4.4A could not normalize CountKnownCards source shape")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    PATH.write_bytes(data)


def harden_v544_scraper_patch():
    # The materialized ScrapeOFCSlot has three independent non-empty identity
    # failure terminals (rank contract, suit recognition and final conversion).
    # v5.4.4 must preserve physical occupancy for ALL three; tying the patch to
    # one formatting-specific REJECTED block made the upgrader itself brittle.
    # Teach the v5.4.4 upgrader to operate only inside ScrapeOFCSlot and convert
    # every one of those three terminal -3 returns into UNKNOWN_OCCUPIED.
    raw = V544_PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    old = '    regex_once(rel, pattern, replacement, "non-empty UNKNOWN remains occupied")\n'
    new = '''    path, text, eol, bom = read_source(rel)
    function_start = 'int CScraper::ScrapeOFCSlot('
    function_end = '\\nstatic bool DeepOFCRegisterKnownCard'
    if text.count(function_start) != 1 or text.count(function_end) != 1:
        raise RuntimeError(
          "non-empty UNKNOWN remains occupied: ScrapeOFCSlot function bounds are not unique")
    start = text.find(function_start)
    end = text.find(function_end, start)
    if end < 0:
        raise RuntimeError(
          "non-empty UNKNOWN remains occupied: ScrapeOFCSlot terminal boundary missing")
    body = text[start:end]
    rejected_marker = 'DeepOFCLogSlot(base_name, "REJECTED", kOFCCardUnknown,'
    rejected_count = body.count(rejected_marker)
    terminal = '    return -3;'
    terminal_count = body.count(terminal)
    if rejected_count != 3 or terminal_count != 3:
        raise RuntimeError(
          f"non-empty UNKNOWN remains occupied: expected 3 identity failures, "
          f"got rejected={rejected_count} return_minus3={terminal_count}")
    body = body.replace(
      rejected_marker,
      'DeepOFCLogSlot(base_name, "UNKNOWN_OCCUPIED", kOFCCardUnknown,')
    body = body.replace(
      terminal,
      '''    // OPENOFC_UNKNOWN_OCCUPIED_V544: the slot was already proven non-empty.
    // Failed rank/suit identity must not erase its physical occupancy.
    card->value = kOFCCardUnknown;
    return 2;''')
    text = text[:start] + body + text[end:]
    write_source(path, text, eol, bom)
    print(
      "patched OpenHoldem/COFCScraper.cpp: 3 non-empty identity failures -> UNKNOWN_OCCUPIED")
'''
    if text.count(old) == 1:
        text = text.replace(old, new, 1)
    elif text.count(new) != 1:
        raise RuntimeError("v5.4.4A could not harden the scraper UNKNOWN patch")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    V544_PATH.write_bytes(data)


def main():
    normalize_state_source()
    harden_v544_scraper_patch()
    print("OpenOFC v5.4.4A source normalization/hardening: PASS")


if __name__ == "__main__":
    main()
