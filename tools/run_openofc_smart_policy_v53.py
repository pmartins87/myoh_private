from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "tools/apply_openofc_smart_policy_v53.py"
text = source.read_text(encoding="utf-8")
old = '''    if count != 2:\n        raise RuntimeError(f"{rel}: expected two terminal scoring sites, got {count}")\n    text = text.replace(old_terminal, new_terminal)\n'''
new = '''    if count != 1:\n        raise RuntimeError(f"{rel}: expected one strict terminal scoring site, got {count}")\n    text = text.replace(old_terminal, new_terminal, 1)\n'''
if old not in text:
    raise RuntimeError("v5.3 wrapper could not find terminal-scoring patch contract")
text = text.replace(old, new, 1)
temp = ROOT / "tools/_apply_openofc_smart_policy_v53_runtime.py"
temp.write_text(text, encoding="utf-8")
try:
    subprocess.run([sys.executable, str(temp)], cwd=str(ROOT), check=True)
    subprocess.run(
        [sys.executable, str(ROOT / "tools/apply_openofc_smart_policy_v53_forward.py")],
        cwd=str(ROOT), check=True)
    subprocess.run(
        [sys.executable, str(ROOT / "tools/apply_openofc_smart_policy_v53_selftest.py")],
        cwd=str(ROOT), check=True)
finally:
    temp.unlink(missing_ok=True)
print("OpenOFC smart baseline v5.3 wrapper applied successfully")
