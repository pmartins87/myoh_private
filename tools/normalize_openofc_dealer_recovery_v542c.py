from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "OpenHoldem/COFCReconstructor.cpp"
raw = path.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig").replace("\r\n", "\n")
eol = "\r\n" if b"\r\n" in raw else "\n"

# ReconstructFantasyDecision is a helper outside COFCReconstructor::Reconstruct,
# so it cannot see that function's local dealer_carried flag. The native
# Fantasy scraper remains strict in v5.4.2C; a valid Fantasy observation always
# owns its visible exact dealer marker. Normalize that one helper assignment to
# explicit false while normal reconstruction retains the carry-forward value.
old = '''  out->dealer_carried = dealer_carried;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = -1;\n'''
new = '''  out->dealer_carried = false;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = -1;\n'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"expected exactly one Fantasy dealer-carried assignment, got {count}")
text = text.replace(old, new, 1)
out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
path.write_bytes(data)
print("normalized Fantasy dealer_carried=false; normal carry-forward remains stateful")
