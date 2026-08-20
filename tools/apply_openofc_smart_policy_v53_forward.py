from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem/COFCBaselinePolicy.cpp"

raw = PATH.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig").replace("\r\n", "\n")
eol = "\r\n" if b"\r\n" in raw else "\n"

anchor = "bool ChooseFantasy15(\n"
prototype = "int FantasyContinuationValue(\n    const array<HandRank, 3> &ranks,\n    int fantasy_count);\n\n"
if prototype not in text:
    if text.count(anchor) != 1:
        raise RuntimeError(f"expected one ChooseFantasy15 anchor, got {text.count(anchor)}")
    text = text.replace(anchor, prototype + anchor, 1)

out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
PATH.write_bytes(data)
print("OpenOFC smart baseline v5.3 forward declaration applied")
