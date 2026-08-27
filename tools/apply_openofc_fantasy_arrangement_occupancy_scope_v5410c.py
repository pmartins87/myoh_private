from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def save(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one target, got {count}")
    return text.replace(old, new, 1)


def main() -> None:
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    path, text, eol, bom = load(rel)

    # v5.4.10 initially put the bright-substrate gate in ExtractUprightRaw.
    # That helper is also shared by normal incoming-card fallback, so scope the
    # gate to Fantasy *arrangement* slots only and keep normal recognition byte-
    # semantically on the previous path.
    injected = r'''  // OPENOFC_FANTASY_FIELD_V5410: card-face occupancy gate.
  // Field fixtures show a very large separation: empty green slots have 0%
  // bright substrate pixels here, while occupied upright cards are ~65-80%.
  // Use a deliberately low 20% threshold to reject only obvious empty UI.
  int bright_face_pixels = 0;
  int face_pixels = 0;
  for (int y = roi.top; y < roi.bottom; ++y) {
    for (int x = roi.left; x < roi.right; ++x) {
      const Pixel p = image.At(x, y);
      const double mean = (p.r + p.g + p.b) / 3.0;
      if (mean >= 165.0 && std::max(p.r, std::max(p.g, p.b)) >= 175)
        ++bright_face_pixels;
      ++face_pixels;
    }
  }
  if (face_pixels <= 0 || bright_face_pixels * 5 < face_pixels) {
    feature->empty = true;
    return true;
  }

'''
    text = replace_once(text, injected, "", "remove global upright occupancy gate")

    marker = '''bool ExtractUprightRaw(\n    const Image &image,\n'''
    helper = r'''bool HasBrightFantasyCardFace(
    const Image &image,
    const COFCPixelRect &rect) {
  const COFCPixelRect roi(
    rect.left, rect.top,
    std::min(rect.right, rect.left + 27),
    std::min(rect.bottom, rect.top + 47));
  if (!roi.Valid() || roi.left < 0 || roi.top < 0
      || roi.right > image.width || roi.bottom > image.height)
    return false;
  int bright_face_pixels = 0;
  int face_pixels = 0;
  for (int y = roi.top; y < roi.bottom; ++y) {
    for (int x = roi.left; x < roi.right; ++x) {
      const Pixel p = image.At(x, y);
      const double mean = (p.r + p.g + p.b) / 3.0;
      if (mean >= 165.0 && std::max(p.r, std::max(p.g, p.b)) >= 175)
        ++bright_face_pixels;
      ++face_pixels;
    }
  }
  return face_pixels > 0 && bright_face_pixels * 5 >= face_pixels;
}

'''
    text = replace_once(text, marker, helper + marker, "insert Fantasy arrangement brightness helper")

    strict = '''    const RECT &slot = slots[i];\n    const COFCPixelRect rect(slot.left, slot.top, slot.right, slot.bottom);\n    COFCFantasy15PixelCard card;\n    bool empty = false;\n    std::string slot_error;\n    if (!ExtractUprightFeature(image, rect, &card, &empty, &slot_error)) {\n'''
    strict_new = '''    const RECT &slot = slots[i];\n    const COFCPixelRect rect(slot.left, slot.top, slot.right, slot.bottom);\n    COFCFantasy15PixelCard card;\n    bool empty = false;\n    std::string slot_error;\n    if (!HasBrightFantasyCardFace(image, rect)) {\n      occupied->push_back(false);\n      cards->push_back(card);\n      continue;\n    }\n    if (!ExtractUprightFeature(image, rect, &card, &empty, &slot_error)) {\n'''
    text = replace_once(text, strict, strict_new, "scope brightness to strict arrangement slots")

    occupancy_old = r'''  for (size_t i = 0; i < slots.size(); ++i) {
    const RECT &slot = slots[i];
    UprightRawFeature raw;
    if (!ExtractUprightRaw(
          image, COFCPixelRect(slot.left, slot.top, slot.right, slot.bottom),
          &raw, error)) {
      occupied->clear();
      return false;
    }
    occupied->push_back(!raw.empty);
  }
'''
    occupancy_new = r'''  for (size_t i = 0; i < slots.size(); ++i) {
    const RECT &slot = slots[i];
    occupied->push_back(HasBrightFantasyCardFace(
      image, COFCPixelRect(slot.left, slot.top, slot.right, slot.bottom)));
  }
'''
    text = replace_once(text, occupancy_old, occupancy_new, "make occupancy brightness-only")

    expected_old = r'''  for (size_t i = 0; i < slots.size(); ++i) {
    const RECT &slot = slots[i];
    if (!ExtractUprightRaw(
          image, COFCPixelRect(slot.left, slot.top, slot.right, slot.bottom),
          &raw[i], error)) {
      occupied->clear();
      cards->clear();
      return false;
    }
    occupied->push_back(!raw[i].empty);
    if (!raw[i].empty) ++occupied_count;
  }
'''
    expected_new = r'''  for (size_t i = 0; i < slots.size(); ++i) {
    const RECT &slot = slots[i];
    const COFCPixelRect rect(slot.left, slot.top, slot.right, slot.bottom);
    if (!HasBrightFantasyCardFace(image, rect)) {
      raw[i].empty = true;
      occupied->push_back(false);
      continue;
    }
    if (!ExtractUprightRaw(image, rect, &raw[i], error)) {
      occupied->clear();
      cards->clear();
      return false;
    }
    // Bright card-face substrate is authoritative for arrangement occupancy.
    // Identity still remains fail-closed below.
    raw[i].empty = false;
    occupied->push_back(true);
    ++occupied_count;
  }
'''
    text = replace_once(text, expected_old, expected_new, "scope expected-set occupancy")

    save(path, text, eol, bom)
    print(
      "OPENOFC_FANTASY_ARRANGEMENT_OCCUPANCY_SCOPE_V5410C=PASS "
      "fantasy_arrangement=BRIGHT_FACE_GATE normal_upright=UNCHANGED"
    )


if __name__ == "__main__":
    main()
