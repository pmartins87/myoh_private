from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "OPENOFC_FANTASY_FIELD_V546"


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool) -> None:
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, got {count}")
    return text.replace(old, new, 1)


def array_close(text: str, array_name: str) -> int:
    pos = text.find(array_name)
    if pos < 0:
        raise RuntimeError(f"array not found: {array_name}")
    brace = text.find("{", pos)
    if brace < 0:
        raise RuntimeError(f"array opening brace not found: {array_name}")
    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    raise RuntimeError(f"array closing brace not found: {array_name}")


def append_exemplars(
    text: str,
    array_name: str,
    declaration: str,
    entries: str,
    count_name: str,
) -> str:
    if count_name in text:
        raise RuntimeError(f"{array_name} already carries v5.4.6 count marker")
    text = replace_once(
        text,
        declaration,
        declaration.replace("[13]", "[]"),
        f"{array_name} declaration",
    )
    close = array_close(text, array_name)
    insertion = (
        "\n  // {}: supplemental field exemplars. These BROADEN the bank; "
        "the original calibrated exemplars remain intact.\n".format(MARKER)
        + entries
        + "\n"
    )
    text = text[:close] + insertion + text[close:]
    close = array_close(text, array_name)
    semicolon = text.find(";", close)
    if semicolon < 0:
        raise RuntimeError(f"array semicolon not found: {array_name}")
    count_line = (
        f"\nstatic const int {count_name} = "
        f"static_cast<int>(sizeof({array_name}) / sizeof({array_name}[0]));\n"
    )
    return text[:semicolon + 1] + count_line + text[semicolon + 1:]


