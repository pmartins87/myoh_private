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
    # v5.4.3 materialization changes harmless formatting around the terminal
    # REJECTED block.  Do not make v5.4.4 depend on that formatting: teach the
    # v5.4.4 upgrader to replace the block structurally, from its semantic log
    # marker through the first following `return -3;`.
    raw = V544_PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    old = '    regex_once(rel, pattern, replacement, "non-empty UNKNOWN remains occupied")\n'
    new = '''    path, text, eol, bom = read_source(rel)
    start_marker = '  DeepOFCLogSlot(base_name, "REJECTED", kOFCCardUnknown,'
    end_marker = '  return -3;'
    if text.count(start_marker) != 1:
        raise RuntimeError(
          "non-empty UNKNOWN remains occupied: semantic REJECTED marker is not unique")
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(
          "non-empty UNKNOWN remains occupied: terminal return -3 not found after marker")
    end += len(end_marker)
    text = text[:start] + replacement + text[end:]
    write_source(path, text, eol, bom)
    print("patched OpenHoldem/COFCScraper.cpp: non-empty UNKNOWN remains occupied")
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
