from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem" / "COFCFantasy15PixelRecognizer.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one target, got {count}")
    return text.replace(old, new, 1)


def main():
    raw = PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    old = '''  // Recovered narrow rank+suit columns deliberately split one connected
  // component into an upper rank anchor and lower suit bounds.
  for (size_t i = 0; i < components.size(); ++i) {
    const COFCPixelRect &candidate = components[i].component.bounds;
    if (candidate.left <= bounds.left && candidate.top <= bounds.top
        && candidate.right >= bounds.right && candidate.bottom >= bounds.bottom) {
      return &components[i];
    }
  }
  return NULL;
'''

    new = '''  // Recovered narrow rank+suit columns deliberately split one connected
  // component into an upper rank anchor and lower suit bounds. Multiple
  // components can geometrically enclose that synthetic anchor (for example a
  // large dark/background-connected component spanning the whole loose-card
  // ROI). Returning the first enclosing box loses physical lineage when that
  // component has no ink inside the synthetic rank bounds. Require actual
  // point overlap and choose the tightest enclosing component instead.
  const InkComponentWithPoints *best = NULL;
  int best_box_area = std::numeric_limits<int>::max();
  for (size_t i = 0; i < components.size(); ++i) {
    const COFCPixelRect &candidate = components[i].component.bounds;
    if (candidate.left > bounds.left || candidate.top > bounds.top
        || candidate.right < bounds.right || candidate.bottom < bounds.bottom) {
      continue;
    }
    bool has_point_inside = false;
    for (size_t p = 0; p < components[i].points.size(); ++p) {
      const InkPoint point = components[i].points[p];
      if (point.x >= bounds.left && point.x < bounds.right
          && point.y >= bounds.top && point.y < bounds.bottom) {
        has_point_inside = true;
        break;
      }
    }
    if (!has_point_inside) continue;
    const int box_area = candidate.Width() * candidate.Height();
    if (best == NULL || box_area < best_box_area) {
      best = &components[i];
      best_box_area = box_area;
    }
  }
  return best;
'''

    text = replace_once(text, old, new, "dynamic component lineage fallback")
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    PATH.write_bytes(data)
    print("applied OpenOFC v5.4.3F dynamic component-lineage fix")


if __name__ == "__main__":
    main()