def patch_banks() -> None:
    rel = "OpenHoldem/COFCFantasyRecognizerBanks.generated.h"
    path, text, eol, bom = read_source(rel)
    if MARKER in text:
        raise RuntimeError(f"{rel} already patched")

    fan_entries = r'''  // K <- field frame000002 14-card fan Kd
  {'K', {0, 0, 0, 0, 0, 896, 480, 504, 446, 412, 440, 1008, 2016, 1504, 32192, 31168, 7616, 8064, 896, 0, 0, 0, 0, 0}},
  // Q <- field frame000002 14-card fan Qd
  {'Q', {0, 0, 0, 96, 248, 766, 942, 798, 1806, 1806, 3342, 3598, 7736, 7672, 8188, 16348, 32760, 31968, 32224, 8160, 2976, 0, 0, 0}},
  // T <- field frame000002 14-card fan Ts
  {'T', {0, 0, 0, 0, 1024, 2816, 7936, 12696, 12700, 12702, 25380, 25376, 25440, 25440, 18016, 31936, 16320, 960, 112, 0, 0, 0, 0, 0}},
  // T <- field frame000002 14-card fan Td
  {'T', {0, 0, 0, 0, 0, 7680, 16128, 15128, 13214, 25022, 25440, 25440, 25440, 25440, 25440, 28384, 32704, 16320, 248, 0, 0, 0, 0, 0}},
  // 8 <- field frame000002 14-card fan 8c
  {'8', {0, 480, 2032, 2040, 4092, 3644, 7224, 7224, 7288, 8184, 4080, 8176, 7288, 6264, 6264, 6264, 7280, 8176, 8128, 8064, 512, 3584, 8064, 0}},
  // 7 <- field frame000002 14-card fan 7s
  {'7', {0, 8188, 8188, 16380, 7196, 7196, 7168, 7168, 7168, 3072, 3840, 3840, 3840, 3840, 3840, 1920, 1920, 1920, 1920, 1920, 960, 960, 960, 0}},
  // 7 <- field frame000002 14-card fan 7c
  {'7', {0, 8184, 8184, 16382, 16382, 15390, 7198, 7168, 7680, 7680, 7680, 3584, 3968, 3968, 1920, 1920, 1920, 1984, 1984, 960, 992, 992, 480, 0}},
  // 7 <- field frame000002 14-card fan 7d
  {'7', {0, 8190, 8190, 16382, 16382, 7198, 7168, 7680, 3584, 3584, 3584, 3968, 3968, 1920, 1984, 960, 960, 960, 992, 480, 480, 496, 96, 0}},
  // 6 <- field frame000002 14-card fan 6d
  {'6', {0, 31744, 31744, 32640, 32704, 2016, 240, 120, 56, 56, 2040, 8190, 8190, 7294, 15422, 15422, 15422, 15390, 7230, 7998, 8184, 2046, 1016, 0}},
  // 3 <- field frame000002 14-card fan 3h
  {'3', {0, 192, 16320, 16320, 32704, 31744, 32256, 3968, 1984, 1984, 4032, 8064, 7680, 7680, 7168, 7182, 3854, 1950, 2044, 1016, 1008, 96, 0, 0}},
  // 3 <- field frame000002 14-card fan 3c
  {'3', {0, 0, 1920, 8128, 32704, 32256, 31744, 32256, 16128, 1984, 4032, 3968, 3584, 7168, 7168, 5646, 3598, 3870, 1982, 2044, 1008, 0, 0, 0}},
  // 3 <- field frame000002 14-card fan 3d
  {'3', {0, 0, 7936, 7936, 28544, 31744, 30720, 32256, 32512, 5888, 3968, 3968, 3584, 7168, 7168, 3598, 3854, 3902, 2046, 988, 248, 0, 0, 0}},
  // 2 <- field frame000002 14-card fan 2s
  {'2', {0, 0, 0, 3584, 16128, 32512, 29440, 28672, 24576, 24576, 28672, 12288, 7936, 4064, 248, 190, 30, 380, 956, 496, 448, 0, 0, 0}},
  // K <- field frame000020 6-card reflow Kc
  {'K', {0, 0, 0, 2048, 3968, 1952, 958, 792, 408, 440, 480, 992, 992, 4064, 5856, 14528, 30912, 31168, 3040, 480, 0, 0, 0, 0}},
  // K <- field frame000020 6-card reflow Kd
  {'K', {0, 0, 0, 2048, 4024, 4030, 1982, 1854, 1840, 1968, 1008, 1008, 2032, 2032, 2016, 7904, 27840, 30912, 31728, 7152, 0, 0, 0, 0}},
  // 7 <- field frame000020 6-card reflow 7c
  {'7', {0, 8184, 8184, 16382, 16382, 7198, 7192, 7168, 7680, 7680, 7680, 3584, 3584, 3968, 3968, 1920, 1920, 1920, 1920, 1984, 1984, 960, 896, 0}},
  // 7 <- field frame000020 6-card reflow 7d
  {'7', {0, 8188, 8188, 16380, 16380, 15388, 7196, 7168, 7936, 7936, 7936, 3840, 3840, 3968, 1920, 1920, 1920, 1984, 1984, 960, 960, 992, 224, 0}},
  // 4 <- field frame000020 6-card reflow 4d
  {'4', {0, 3072, 3072, 16128, 16128, 8064, 8128, 8128, 8160, 8160, 7392, 7408, 7280, 7288, 7422, 32766, 32766, 32760, 16256, 3840, 16320, 16352, 16320, 0}},
  // 2 <- field frame000020 6-card reflow 2h
  {'2', {0, 0, 3840, 16320, 16352, 32736, 30944, 14448, 14336, 15360, 15360, 7680, 7936, 3968, 1984, 992, 496, 1274, 3646, 2046, 2044, 2040, 0, 0}},'''

    upright_entries = r'''  // A <- field frame000020 top0 As
  {'A', {0, 0, 896, 896, 960, 960, 1984, 1984, 1984, 1984, 2016, 4064, 3808, 3808, 3680, 4080, 8176, 8176, 7280, 32510, 32510, 32510, 0, 0}},
  // J <- field frame000020 top1 Jh
  {'J', {0, 16256, 16256, 16320, 16256, 7168, 7168, 7168, 7168, 7168, 7168, 7168, 7168, 7168, 7196, 7196, 7196, 7196, 3900, 3900, 4092, 2032, 992, 0}},
  // T <- field frame000020 top2 Tc
  {'T', {0, 0, 0, 0, 0, 7168, 15928, 32318, 25404, 25392, 25520, 25520, 25520, 25520, 25520, 25392, 25392, 30718, 16126, 0, 0, 0, 0, 0}},
  // Q <- field frame000020 bottom1 Qs
  {'Q', {0, 1984, 1984, 8176, 8176, 14392, 14392, 14392, 14392, 14392, 14392, 14392, 14398, 14590, 15358, 16376, 16376, 16312, 16184, 15480, 32752, 32752, 18368, 0}},
  // Q <- field frame000020 bottom2 Qh
  {'Q', {0, 896, 896, 4064, 8176, 15472, 14392, 14392, 14392, 14392, 14392, 14392, 14392, 14462, 15358, 16376, 16376, 16312, 16184, 15480, 31984, 32752, 28640, 0}},
  // Q <- field frame000020 bottom3 Qd
  {'Q', {0, 0, 384, 384, 4064, 4080, 7920, 7280, 6192, 6192, 6192, 6192, 6200, 6270, 6654, 7160, 8112, 7984, 7792, 16112, 32752, 30688, 0, 0}},
  // 8 <- field frame000020 bottom4 8s
  {'8', {0, 1984, 1984, 8160, 16368, 14448, 14384, 14384, 14448, 14448, 15472, 8160, 8160, 16368, 14448, 14396, 14396, 12348, 14384, 15472, 16368, 8160, 1920, 0}},'''

    text = append_exemplars(
        text,
        "kDeepOFCFantasy15FanRankTemplates",
        "static const COFCRankTemplate kDeepOFCFantasy15FanRankTemplates[13] = {",
        fan_entries,
        "kDeepOFCFantasy15FanRankTemplateCount",
    )
    text = append_exemplars(
        text,
        "kDeepOFCUprightLargeRankTemplates",
        "static const COFCRankTemplate kDeepOFCUprightLargeRankTemplates[13] = {",
        upright_entries,
        "kDeepOFCUprightLargeRankTemplateCount",
    )
    write_source(path, text, eol, bom)
    print(f"patched {rel}: v5.4.6 field exemplar banks")


