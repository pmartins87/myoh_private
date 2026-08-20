from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "tools/apply_openofc_generic_fantasy_v543.py"
text = source.read_text(encoding="utf-8")

old_count = '''def patch_fantasy_count_contract():
    for rel in ("OpenHoldem/COFCVisualObservation.h", "OpenHoldem/COFCState.h"):
        replace_once(
            rel,
            ''' + "'''" + '''    round_index = -1;\\n    hero_can_prepare = false;\\n''' + "'''" + ''',
            ''' + "'''" + '''    round_index = -1;\\n    // OPENOFC_GENERIC_FANTASY_V543: one Fantasy state; count is data.\\n    fantasy_card_count = 0;\\n    hero_can_prepare = false;\\n''' + "'''" + ''')
        replace_once(
            rel,
            ''' + "'''" + '''  int round_index;\\n  bool hero_can_prepare;\\n''' + "'''" + ''',
            ''' + "'''" + '''  int round_index;\\n  // Zero outside Fantasy; 14..17 while Hero is in Fantasy.\\n  int fantasy_card_count;\\n  bool hero_can_prepare;\\n''' + "'''" + ''')
'''
new_count = '''def patch_fantasy_count_contract():
    # v4/v5.4.2 add timer/phase/confidence fields around round_index. Anchor only
    # the stable field itself so the late v5.4.3 patch does not depend on layout.
    for rel in ("OpenHoldem/COFCVisualObservation.h", "OpenHoldem/COFCState.h"):
        replace_once(
            rel,
            ''' + "'''" + '''    round_index = -1;\\n''' + "'''" + ''',
            ''' + "'''" + '''    round_index = -1;\\n    // OPENOFC_GENERIC_FANTASY_V543: one Fantasy state; count is data.\\n    fantasy_card_count = 0;\\n''' + "'''" + ''')
        replace_once(
            rel,
            ''' + "'''" + '''  int round_index;\\n''' + "'''" + ''',
            ''' + "'''" + '''  int round_index;\\n  // Zero outside Fantasy; 14..17 while Hero is in Fantasy.\\n  int fantasy_card_count;\\n''' + "'''" + ''')
'''
if old_count not in text:
    raise RuntimeError("v5.4.3 wrapper could not find brittle count-contract patch")
text = text.replace(old_count, new_count, 1)

pattern = r'''def patch_dynamic_recognizer_unbound_mode\(\):.*?\n\ndef patch_scraper_generic_fantasy\(\):'''
replacement = '''def patch_dynamic_recognizer_unbound_mode():
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    regex_once(
        rel,
        r''' + "'''" + '''!COFCFantasyDynamicGeometry::RequirePhysicalCardLineage\\(\\s*labels,\\s*original_fantasy_cards,\\s*&identity_error\\)''' + "'''" + ''',
        ''' + "'''" + '''(!original_fantasy_cards.empty()\n          && !COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(\n            labels, original_fantasy_cards, &identity_error))''' + "'''" + ''')


def patch_scraper_generic_fantasy():'''
text, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError(f"v5.4.3 wrapper could not replace dynamic recognizer patch: {count}")

log_pattern = r'''    # Runtime-facing raw log now surfaces the generic count explicitly\..*?\n\n    helper_anchor ='''
log_replacement = '''    # Runtime-facing raw log now surfaces the generic count explicitly.
    path, raw_text, raw_eol, raw_bom = read_source(rel)
    format_token = ''' + "'''" + '''"round=%d ''' + "'''" + '''
    if raw_text.count(format_token) != 1:
        raise RuntimeError("DeepOFC raw round log token is not unique")
    raw_text = raw_text.replace(
        format_token, ''' + "'''" + '''"round=%d fantasy_card_count=%d ''' + "'''" + ''', 1)
    arg_pattern = r''' + "'''" + '''obs\\.dealer_chair,\\s*obs\\.acting_chair,\\s*obs\\.round_index,''' + "'''" + '''
    raw_text, arg_count = re.subn(
        arg_pattern,
        ''' + "'''" + '''obs.dealer_chair, obs.acting_chair, obs.round_index,\n    obs.fantasy_card_count,''' + "'''" + ''',
        raw_text, count=1)
    if arg_count != 1:
        raise RuntimeError("DeepOFC raw round argument tuple is not unique")
    write_source(path, raw_text, raw_eol, raw_bom)
    print(f"patched {rel}: generic Fantasy count in raw log")

    helper_anchor ='''
text, log_count = re.subn(log_pattern, lambda _m: log_replacement, text, count=1, flags=re.S)
if log_count != 1:
    raise RuntimeError(f"v5.4.3 wrapper could not replace raw-log patch: {log_count}")

# Later patches leave comments/blank lines between the isolated Fantasy scraper
# and the normal scraper. The semantic boundary is the next function signature,
# not exact whitespace.
old_boundary = r'''bool CScraper::ScrapeOFCFantasyVisualObservation\(int player_count, int hero_chair\) \{.*?\n\}\nbool CScraper::ScrapeOFCVisualObservation\(\) \{'''
new_boundary = r'''bool CScraper::ScrapeOFCFantasyVisualObservation\(int player_count, int hero_chair\) \{.*?\n\}\s*\nbool CScraper::ScrapeOFCVisualObservation\(\) \{'''
if old_boundary not in text:
    raise RuntimeError("v5.4.3 wrapper could not find Fantasy scraper boundary regex")
text = text.replace(old_boundary, new_boundary, 1)

temp = ROOT / "tools/_apply_openofc_generic_fantasy_v543_runtime.py"
temp.write_text(text, encoding="utf-8")
try:
    subprocess.run([sys.executable, str(temp)], cwd=str(ROOT), check=True)
finally:
    temp.unlink(missing_ok=True)

print("OpenOFC v5.4.3 resilient patch wrapper applied successfully")
