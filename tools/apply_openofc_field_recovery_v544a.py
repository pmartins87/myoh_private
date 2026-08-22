from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem" / "COFCState.h"


def main():
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
    print("OpenOFC v5.4.4A state source normalization: PASS")


if __name__ == "__main__":
    main()
