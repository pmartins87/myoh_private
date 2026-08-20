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
            f"{rel}: expected one target, got {count}: {old[:140]!r}"
        )
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def replace_exact_count(rel: str, old: str, new: str, expected: int):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != expected:
        raise RuntimeError(
            f"{rel}: expected {expected} targets, got {count}: {old[:140]!r}"
        )
    text = text.replace(old, new)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: {count} sites")


def patch_state_contract():
    rel = "OpenHoldem/COFCState.h"
    replace_once(
        rel,
        '''    action_required = false;\n    hero_incoming_count = 0;\n''',
        '''    action_required = false;\n    // OPENOFC_PARTIAL_RECONNECT_V542B. True only for a process-memory-\n    // independent continuation of a later normal round that was already\n    // partially arranged before this runtime attached. In that mode the\n    // visible Hero board is the fixed baseline and hero_incoming contains only\n    // the still-live current cards needed to finish the UI transaction.\n    partial_turn_recovery = false;\n    hero_incoming_count = 0;\n''')
    replace_once(
        rel,
        '''  bool action_required;\n\n  COFCPlayerState players[kOFCMaxPlayers];\n''',
        '''  bool action_required;\n  bool partial_turn_recovery;\n\n  COFCPlayerState players[kOFCMaxPlayers];\n''')


