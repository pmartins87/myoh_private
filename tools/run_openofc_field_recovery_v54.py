from __future__ import annotations

import apply_openofc_field_recovery_v54 as v54


_original_replace_once = v54.replace_once


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
    v54.regex_once(rel, pattern, replacement)


v54.replace_once = replace_once_contextual

if __name__ == "__main__":
    v54.main()
