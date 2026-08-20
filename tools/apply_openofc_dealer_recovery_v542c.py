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
        raise RuntimeError(
            f"{rel}: expected one target, got {count}: {old[:160]!r}"
        )
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_observation_contract():
    rel = "OpenHoldem/COFCVisualObservation.h"
    replace_once(
        rel,
        '''    dealer_chair = -1;\n    acting_chair = -1;\n''',
        '''    dealer_chair = -1;\n    // OPENOFC_DEALER_RECOVERY_V542C. A missing/ambiguous dealer marker is\n    // represented explicitly instead of invalidating the entire card frame.\n    dealer_known = false;\n    acting_chair = -1;\n''')
    replace_once(
        rel,
        '''  int dealer_chair;\n  int acting_chair;\n''',
        '''  int dealer_chair;\n  bool dealer_known;\n  int acting_chair;\n''')


def patch_state_contract():
    rel = "OpenHoldem/COFCState.h"
    replace_once(
        rel,
        '''    dealer_chair = -1;\n    acting_chair = -1;\n''',
        '''    dealer_chair = -1;\n    dealer_known = false;\n    dealer_carried = false;\n    acting_chair = -1;\n''')
    replace_once(
        rel,
        '''  int dealer_chair;\n  int acting_chair;\n''',
        '''  int dealer_chair;\n  // dealer_known means canonical finalization may use dealer identity.\n  // dealer_carried means that identity came from same-hand prior lineage after\n  // the raw marker temporarily disappeared; it was never guessed.\n  bool dealer_known;\n  bool dealer_carried;\n  int acting_chair;\n''')


def patch_scraper():
    rel = "OpenHoldem/COFCScraper.cpp"

    # Normal play: exact dealer identity is useful for finalization, but the
    # board/current-card scrape remains actionable even when the marker blinks
    # out during animation. Keep the raw frame valid and make uncertainty data.
    replace_once(
        rel,
        '''  if (dealer_count != 1) {\n    write_log(k_always_log_errors,\n      "[DeepOFC] Expected exactly one dealer; got dealer=%d\\n",\n      dealer_count);\n    return false;\n  }\n\n  if (!DeepOFCReadMandatoryBoolean(this,\n''',
        '''  obs->dealer_known = dealer_count == 1;\n  if (!obs->dealer_known) {\n    obs->dealer_chair = -1;\n    write_log(k_always_log_errors,\n      "[OpenOFC DEALER_RAW] count=%d dealer=UNKNOWN terminal=0 "\n      "action=PROVISIONAL_ONLY continue_scraping=1\\n",\n      dealer_count);\n  } else {\n    write_log(true,\n      "[OpenOFC DEALER_RAW] count=1 dealer=%d source=VISIBLE_MARKER\\n",\n      obs->dealer_chair);\n  }\n\n  if (!DeepOFCReadMandatoryBoolean(this,\n''')

    # Fantasy route remains strict in this gate, but mark its exact observation
    # so the new canonical field is truthful. Generic native Fantasy routing is
    # still a separate v5.4.3 capability gate.
    replace_once(
        rel,
        '''  if (dealer_count != 1) return false;\n  if (!DeepOFCReadMandatoryBoolean(\n        this, "ofc_fantasy15_confirm_visible", &obs->confirm_visible)) {\n''',
        '''  obs->dealer_known = dealer_count == 1;\n  if (!obs->dealer_known) return false;\n  if (!DeepOFCReadMandatoryBoolean(\n        this, "ofc_fantasy15_confirm_visible", &obs->confirm_visible)) {\n''')