def patch_reconstructor():
    rel = "OpenHoldem/COFCReconstructor.cpp"

    # A same-round lineage that originated from a partial bootstrap intentionally
    # carries only the remaining live card set (1 or 2 cards), not the historical
    # three-card deal that can no longer be recovered from one static frame.
    replace_once(
        rel,
        '''  int expected_incoming = observation.round_index == 0 ? 5 : 3;\n  if (static_cast<int>(current_incoming.size()) != expected_incoming) {\n''',
        '''  const bool partial_same_round = previous != NULL && previous->valid\n    && previous->partial_turn_recovery\n    && observation.round_index == previous->round_index;\n  int expected_incoming = observation.round_index == 0 ? 5 : 3;\n  if (partial_same_round) expected_incoming = previous->hero_incoming_count;\n  if (static_cast<int>(current_incoming.size()) != expected_incoming) {\n''')

    # This anchor is normal-flow-specific (Fantasy writes round_index=-1).
    replace_once(
        rel,
        '''  out->round_index = observation.round_index;\n  out->hero_can_prepare = observation.hero_can_prepare;\n''',
        '''  out->round_index = observation.round_index;\n  out->partial_turn_recovery = partial_same_round;\n  out->hero_can_prepare = observation.hero_can_prepare;\n''')

    # v4.2 derives discards from visibility instead of trusting tiny tracker OCR.
    # During partial recovery prior_incoming is intentionally reduced, therefore
    # only post-attach pending placements are expected to appear as newly
    # committed. The one absent reduced incoming card remains the derived discard.
    replace_once(
        rel,
        '''      const int expected_commit_count = previous->round_index == 0 ? 5 : 2;\n      const int expected_discard_count = previous->round_index == 0 ? 0 : 1;\n      if (static_cast<int>(committed_from_prior.size()) != expected_commit_count\n          || static_cast<int>(discard_delta.size()) != expected_discard_count) {\n''',
        '''      int expected_commit_count = previous->round_index == 0 ? 5 : 2;\n      const int expected_discard_count = previous->round_index == 0 ? 0 : 1;\n      if (previous->partial_turn_recovery) {\n        expected_commit_count = 0;\n        for (int i = 0; i < kOFCMaxIncomingCards; ++i)\n          if (previous->pending[i].active) ++expected_commit_count;\n      }\n      if (static_cast<int>(committed_from_prior.size()) != expected_commit_count\n          || static_cast<int>(discard_delta.size()) != expected_discard_count) {\n''')

    # Generalize v5.4 current-screen recovery from all-three-loose only to the
    # two partial shapes that are physically actionable in KKPoker: loose=2
    # means one placement has already happened and one more must be chosen;
    # loose=1 means two placements are already on the board and Confirm can
    # safely finish the round, leaving the last loose card as the discard.
    replace_once(
        rel,
        '''  // In R1..R4 the current screen is unambiguous when all three current cards\n  // are still loose: every Hero row card is committed. Once one of the three\n  // has been dragged into a row, a single frame cannot prove which visible row\n  // card is current-round tentative, so v5.4.2A refuses to guess.\n  if (observation.hero_loose_count != 3) {\n    ostringstream oss;\n    oss << "current-screen normal round " << observation.round_index\n        << " is partially arranged; expected all 3 current cards loose, got "\n        << observation.hero_loose_count;\n    return Fail(out, error, oss.str());\n  }\n\n  const COFCPlayerBoard &hero_visual =\n    observation.players[observation.hero_chair].visual_board;\n  const int expected_committed = 3 + 2 * observation.round_index;\n  if (hero_visual.CountKnownCards() != expected_committed) {\n    ostringstream oss;\n    oss << "current-screen normal round " << observation.round_index\n        << " expected " << expected_committed\n        << " committed Hero row cards with all three current cards loose; got "\n        << hero_visual.CountKnownCards();\n    return Fail(out, error, oss.str());\n  }\n\n  set<int> current = CardArraySet(\n    observation.hero_loose_cards, observation.hero_loose_count);\n  if (current.size() != 3) {\n    return Fail(out, error,\n      "current-screen normal recovery requires three unique known loose cards");\n  }\n''',
        '''  // OPENOFC_PARTIAL_RECONNECT_V542B. A later normal round is still\n  // physically self-describing even after 1 or 2 cards were placed before this\n  // process attached. We do not invent which historical three-card deal or\n  // which visible row card was tentative. Instead the entire visible Hero board\n  // becomes the fixed continuation baseline and only the remaining 1..3 loose\n  // physical cards form the live decision set. This is sufficient to finish\n  // the client transaction without reconstructing unknowable history.\n  if (observation.hero_loose_count < 1 || observation.hero_loose_count > 3) {\n    ostringstream oss;\n    oss << "current-screen normal round " << observation.round_index\n        << " requires 1..3 live loose cards, got "\n        << observation.hero_loose_count;\n    return Fail(out, error, oss.str());\n  }\n\n  const COFCPlayerBoard &hero_visual =\n    observation.players[observation.hero_chair].visual_board;\n  const int expected_before_round = 3 + 2 * observation.round_index;\n  const int already_placed_now = 3 - observation.hero_loose_count;\n  const int expected_visible = expected_before_round + already_placed_now;\n  if (hero_visual.CountKnownCards() != expected_visible) {\n    ostringstream oss;\n    oss << "current-screen normal round " << observation.round_index\n        << " expected visible Hero board count=" << expected_visible\n        << " for loose=" << observation.hero_loose_count\n        << ", got " << hero_visual.CountKnownCards();\n    return Fail(out, error, oss.str());\n  }\n\n  set<int> current = CardArraySet(\n    observation.hero_loose_cards, observation.hero_loose_count);\n  if (static_cast<int>(current.size()) != observation.hero_loose_count) {\n    return Fail(out, error,\n      "current-screen normal recovery requires unique known loose cards");\n  }\n''')

    replace_once(
        rel,
        '''  seed.hero_discard_count = 0;\n  seed.valid = true;\n\n  if (!Reconstruct(observation, &seed, out, error)) {\n''',
        '''  seed.hero_discard_count = 0;\n  seed.partial_turn_recovery = observation.hero_loose_count < 3;\n  seed.valid = true;\n\n  if (!Reconstruct(observation, &seed, out, error)) {\n''')

    replace_once(
        rel,
        '''      << ",\\\"action_required\\\":" << BoolJson(state.action_required)\n      << "}";\n''',
        '''      << ",\\\"action_required\\\":" << BoolJson(state.action_required)\n      << ",\\\"partial_turn_recovery\\\":" << BoolJson(state.partial_turn_recovery)\n      << "}";\n''')


