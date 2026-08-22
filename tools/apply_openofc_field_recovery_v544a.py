from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem" / "COFCState.h"
V544_PATH = ROOT / "tools" / "apply_openofc_field_recovery_v544.py"


def read_script():
    raw = V544_PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return text, eol, bom


def write_script(text, eol, bom):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    V544_PATH.write_bytes(data)


def normalize_state_source():
    raw = PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    one_line = '''  bool IsKnownPhysicalCard() const { return IsKnownStandardCard() || IsJoker(); }
  bool IsCardBack() const { return value == kOFCCardBack; }
'''
    multi_line = '''  bool IsKnownPhysicalCard() const {
    return IsKnownStandardCard() || IsJoker();
  }
  bool IsCardBack() const { return value == kOFCCardBack; }
'''
    if text.count(one_line) == 1:
        text = text.replace(one_line, multi_line, 1)
    elif text.count(multi_line) != 1:
        raise RuntimeError("v5.4.4A could not normalize IsKnownPhysicalCard source shape")

    count_result = '''  int CountKnownCards() const {
    int result = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsKnownPhysicalCard()) ++result;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsKnownPhysicalCard()) ++result;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsKnownPhysicalCard()) ++result;
    return result;
  }
'''
    count_count = '''  int CountKnownCards() const {
    int count = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsKnownPhysicalCard()) ++count;
    return count;
  }
'''
    if text.count(count_result) == 1:
        text = text.replace(count_result, count_count, 1)
    elif text.count(count_count) != 1:
        raise RuntimeError("v5.4.4A could not normalize CountKnownCards source shape")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    PATH.write_bytes(data)


def harden_v544_scraper_patch():
    text, eol, bom = read_script()
    old = '    regex_once(rel, pattern, replacement, "non-empty UNKNOWN remains occupied")\n'
    new = r"""    path, text, eol, bom = read_source(rel)
    function_start = 'int CScraper::ScrapeOFCSlot('
    function_end = '\nstatic bool DeepOFCRegisterKnownCard'
    if text.count(function_start) != 1 or text.count(function_end) != 1:
        raise RuntimeError(
          "non-empty UNKNOWN remains occupied: ScrapeOFCSlot function bounds are not unique")
    start = text.find(function_start)
    end = text.find(function_end, start)
    if end < 0:
        raise RuntimeError(
          "non-empty UNKNOWN remains occupied: ScrapeOFCSlot terminal boundary missing")
    body = text[start:end]
    rejected_marker = 'DeepOFCLogSlot(base_name, "REJECTED", kOFCCardUnknown,'
    rejected_count = body.count(rejected_marker)
    terminal = '    return -3;'
    terminal_count = body.count(terminal)
    if rejected_count != 3 or terminal_count != 3:
        raise RuntimeError(
          f"non-empty UNKNOWN remains occupied: expected 3 identity failures, "
          f"got rejected={rejected_count} return_minus3={terminal_count}")
    body = body.replace(
      rejected_marker,
      'DeepOFCLogSlot(base_name, "UNKNOWN_OCCUPIED", kOFCCardUnknown,')
    body = body.replace(
      terminal,
      '''    // OPENOFC_UNKNOWN_OCCUPIED_V544: the slot was already proven non-empty.
    // Failed rank/suit identity must not erase its physical occupancy.
    card->value = kOFCCardUnknown;
    return 2;''')
    text = text[:start] + body + text[end:]
    write_source(path, text, eol, bom)
    print(
      "patched OpenHoldem/COFCScraper.cpp: 3 non-empty identity failures -> UNKNOWN_OCCUPIED")
"""
    if text.count(old) == 1:
        text = text.replace(old, new, 1)
    elif text.count(new) != 1:
        raise RuntimeError("v5.4.4A could not harden the scraper UNKNOWN patch")
    write_script(text, eol, bom)


