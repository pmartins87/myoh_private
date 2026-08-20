from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem/COFCBaselinePolicySelftest.cpp"
raw = PATH.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig").replace("\r\n", "\n")
eol = "\r\n" if b"\r\n" in raw else "\n"

old = '''  return action.valid && action.placement_count == 5 && action.unused_count == 0
    && rows[0] == 1 && rows[1] == 2 && rows[2] == 2
    && plan.valid && plan.already_correct_count == 2 && plan.to_add_count == 3;
}
'''
new = '''  // Smart baseline no longer hard-codes a 1/2/2 opening. The invariant is
  // a legal complete five-card assignment and a valid relocation plan.
  return action.valid && action.placement_count == 5 && action.unused_count == 0
    && rows[0] <= 3 && rows[1] <= 5 && rows[2] <= 5
    && rows[0] + rows[1] + rows[2] == 5
    && plan.valid && plan.target_count == 5;
}

bool SmartOpeningUsesQQFantasyGateway() {
  COFCState state = BaseState(false, 0);
  const int q1 = Card(12, 0);
  const int q2 = Card(12, 1);
  const int cards[5] = {q1, q2, Card(9, 2), Card(5, 3), Card(2, 0)};
  state.hero_incoming_count = 5;
  for (int i = 0; i < 5; ++i) state.hero_incoming[i].value = cards[i];
  COFCStrategyAction action;
  std::string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    std::cerr << "smart QQ opening policy rejected: " << error << "\\n";
    return false;
  }
  int q_top = 0;
  for (int i = 0; i < action.placement_count; ++i) {
    if ((action.placements[i].card_value == q1
          || action.placements[i].card_value == q2)
        && action.placements[i].row == kOFCRowTop) ++q_top;
  }
  if (q_top != 2) {
    std::cerr << "smart QQ opening failed to preserve Fantasy gateway; q_top="
      << q_top << "\\n";
    return false;
  }
  return true;
}
'''
if text.count(old) != 1:
    raise RuntimeError(f"expected one old NormalOpening assertion, got {text.count(old)}")
text = text.replace(old, new, 1)

old_main = '''  if (!Fantasy15() || !Fantasy15DualJoker() || !NormalOpening()
      || !NormalRoundPreservesJoker() || !UnavoidableFoulStillActs()) return 1;
'''
new_main = '''  if (!Fantasy15() || !Fantasy15DualJoker() || !NormalOpening()
      || !SmartOpeningUsesQQFantasyGateway()
      || !NormalRoundPreservesJoker() || !UnavoidableFoulStillActs()) return 1;
'''
if text.count(old_main) != 1:
    raise RuntimeError(f"expected one v4.3 main chain, got {text.count(old_main)}")
text = text.replace(old_main, new_main, 1)

out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
PATH.write_bytes(data)
print("OpenOFC smart baseline v5.3 selftest semantics applied")
