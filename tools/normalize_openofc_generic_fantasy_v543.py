from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rewrite(rel: str, old: str, new: str, expected: int = 1):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{rel}: expected {expected} generic-Fantasy normalization target(s), got {count}")
    text = text.replace(old, new, expected)
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


# The frozen v5.3 policy regression fixtures predate fantasy_card_count. Their
# two 15-card fixtures remain useful, but count is now explicit data rather than
# a runtime mode. Mark the fixture data truthfully after v5.4.3 materializes.
rewrite(
    "OpenHoldem/COFCBaselinePolicySelftest.cpp",
    '''  state.hero_incoming_count = 15;\n  for (int i = 0; i < 15; ++i) state.hero_incoming[i].value = cards[i];\n''',
    '''  state.fantasy_card_count = 15;\n  state.hero_incoming_count = 15;\n  for (int i = 0; i < 15; ++i) state.hero_incoming[i].value = cards[i];\n''',
    expected=2)

print("normalized legacy 15-card policy fixtures to the generic Fantasy count contract")