def patch_policy():
    rel = "OpenHoldem/COFCBaselinePolicy.cpp"
    replace_once(
        rel,
        '''  const int expected = state.round_index == 0 ? 5 : 3;\n  if (state.hero_incoming_count != expected) {\n    return Fail(action, error, "normal incoming count disagrees with round");\n  }\n''',
        '''  const bool partial_recovery = state.partial_turn_recovery;\n  const int expected = state.round_index == 0\n    ? 5 : (partial_recovery ? state.hero_incoming_count : 3);\n  if (partial_recovery\n      && (state.round_index < 1 || expected < 1 || expected > 2)) {\n    return Fail(action, error, "partial reconnect requires 1..2 live incoming cards");\n  }\n  if (state.hero_incoming_count != expected) {\n    return Fail(action, error, "normal incoming count disagrees with round");\n  }\n''')

    # v4.3 has both the strict and unavoidable-foul enumeration passes. In a
    # partial reconnect the client may already have forced Joker to be the only
    # remaining discard candidate, so continuity must permit that shape in both.
    replace_exact_count(
        rel,
        '''    if (unused >= 0 && incoming[unused].joker != 0) continue;\n''',
        '''    if (unused >= 0 && incoming[unused].joker != 0\n        && !partial_recovery) continue;\n''',
        2)

    replace_once(
        rel,
        '''  action->valid = action->placement_count == (state.round_index == 0 ? 5 : 2)\n    && action->unused_count == (state.round_index == 0 ? 0 : 1);\n''',
        '''  const int required_placements = state.round_index == 0\n    ? 5 : (partial_recovery ? expected - 1 : 2);\n  action->valid = action->placement_count == required_placements\n    && action->unused_count == (state.round_index == 0 ? 0 : 1);\n''')


def patch_turn_plan():
    rel = "OpenHoldem/COFCTurnPlan.cpp"
    replace_once(
        rel,
        '''    const int expected_incoming = state.round_index == 0 ? 5 : 3;\n    if (state.hero_incoming_count != expected_incoming) {\n      return Fail(out, error, "normal incoming-card count disagrees with round");\n    }\n    expected_placements = state.round_index == 0 ? 5 : 2;\n    expected_unused = state.round_index == 0 ? 0 : 1;\n''',
        '''    if (state.partial_turn_recovery) {\n      if (state.round_index < 1\n          || state.hero_incoming_count < 1\n          || state.hero_incoming_count > 2) {\n        return Fail(out, error, "invalid partial-reconnect normal decision shape");\n      }\n      expected_placements = state.hero_incoming_count - 1;\n      expected_unused = 1;\n    } else {\n      const int expected_incoming = state.round_index == 0 ? 5 : 3;\n      if (state.hero_incoming_count != expected_incoming) {\n        return Fail(out, error, "normal incoming-card count disagrees with round");\n      }\n      expected_placements = state.round_index == 0 ? 5 : 2;\n      expected_unused = state.round_index == 0 ? 0 : 1;\n    }\n''')


def assert_contract():
    checks = {
        "OpenHoldem/COFCState.h": [
            "OPENOFC_PARTIAL_RECONNECT_V542B",
            "partial_turn_recovery",
        ],
        "OpenHoldem/COFCReconstructor.cpp": [
            "partial_same_round",
            "expected_before_round",
            "already_placed_now",
            "seed.partial_turn_recovery",
            "partial_turn_recovery\\\"",
        ],
        "OpenHoldem/COFCBaselinePolicy.cpp": [
            "partial_recovery",
            "partial reconnect requires 1..2 live incoming cards",
            "required_placements",
        ],
        "OpenHoldem/COFCTurnPlan.cpp": [
            "invalid partial-reconnect normal decision shape",
            "state.hero_incoming_count - 1",
        ],
    }
    for rel, needles in checks.items():
        text = (ROOT / rel).read_text(encoding="utf-8-sig", errors="strict")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise RuntimeError(f"{rel}: missing v5.4.2B markers: {missing}")
    print("OpenOFC v5.4.2B source contract assertions passed")


def main():
    patch_state_contract()
    patch_reconstructor()
    patch_policy()
    patch_turn_plan()
    assert_contract()
    print("OpenOFC v5.4.2B partial reconnect patch applied successfully")


if __name__ == "__main__":
    main()
