from __future__ import annotations

import apply_openofc_field_recovery_v54 as v54


_original_replace_once = v54.replace_once
_original_regex_once = v54.regex_once


def replace_once_contextual(rel: str, old: str, new: str):
    recognizer_tail = (
        rel == "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
        and old.startswith("  std::string identity_error;\n")
        and "RequirePhysicalCardLineage" in old
        and "RecognizeUprightCard" in old
    )
    if not recognizer_tail:
        return _original_replace_once(rel, old, new)

    pattern = (
        r"  std::string identity_error;\n"
        r"  if \(!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards\(\n"
        r"        labels, &identity_error\).*?"
        r"  return true;\n"
        r"\}\n\n"
        r"bool COFCFantasy15PixelRecognizer::RecognizeUprightCard\("
    )
    replacement = '''  std::string identity_error;\n  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(\n        labels, &identity_error)) {\n    objects_left_to_right->clear();\n    return Fail(error, identity_error);\n  }\n  if (original_fantasy_cards.empty()) {\n    // OPENOFC_FANTASY_UNBOUND_RECONNECT_V54: used for a fresh attachment or\n    // initial 14..17 fan. Total-card validation remains in the OFC scraper,\n    // where tentative board cards and loose cards can be counted together.\n    return true;\n  }\n  if (!COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(\n        labels, original_fantasy_cards, &identity_error)) {\n    objects_left_to_right->clear();\n    return Fail(error, identity_error);\n  }\n  return true;\n}\n\nbool COFCFantasy15PixelRecognizer::RecognizeUprightCard('''
    _original_regex_once(rel, pattern, replacement)


def _replace_span(rel: str, start_marker: str, end_marker: str, replacement: str):
    path, text, eol, bom = v54.read_source(rel)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{rel}: structural start marker missing: {start_marker[:100]!r}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise RuntimeError(f"{rel}: structural end marker missing: {end_marker[:100]!r}")
    text = text[:start] + replacement + text[end + len(end_marker):]
    v54.write_source(path, text, eol, bom)
    print(f"patched {rel}: structural span")


def regex_once_contextual(rel: str, pattern: str, replacement: str):
    if rel == "OpenHoldem/COFCScraper.cpp" and pattern.startswith(
        "bool CScraper::ScrapeOFCFantasyVisualObservation"
    ):
        _replace_span(
            rel,
            "bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {",
            "bool CScraper::ScrapeOFCVisualObservation() {",
            replacement,
        )
        return

    if rel == "OpenHoldem/COFCScraper.cpp" and "fantasy_active" in pattern:
        _replace_span(
            rel,
            "  // Route Fantasy BEFORE touching normal Hero row/incoming geometry.",
            "  int visible_joker_count = 0;",
            replacement,
        )
        return

    return _original_regex_once(rel, pattern, replacement)


v54.replace_once = replace_once_contextual
v54.regex_once = regex_once_contextual

if __name__ == "__main__":
    v54.main()
