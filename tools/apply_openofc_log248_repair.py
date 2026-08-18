from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel: str, old: str, new: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected exactly one replacement target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_stddeck_suit_labels():
    # poker-eval StdDeck suit order is HEARTS, DIAMONDS, CLUBS, SPADES.
    # The old diagnostic helpers used cdhs, which made correctly decoded Jc/6h
    # appear in logs as Jh/6c even though the underlying card values were right.
    replacements = [
        ("OpenHoldem/COFCScraper.cpp",
         '  const char suits[] = "cdhs";\n',
         '  const char suits[] = "hdcs";\n'),
        ("OpenHoldem/COFCRuntimeController.cpp",
         '  const char suits[] = "cdhs";\n',
         '  const char suits[] = "hdcs";\n'),
        ("OpenHoldem/COFCActionExecutor.cpp",
         '  const char suits[] = "cdhs";\n',
         '  const char suits[] = "hdcs";\n'),
        ("OpenHoldem/COFCInspectorSnapshot.h",
         '    static const char suits[] = "cdhs";\n',
         '    static const char suits[] = "hdcs";\n'),
    ]
    for rel, old, new in replacements:
        replace_once(rel, old, new)


def patch_normal_hero_authority():
    old = '''  int dealer_count = 0, actor_count = 0;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool value = false;
    region.Format("ofc_p%d_dealer", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) { obs->dealer_chair = p; ++dealer_count; }

    value = false;
    region.Format("ofc_p%d_turn", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) { obs->acting_chair = p; ++actor_count; }
  }
  if ((dealer_count != 1) || (actor_count != 1)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Expected one dealer/actor; got dealer=%d actor=%d\\n",
      dealer_count, actor_count);
    return false;
  }

  if (!DeepOFCReadMandatoryBoolean(this,
        "ofc_confirm_visible", &obs->confirm_visible)) return false;
'''
    new = '''  // OPENOFC_CONFIRM_AUTHORITY: in KKPoker normal OFC the Hero can have an
  // actionable arrangement/Confirm UI while an opponent timer is also visible.
  // A Hold'em-style requirement for exactly one visual "actor" therefore
  // rejects a perfectly actionable OFC state. Dealer identity remains strict;
  // Hero input authority comes from the dedicated Confirm UI. Raw turn markers
  // are retained only as secondary wait-state evidence.
  int dealer_count = 0;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool value = false;
    region.Format("ofc_p%d_dealer", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) { obs->dealer_chair = p; ++dealer_count; }
  }
  if (dealer_count != 1) {
    write_log(k_always_log_errors,
      "[DeepOFC] Expected exactly one dealer; got dealer=%d\\n",
      dealer_count);
    return false;
  }

  if (!DeepOFCReadMandatoryBoolean(this,
        "ofc_confirm_visible", &obs->confirm_visible)) return false;

  int turn_flag_count = 0;
  int turn_flag_chair = -1;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool value = false;
    region.Format("ofc_p%d_turn", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) {
      turn_flag_chair = p;
      ++turn_flag_count;
    }
  }

  if (obs->confirm_visible) {
    // The visible Hero Confirm is the strongest available proof that the Hero
    // may arrange/submit this OFC decision, regardless of opponent timer UI.
    obs->acting_chair = hero_chair;
    write_log(true,
      "[OpenOFC AUTHORITY] hero_actionable=1 source=CONFIRM_VISIBLE raw_turn_flags=%d raw_turn_chair=%d\\n",
      turn_flag_count, turn_flag_chair);
  } else if (turn_flag_count == 1) {
    obs->acting_chair = turn_flag_chair;
  } else if (player_count == 2 && turn_flag_count == 0) {
    // HU wait-state fallback: when Hero has no Confirm and no calibrated turn
    // marker is lit, the only safe canonical actor is the other chair. This
    // keeps post-Confirm handoff observable without authorizing Hero input.
    obs->acting_chair = 1 - hero_chair;
    write_log(true,
      "[OpenOFC AUTHORITY] hero_actionable=0 source=HU_WAIT_INFERENCE raw_turn_flags=0\\n");
  } else {
    write_log(k_always_log_errors,
      "[DeepOFC] Ambiguous normal OFC action authority: confirm=%d turn_flags=%d\\n",
      obs->confirm_visible ? 1 : 0, turn_flag_count);
    return false;
  }
'''
    replace_once("OpenHoldem/COFCScraper.cpp", old, new)

    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        "  obs->hero_can_prepare = true;\n",
        "  obs->hero_can_prepare = (obs->acting_chair == hero_chair);\n")


def main():
    patch_stddeck_suit_labels()
    patch_normal_hero_authority()
    print("OpenOFC log248 repair applied successfully")


if __name__ == "__main__":
    main()