def patch_reconstructor():
    rel = "OpenHoldem/COFCReconstructor.cpp"

    # Resolve a transient raw dealer dropout from previous same-hand canonical
    # lineage before metadata validation. This is temporal carry-forward, not an
    # inference: only an already certified exact chair can be reused.
    replace_once(
        rel,
        '''  COFCVisualObservation observation = input_observation;\n  // The TableMap emits a single rank token X for Joker. Resolve up to two raw\n''',
        '''  COFCVisualObservation observation = input_observation;\n  bool dealer_carried = false;\n  if (!observation.dealer_known\n      && previous != NULL && previous->valid && previous->dealer_known\n      && previous->player_count == observation.player_count\n      && previous->hero_chair == observation.hero_chair) {\n    observation.dealer_chair = previous->dealer_chair;\n    observation.dealer_known = true;\n    dealer_carried = true;\n  }\n  // The TableMap emits a single rank token X for Joker. Resolve up to two raw\n''')

    replace_once(
        rel,
        '''      || observation.dealer_chair < 0\n      || observation.dealer_chair >= observation.player_count\n      || observation.acting_chair < 0\n''',
        '''      || (observation.dealer_known\n          && (observation.dealer_chair < 0\n              || observation.dealer_chair >= observation.player_count))\n      || (!observation.dealer_known && observation.dealer_chair != -1)\n      || observation.acting_chair < 0\n''')

    # Existing hand metadata may upgrade unknown -> exact, or carry an exact
    # prior chair through a dropout. Reject only contradictory exact identities.
    replace_once(
        rel,
        '''    if (previous->dealer_chair != observation.dealer_chair) {\n      return Fail(out, error, "dealer chair changed inside hand");\n    }\n''',
        '''    if (previous->dealer_known && observation.dealer_known\n        && previous->dealer_chair != observation.dealer_chair) {\n      return Fail(out, error, "dealer chair changed inside hand");\n    }\n''')

    replace_once(
        rel,
        '''          || previous->hero_chair != observation.hero_chair\n          || previous->dealer_chair != observation.dealer_chair) {\n        return Fail(out, error, "Fantasy hand metadata changed during arrangement");\n''',
        '''          || previous->hero_chair != observation.hero_chair\n          || (previous->dealer_known && observation.dealer_known\n              && previous->dealer_chair != observation.dealer_chair)) {\n        return Fail(out, error, "Fantasy hand metadata changed during arrangement");\n''')

    path, text, eol, bom = read_source(rel)
    old = '''  out->hero_chair = observation.hero_chair;\n  out->dealer_chair = observation.dealer_chair;\n  out->acting_chair = observation.acting_chair;\n'''
    new = '''  out->hero_chair = observation.hero_chair;\n  out->dealer_chair = observation.dealer_chair;\n  out->dealer_known = observation.dealer_known;\n  out->dealer_carried = dealer_carried;\n  out->acting_chair = observation.acting_chair;\n'''
    count = text.count(old)
    if count != 2:
        raise RuntimeError(f"{rel}: expected 2 output metadata blocks, got {count}")
    text = text.replace(old, new)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: 2 output metadata blocks")

    # The opponent-reveal fallback was added after v2. Preserve it while making
    # dealer-based finalization confidence-aware. Otherwise unknown -1 would
    # incorrectly satisfy `dealer_chair != hero`.
    path, text, eol, bom = read_source(rel)
    old = '''  out->decision_finalizable = hero_fantasy\n    || observation.dealer_chair != observation.hero_chair\n    || observation.hero_timer_active\n    || opponent_final_info_visible;\n'''
    new = '''  out->decision_finalizable = hero_fantasy\n    || (observation.dealer_known\n        && observation.dealer_chair != observation.hero_chair)\n    || observation.hero_timer_active\n    || opponent_final_info_visible;\n'''
    count = text.count(old)
    if count != 2:
        raise RuntimeError(f"{rel}: expected 2 finalization blocks, got {count}")
    text = text.replace(old, new)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: 2 dealer-safe finalization blocks")

    replace_once(
        rel,
        '''  seed.hero_chair = observation.hero_chair;\n  seed.dealer_chair = observation.dealer_chair;\n  seed.acting_chair = observation.acting_chair;\n''',
        '''  seed.hero_chair = observation.hero_chair;\n  seed.dealer_chair = observation.dealer_chair;\n  seed.dealer_known = observation.dealer_known;\n  seed.dealer_carried = false;\n  seed.acting_chair = observation.acting_chair;\n''')

    replace_once(
        rel,
        '''      << ",\\\"dealer_chair\\\":" << state.dealer_chair\n      << ",\\\"acting_chair\\\":" << state.acting_chair\n''',
        '''      << ",\\\"dealer_chair\\\":" << state.dealer_chair\n      << ",\\\"dealer_known\\\":" << BoolJson(state.dealer_known)\n      << ",\\\"dealer_carried\\\":" << BoolJson(state.dealer_carried)\n      << ",\\\"acting_chair\\\":" << state.acting_chair\n''')


