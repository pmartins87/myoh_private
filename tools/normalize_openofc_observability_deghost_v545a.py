from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "OpenHoldem" / "COFCScraper.cpp"
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    start_token = "// OPENOFC_EXACT_LINEAGE_DEGHOST_V545"
    end_token = "// OPENOFC_FANTASY_ENTRY_V544."
    start = text.find(start_token)
    end = text.find(end_token, start)
    if start < 0 or end < 0:
        raise RuntimeError("v5.4.5 deghost normalization bounds missing")

    prefix = text[:start]
    block = text[start:end]
    suffix = text[end:]
    count = block.count("kOFCCardEmpty")
    if count != 3:
        raise RuntimeError(
            f"v5.4.5 expected exactly 3 generated kOFCCardEmpty tokens, got {count}"
        )
    block = block.replace("kOFCCardEmpty", "kOFCCardNoCard")
    text = prefix + block + suffix

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)

    check = path.read_text(encoding="utf-8-sig")
    normalized = check[check.find(start_token):check.find(end_token, check.find(start_token))]
    if "kOFCCardEmpty" in normalized or normalized.count("kOFCCardNoCard") < 3:
        raise RuntimeError("v5.4.5 empty-sentinel normalization did not stick")
    print("OpenOFC v5.4.5A deghost empty sentinel normalization: PASS")


if __name__ == "__main__":
    main()