def harden_v544_reconstructor_patch():
    text, eol, bom = read_script()

    helper_start = "COFCCard *MutableRowCards(COFCPlayerBoard *board, EOFCRow row, int *count) {\n"
    repair_start = "void RepairCommittedUnknownRows(\n"
    hs = text.find(helper_start)
    if hs >= 0:
        he = text.find(repair_start, hs)
        if he < 0:
            raise RuntimeError("v5.4.4A duplicate MutableRowCards terminal marker missing")
        text = text[:hs] + text[he:]
    elif text.count("OPENOFC_UNKNOWN_LINEAGE_V544") != 1:
        raise RuntimeError("v5.4.4A UNKNOWN helper payload missing")

    old_expected = "      const int expected_commit_count = previous->round_index == 0 ? 5 : 2;\n"
    new_expected = r"""      int expected_commit_count = previous->round_index == 0 ? 5 : 2;
      if (previous->partial_turn_recovery) {
        expected_commit_count = 0;
        for (int i = 0; i < kOFCMaxIncomingCards; ++i)
          if (previous->pending[i].active) ++expected_commit_count;
      }
"""
    if text.count(old_expected) == 1:
        text = text.replace(old_expected, new_expected, 1)
    elif text.count(new_expected) != 1:
        raise RuntimeError("v5.4.4A could not preserve partial reconnect discard count")

    region_start_marker = "    # Replace normal current-incoming set cardinality with known + exactly one\n"
    region_end_marker = "\n\ndef patch_policy_unknown_and_pending_discard():\n"
    rs = text.find(region_start_marker)
    re = text.find(region_end_marker, rs)
    if rs < 0 or re < 0:
        raise RuntimeError("v5.4.4A reconstructor hardening region markers missing")

    hardened = r"""    # OPENOFC_UNKNOWN_PARTIAL_RECONNECT_V544A. Operate on semantic
    # boundaries after v5.4.2B/v5.4.2C/v5.4.3 materialization.
    path, text, eol, bom = read_source(rel)
    normal_start_marker = "  set<int> committed_cards = KnownBoardSet(hero_committed);\n"
    normal_end_marker = "\n  out->schema_version = kOFCStateSchemaVersion;\n"
    if text.count(normal_start_marker) != 1:
        raise RuntimeError(
          "normal incoming UNKNOWN patch: committed-card marker is not unique")
    normal_start = text.find(normal_start_marker)
    normal_end = text.find(normal_end_marker, normal_start)
    if normal_end < 0:
        raise RuntimeError("normal incoming UNKNOWN patch: metadata boundary missing")

    normal_replacement = r'''  set<int> committed_cards = KnownBoardSet(hero_committed);
  set<int> pending_known;
  int pending_unknown = 0;
  vector<pair<int, EOFCRow> > pending;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow row = static_cast<EOFCRow>(r);
    int count = 0;
    const COFCCard *cards = RowCards(hero_visual, row, &count);
    for (int i = 0; i < count; ++i) {
      const int value = cards[i].value;
      if (cards[i].IsKnownPhysicalCard()) {
        if (committed_cards.find(value) != committed_cards.end()) continue;
        if (!pending_known.insert(value).second)
          return Fail(out, error, "duplicate current Hero pending physical card");
        pending.push_back(make_pair(value, row));
      } else if (value == kOFCCardUnknown) {
        ++pending_unknown;
        pending.push_back(make_pair(kOFCCardUnknown, row));
      }
    }
  }

  set<int> loose_known = CardArraySet(
    observation.hero_loose_cards, observation.hero_loose_count);
  const int loose_unknown = UnknownCount(
    observation.hero_loose_cards, observation.hero_loose_count);
  for (set<int>::const_iterator it = pending_known.begin();
       it != pending_known.end(); ++it) {
    if (loose_known.find(*it) != loose_known.end()) {
      return Fail(out, error,
        "same Hero current card is both loose and tentatively placed");
    }
  }
  set<int> current_incoming = pending_known;
  current_incoming.insert(loose_known.begin(), loose_known.end());
  const int current_unknown = pending_unknown + loose_unknown;
  if (current_unknown > 1) {
    return Fail(out, error,
      "normal decision supports at most one UNKNOWN occupied current card");
  }

  if (previous != NULL && previous->valid
      && observation.round_index == previous->round_index) {
    const set<int> old_incoming = CardArraySet(
      previous->hero_incoming, previous->hero_incoming_count);
    const int old_unknown = UnknownCount(
      previous->hero_incoming, previous->hero_incoming_count);
    if (old_incoming != current_incoming || old_unknown != current_unknown) {
      return Fail(out, error,
        "same-round incoming physical set changed outside UNKNOWN lineage repair");
    }
  }

  const bool partial_same_round = previous != NULL && previous->valid
    && previous->partial_turn_recovery
    && observation.round_index == previous->round_index;
  int expected_incoming = observation.round_index == 0 ? 5 : 3;
  if (partial_same_round) expected_incoming = previous->hero_incoming_count;
  const int current_total =
    static_cast<int>(current_incoming.size()) + current_unknown;
  if (current_total != expected_incoming) {
    ostringstream oss;
    oss << "normal round " << observation.round_index << " requires "
        << expected_incoming << " current Hero occupied cards; got "
        << current_total << " (known=" << current_incoming.size()
        << " unknown=" << current_unknown << ")";
    return Fail(out, error, oss.str());
  }'''
    text = text[:normal_start] + normal_replacement + text[normal_end:]

    copy_search_from = normal_start + len(normal_replacement)
    copy_guard = "  if (static_cast<int>(current_incoming.size()) > kOFCMaxIncomingCards) {\n"
    copy_start = text.find(copy_guard, copy_search_from)
    if copy_start < 0:
        raise RuntimeError("normal incoming UNKNOWN patch: canonical copy guard missing")
    copy_terminal = "&out->hero_incoming_count);"
    copy_end = text.find(copy_terminal, copy_start)
    if copy_end < 0:
        raise RuntimeError("normal incoming UNKNOWN patch: canonical copy terminal missing")
    copy_end += len(copy_terminal)
    copy_replacement = r'''  if (static_cast<int>(current_incoming.size()) + current_unknown
      > kOFCMaxIncomingCards) {
    return Fail(out, error, "Hero incoming exceeds storage capacity");
  }
  CopyKnownAndUnknownToCards(
    current_incoming, current_unknown,
    out->hero_incoming, kOFCMaxIncomingCards,
    &out->hero_incoming_count);'''
    text = text[:copy_start] + copy_replacement + text[copy_end:]

    known_guard = "  if (hero_visual.CountKnownCards() != expected_visible) {"
    if text.count(known_guard) != 1:
        raise RuntimeError(
          f"current-screen UNKNOWN bootstrap: expected one visible-count guard, got {text.count(known_guard)}")
    text = text.replace(
      known_guard,
      "  if (hero_visual.CountOccupiedCards() != expected_visible) {",
      1)
    known_report = '        << ", got " << hero_visual.CountKnownCards();'
    if text.count(known_report) != 1:
        raise RuntimeError("current-screen UNKNOWN bootstrap: visible-count report missing")
    text = text.replace(
      known_report,
      '        << ", got " << hero_visual.CountOccupiedCards();',
      1)

    current_old = '''  set<int> current = CardArraySet(
    observation.hero_loose_cards, observation.hero_loose_count);
  if (static_cast<int>(current.size()) != observation.hero_loose_count) {
    return Fail(out, error,
      "current-screen normal recovery requires unique known loose cards");
  }
'''
    current_new = '''  set<int> current = CardArraySet(
    observation.hero_loose_cards, observation.hero_loose_count);
  const int current_unknown = UnknownCount(
    observation.hero_loose_cards, observation.hero_loose_count);
  if (current_unknown > 1
      || static_cast<int>(current.size()) + current_unknown
          != observation.hero_loose_count) {
    return Fail(out, error,
      "current-screen normal recovery requires unique occupied loose cards with at most one UNKNOWN");
  }
'''
    if text.count(current_old) != 1:
        raise RuntimeError(
          f"current-screen UNKNOWN bootstrap: v5.4.2B loose-set block expected 1, got {text.count(current_old)}")
    text = text.replace(current_old, current_new, 1)

    seed_old = '''  CopySortedValuesToCards(
    current, seed.hero_incoming, kOFCMaxIncomingCards,
    &seed.hero_incoming_count);
'''
    seed_new = '''  CopyKnownAndUnknownToCards(
    current, current_unknown,
    seed.hero_incoming, kOFCMaxIncomingCards,
    &seed.hero_incoming_count);
'''
    if text.count(seed_old) != 1:
        raise RuntimeError(
          f"current-screen UNKNOWN bootstrap: seed copy expected 1, got {text.count(seed_old)}")
    text = text.replace(seed_old, seed_new, 1)

    write_source(path, text, eol, bom)
    print("patched OpenHoldem/COFCReconstructor.cpp: UNKNOWN occupancy + partial reconnect preserved")
"""

    text = text[:rs] + hardened + text[re:]
    write_script(text, eol, bom)


def main():
    normalize_state_source()
    harden_v544_scraper_patch()
    harden_v544_reconstructor_patch()
    print("OpenOFC v5.4.4A source normalization/hardening: PASS")


if __name__ == "__main__":
    main()
