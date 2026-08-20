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
        raise RuntimeError(f"{rel}: expected {expected} normalization target(s), got {count}")
    text = text.replace(old, new, expected)
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


# ReconstructFantasyDecision is a helper outside COFCReconstructor::Reconstruct,
# so it cannot see that function's local dealer_carried flag. The native
# Fantasy scraper remains strict in v5.4.2C; a valid Fantasy observation always
# owns its visible exact dealer marker. Normalize that one helper assignment to
# explicit false while normal reconstruction retains the carry-forward value.
rewrite(
    "OpenHoldem/COFCReconstructor.cpp",
    '''  out->dealer_carried = dealer_carried;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = -1;\n''',
    '''  out->dealer_carried = false;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = -1;\n''')

# v5.4/v5.4.2B selftests predate the explicit dealer-confidence bit and create
# their observations by hand. Their fixed dealer_chair=0 is certified test data,
# so mark it known after the v5.4.2C state contract is materialized.
for rel in (
    "OpenHoldem/COFCRuntimeContinuitySelftest.cpp",
    "OpenHoldem/COFCPartialReconnectSelftest.cpp",
):
    rewrite(
        rel,
        '''  obs->dealer_chair = 0;\n  obs->acting_chair = 1;\n''',
        '''  obs->dealer_chair = 0;\n  obs->dealer_known = true;\n  obs->acting_chair = 1;\n''')

print("normalized Fantasy dealer carry scope and legacy selftest dealer confidence")
