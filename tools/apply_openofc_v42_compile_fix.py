from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
raw = path.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig").replace("\r\n", "\n")
eol = "\r\n" if b"\r\n" in raw else "\n"

old = '''write_log(true, "[OpenOFC SESSION] stop_schedule=DISABLED hhmm=%d
", hhmm);'''
new = 'write_log(true, "[OpenOFC SESSION] stop_schedule=DISABLED hhmm=%d\\n", hhmm);'
count = text.count(old)
if count != 1:
    raise RuntimeError(f"expected one malformed v4.2 stop-schedule literal, got {count}")
text = text.replace(old, new, 1)

out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
path.write_bytes(data)
print("OpenOFC v4.2 compile-literal repair applied")