def patch_recognizer() -> None:
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    path, text, eol, bom = read_source(rel)
    if "// OPENOFC_FANTASY_FIELD_V546: class-level multi-exemplar rank bank." in text:
        raise RuntimeError(f"{rel} already patched")

    old = '''  COFCRecognitionResult rank = COFCFantasyRecognitionCore::ClassifyRank(
    rows,
    upright ? kDeepOFCUprightLargeRankTemplates
            : kDeepOFCFantasy15FanRankTemplates,
    13,
    2,
'''
    new = '''  // OPENOFC_FANTASY_FIELD_V546: class-level multi-exemplar rank bank.
  // ClassifyRank collapses duplicate exemplars to one best distance per rank,
  // so the confidence margin remains rank-vs-rank rather than sample-vs-sample.
  COFCRecognitionResult rank = COFCFantasyRecognitionCore::ClassifyRank(
    rows,
    upright ? kDeepOFCUprightLargeRankTemplates
            : kDeepOFCFantasy15FanRankTemplates,
    upright ? kDeepOFCUprightLargeRankTemplateCount
            : kDeepOFCFantasy15FanRankTemplateCount,
    2,
'''
    text = replace_once(text, old, new, "CardFromFeature template count")

    old_find = '''  // Recovered narrow rank+suit columns deliberately split one connected
  // component into an upper rank anchor and lower suit bounds.
  for (size_t i = 0; i < components.size(); ++i) {
    const COFCPixelRect &candidate = components[i].component.bounds;
    if (candidate.left <= bounds.left && candidate.top <= bounds.top
        && candidate.right >= bounds.right && candidate.bottom >= bounds.bottom) {
      return &components[i];
    }
  }
  return NULL;
}
'''
    new_find = '''  // Recovered narrow rank+suit columns deliberately split one connected
  // component into an upper rank anchor and lower suit bounds.
  //
  // OPENOFC_FANTASY_FIELD_V546: do not return the first broad container.
  // A large connected card/background component can contain the anchor by
  // bounds while contributing zero ink pixels inside it. Choose the containing
  // component with the greatest ACTUAL point overlap; ties prefer the tighter
  // component. If no container contributes ink, fail closed.
  const InkComponentWithPoints *best = NULL;
  int best_overlap = 0;
  int best_bounds_area = std::numeric_limits<int>::max();
  for (size_t i = 0; i < components.size(); ++i) {
    const COFCPixelRect &candidate = components[i].component.bounds;
    if (candidate.left > bounds.left || candidate.top > bounds.top
        || candidate.right < bounds.right || candidate.bottom < bounds.bottom) {
      continue;
    }
    int overlap = 0;
    for (size_t p = 0; p < components[i].points.size(); ++p) {
      const InkPoint &point = components[i].points[p];
      if (point.x >= bounds.left && point.x < bounds.right
          && point.y >= bounds.top && point.y < bounds.bottom) {
        ++overlap;
      }
    }
    const int bounds_area = candidate.Width() * candidate.Height();
    if (overlap > best_overlap
        || (overlap == best_overlap && overlap > 0
            && bounds_area < best_bounds_area)) {
      best = &components[i];
      best_overlap = overlap;
      best_bounds_area = bounds_area;
    }
  }
  return best;
}
'''
    text = replace_once(text, old_find, new_find, "FindComponent fallback")

    write_source(path, text, eol, bom)
    print(f"patched {rel}: multi-exemplar count + overlap-safe split lineage")


def patch_dynamic_geometry() -> None:
    rel = "OpenHoldem/COFCFantasyDynamicGeometry.h"
    path, text, eol, bom = read_source(rel)
    if "OPENOFC_FANTASY_FIELD_V546: lower glyph geometry floor." in text:
        raise RuntimeError(f"{rel} already patched")
    old = '''      for (size_t j = 0; j < components.size(); ++j) {
        const COFCFantasyInkComponent &lower = components[j];
        const double dy = lower.bounds.CenterY() - upper.bounds.CenterY();
'''
    new = '''      for (size_t j = 0; j < components.size(); ++j) {
        const COFCFantasyInkComponent &lower = components[j];
        // OPENOFC_FANTASY_FIELD_V546: lower glyph geometry floor.
        // A one-pixel UI/card-border line underneath a suit used to let that
        // suit impersonate a rank and suppress the true rank in the same x band.
        // Real suit glyphs in the certified/current fixtures are materially
        // taller; reject line noise before rank/suit pairing.
        if (lower.area < 12 || lower.bounds.Width() < 3
            || lower.bounds.Height() < 5) {
          continue;
        }
        const double dy = lower.bounds.CenterY() - upper.bounds.CenterY();
'''
    text = replace_once(text, old, new, "PairRankAnchors lower geometry")
    write_source(path, text, eol, bom)
    print(f"patched {rel}: reject one-pixel lower-line false anchors")


def main() -> None:
    patch_banks()
    patch_recognizer()
    patch_dynamic_geometry()
    print("OPENOFC_FANTASY_FIELD_V546=PATCHED")


if __name__ == "__main__":
    main()