def patch_lazy_scraper_logging():
    rel = "OpenHoldem/CLazyScraper.cpp"
    replace_once(
        rel,
        '''      write_log(true,\n        "[DeepOFC CYCLE] id=%lu result=CANONICAL_VALID source=LINEAGE\\n",\n        deepofc_cycle);\n      write_log(true, "[DeepOFC SNAPSHOT v1] %s\\n", snapshot.c_str());\n''',
        '''      write_log(true,\n        "[DeepOFC CYCLE] id=%lu result=CANONICAL_VALID source=LINEAGE\\n",\n        deepofc_cycle);\n      if (rebuilt.dealer_carried) {\n        write_log(k_always_log_errors,\n          "[OpenOFC DEALER_CARRY_FORWARD] id=%lu dealer=%d "\n          "source=PRIOR_CANONICAL terminal=0 continue_scraping=1\\n",\n          deepofc_cycle, rebuilt.dealer_chair);\n      } else if (!rebuilt.dealer_known) {\n        write_log(true,\n          "[OpenOFC DEALER_UNKNOWN_PROVISIONAL] id=%lu confirm=HELD "\n          "unless_timer=1 terminal=0 continue_scraping=1\\n",\n          deepofc_cycle);\n      }\n      write_log(true, "[DeepOFC SNAPSHOT v1] %s\\n", snapshot.c_str());\n''')


def assert_contract():
    checks = {
        "OpenHoldem/COFCVisualObservation.h": [
            "OPENOFC_DEALER_RECOVERY_V542C",
            "dealer_known",
        ],
        "OpenHoldem/COFCState.h": [
            "dealer_known",
            "dealer_carried",
        ],
        "OpenHoldem/COFCScraper.cpp": [
            "[OpenOFC DEALER_RAW]",
            "action=PROVISIONAL_ONLY",
            "OPENOFC_TURN_SEMANTICS_DISABLED_V44",
        ],
        "OpenHoldem/COFCReconstructor.cpp": [
            "bool dealer_carried = false",
            "previous->dealer_known && observation.dealer_known",
            "observation.dealer_known",
            "state.dealer_carried",
        ],
        "OpenHoldem/CLazyScraper.cpp": [
            "[OpenOFC DEALER_CARRY_FORWARD]",
            "[OpenOFC DEALER_UNKNOWN_PROVISIONAL]",
        ],
    }
    for rel, needles in checks.items():
        text = (ROOT / rel).read_text(encoding="utf-8-sig", errors="strict")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise RuntimeError(f"{rel}: missing v5.4.2C markers: {missing}")

    scraper = (ROOT / "OpenHoldem/COFCScraper.cpp").read_text(
        encoding="utf-8-sig", errors="strict")
    if "Expected exactly one dealer; got dealer=%d" in scraper:
        raise RuntimeError("normal dealer dropout still rejects the entire raw frame")
    print("OpenOFC v5.4.2C dealer/actor continuity source contract passed")


def main():
    patch_observation_contract()
    patch_state_contract()
    patch_scraper()
    patch_reconstructor()
    patch_lazy_scraper_logging()
    assert_contract()
    print("OpenOFC v5.4.2C dealer recovery patch applied successfully")


if __name__ == "__main__":
    main()
