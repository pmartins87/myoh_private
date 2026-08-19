from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "OpenHoldem/COFCReconstructor.cpp"
PATH = ROOT / REL
raw = PATH.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
eol = "\r\n" if b"\r\n" in raw else "\n"
text = raw.decode("utf-8-sig").replace("\r\n", "\n")

anchor = "bool ValidateObservationKnownCardUniqueness(\n"
helper = r'''bool OpponentFinalInformationVisible(
    const COFCVisualObservation &observation) {
  if (observation.hero_chair < 0
      || observation.hero_chair >= observation.player_count) return false;
  if (observation.round_index < 0 || observation.round_index > 4) return false;
  bool found_opponent = false;
  for (int p = 0; p < observation.player_count; ++p) {
    if (p == observation.hero_chair || !observation.players[p].occupied
        || observation.players[p].sitting_out) continue;
    found_opponent = true;
    const COFCVisualPlayerObservation &opp = observation.players[p];
    if (opp.hidden_incoming_count != 0) return false;
    const int known = opp.visual_board.CountKnownCards();
    const int expected_public = opp.fantasy
      ? 13 : (5 + 2 * observation.round_index);
    if (known < expected_public) return false;
  }
  return found_opponent;
}

'''
if anchor not in text:
    raise RuntimeError("reconstructor uniqueness anchor missing")
text = text.replace(anchor, helper + anchor, 1)

old = '''  const bool hero_fantasy =
    observation.players[observation.hero_chair].fantasy;
  out->decision_finalizable = hero_fantasy
    || observation.dealer_chair != observation.hero_chair
    || observation.hero_timer_active;
'''
new = '''  const bool hero_fantasy =
    observation.players[observation.hero_chair].fantasy;
  const bool opponent_final_info_visible =
    OpponentFinalInformationVisible(observation);
  out->decision_finalizable = hero_fantasy
    || observation.dealer_chair != observation.hero_chair
    || observation.hero_timer_active
    || opponent_final_info_visible;
'''
count = text.count(old)
if count != 2:
    raise RuntimeError(f"expected two finalization blocks, got {count}")
text = text.replace(old, new)

out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
PATH.write_bytes(data)
print("OpenOFC opponent-reveal finalization fallback applied successfully")
