from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem/COFCBaselinePolicySelftest.cpp"

raw = PATH.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig").replace("\r\n", "\n")
eol = "\r\n" if b"\r\n" in raw else "\n"

old = '''int main() {
  if (!Fantasy15() || !Fantasy15DualJoker() || !NormalOpening()
      || !NormalRoundPreservesJoker() || !UnavoidableFoulStillActs()) return 1;
  std::cout << "DEEPOFC BASELINE POLICY: PASS\\n";
  return 0;
}
'''
new = '''int main() {
  bool ok = true;
  const bool fantasy15 = Fantasy15();
  std::cout << "POLICY_CASE Fantasy15=" << (fantasy15 ? "PASS" : "FAIL") << "\\n";
  ok = fantasy15 && ok;
  const bool fantasy15_dual = Fantasy15DualJoker();
  std::cout << "POLICY_CASE Fantasy15DualJoker=" << (fantasy15_dual ? "PASS" : "FAIL") << "\\n";
  ok = fantasy15_dual && ok;
  const bool opening = NormalOpening();
  std::cout << "POLICY_CASE NormalOpening=" << (opening ? "PASS" : "FAIL") << "\\n";
  ok = opening && ok;
  const bool joker = NormalRoundPreservesJoker();
  std::cout << "POLICY_CASE NormalRoundPreservesJoker=" << (joker ? "PASS" : "FAIL") << "\\n";
  ok = joker && ok;
  const bool foul = UnavoidableFoulStillActs();
  std::cout << "POLICY_CASE UnavoidableFoulStillActs=" << (foul ? "PASS" : "FAIL") << "\\n";
  ok = foul && ok;
  if (!ok) return 1;
  std::cout << "DEEPOFC BASELINE POLICY: PASS\\n";
  return 0;
}
'''
if text.count(old) != 1:
    raise RuntimeError("expected patched v4.3 policy selftest main exactly once")
text = text.replace(old, new, 1)
out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
PATH.write_bytes(data)
print("instrumented OpenOFC policy selftest with per-case diagnostics")
