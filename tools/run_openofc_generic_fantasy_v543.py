from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "tools/apply_openofc_generic_fantasy_v543.py"
text = source.read_text(encoding="utf-8")

old = '''def patch_fantasy_count_contract():
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

new = '''def patch_fantasy_count_contract():
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

if old not in text:
    raise RuntimeError("v5.4.3 wrapper could not find brittle count-contract patch")
text = text.replace(old, new, 1)

temp = ROOT / "tools/_apply_openofc_generic_fantasy_v543_runtime.py"
temp.write_text(text, encoding="utf-8")
try:
    subprocess.run([sys.executable, str(temp)], cwd=str(ROOT), check=True)
finally:
    temp.unlink(missing_ok=True)

print("OpenOFC v5.4.3 resilient patch wrapper applied successfully")
