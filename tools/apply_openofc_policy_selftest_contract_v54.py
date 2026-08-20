from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem/COFCBaselinePolicySelftest.cpp"

raw = PATH.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig").replace("\r\n", "\n")
eol = "\r\n" if b"\r\n" in raw else "\n"

# v5.3 deliberately removed the million-point forced 1/2/2 opening-shape rule,
# but the inherited deterministic selftest still required that exact shape and
# exact 2-already/3-relocation plan. That assertion now tests behavior v5.3
# explicitly abolished. Keep the meaningful invariants instead: every opening
# card must be assigned exactly once, row capacities must be legal, no card is
# discarded, and the physical turn plan must cover every target card exactly
# once between already-correct and still-to-add sets.
old = '''  return action.valid && action.placement_count == 5 && action.unused_count == 0
    && rows[0] == 1 && rows[1] == 2 && rows[2] == 2
    && plan.valid && plan.already_correct_count == 2 && plan.to_add_count == 3;
'''
new = '''  const bool legal_shape = rows[0] >= 0 && rows[0] <= 3
    && rows[1] >= 0 && rows[1] <= 5
    && rows[2] >= 0 && rows[2] <= 5
    && rows[0] + rows[1] + rows[2] == 5;
  const bool complete_plan = plan.valid && plan.target_count == 5
    && plan.unused_count == 0
    && plan.already_correct_count + plan.to_add_count == 5;
  if (!legal_shape || !complete_plan) {
    std::cerr << "normal opening structural contract failed: rows="
      << rows[0] << "/" << rows[1] << "/" << rows[2]
      << " target=" << plan.target_count
      << " already=" << plan.already_correct_count
      << " add=" << plan.to_add_count
      << " unused=" << plan.unused_count << "\\n";
  }
  return action.valid && action.placement_count == 5 && action.unused_count == 0
    && legal_shape && complete_plan;
'''
if text.count(old) != 1:
    raise RuntimeError("stale exact-1/2/2 NormalOpening selftest contract not found exactly once")
text = text.replace(old, new, 1)

# Make the fixture naming explicit in comments/output without changing the
# function names expected by older patch scripts. A 15-card test vector is one
# Fantasy fixture, not a separate runtime mode.
text = text.replace(
    'std::cerr << "Fantasy15 policy rejected: " << error << "\\n";',
    'std::cerr << "Fantasy fixture(count=15) policy rejected: " << error << "\\n";',
    1,
)
text = text.replace(
    'std::cerr << "dual-Joker Fantasy15 policy rejected: " << error << "\\n";',
    'std::cerr << "dual-Joker Fantasy fixture(count=15) policy rejected: " << error << "\\n";',
    1,
)

out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
PATH.write_bytes(data)
print("repaired v5.3 policy selftest: opening is structural, not forced 1/2/2")
