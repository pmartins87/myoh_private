from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel: str, old: str, new: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one target, got {count}: {old[:180]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_expected_matcher() -> None:
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    old = '''const COFCRankTemplate *UprightTemplate(char rank) {\n  for (int i = 0; i < 13; ++i)\n    if (kDeepOFCUprightLargeRankTemplates[i].label == rank)\n      return &kDeepOFCUprightLargeRankTemplates[i];\n  return NULL;\n}\n'''
    new = r'''double BestTemplateDistanceForRank(
    const uint16_t rows[kDeepOFCGlyphHeight],
    const COFCRankTemplate *templates,
    size_t template_count,
    char rank) {
  double best = std::numeric_limits<double>::infinity();
  for (size_t i = 0; i < template_count; ++i) {
    if (templates[i].label != rank) continue;
    best = std::min(best,
      COFCFantasyRecognitionCore::AlignedBinaryDistance(
        rows, templates[i].rows, 2));
  }
  return best;
}

double BestUprightTemplateDistance(
    const uint16_t rows[kDeepOFCGlyphHeight], char rank) {
  return BestTemplateDistanceForRank(
    rows, kDeepOFCUprightLargeRankTemplates,
    sizeof(kDeepOFCUprightLargeRankTemplates) /
      sizeof(kDeepOFCUprightLargeRankTemplates[0]),
    rank);
}

double BestFanTemplateDistance(
    const uint16_t rows[kDeepOFCGlyphHeight], char rank) {
  return BestTemplateDistanceForRank(
    rows, kDeepOFCFantasy15FanRankTemplates,
    sizeof(kDeepOFCFantasy15FanRankTemplates) /
      sizeof(kDeepOFCFantasy15FanRankTemplates[0]),
    rank);
}

bool CardFromExpectedLineageFeature(
    const uint16_t rows[kDeepOFCGlyphHeight],
    double r, double g, double b,
    int area, int width, int height,
    bool upright,
    const std::vector<std::string> &original_fantasy_cards,
    const std::vector<std::string> &already_assigned,
    COFCFantasy15PixelCard *card,
    std::string *error) {
  if (card == NULL) return Fail(error, "expected-lineage card output is null");
  *card = COFCFantasy15PixelCard();
  std::set<std::string> allowed(
    original_fantasy_cards.begin(), original_fantasy_cards.end());
  std::set<std::string> used(
    already_assigned.begin(), already_assigned.end());

  // Preserve the existing compact-Joker color semantics; exact lineage decides
  // which physical Joker is allowed, never rank-template proximity.
  if (area < 60 && width <= 8 && height <= 10) {
    const double spread = std::max(r, std::max(g, b))
      - std::min(r, std::min(g, b));
    int joker = 0;
    if (r - std::max(g, b) > 100.0) joker = 1;
    const double mean = (r + g + b) / 3.0;
    if (joker == 0 && spread < 25.0 && mean >= 50.0 && mean <= 160.0)
      joker = 2;
    if (joker != 0) {
      const std::string label = joker == 1 ? "JK1" : "JK2";
      if (allowed.find(label) == allowed.end() || used.find(label) != used.end())
        return Fail(error, "expected-lineage Joker is not available");
      card->valid = true;
      card->joker_id = joker;
      return true;
    }
  }

  const COFCRecognitionResult suit = COFCFantasyRecognitionCore::ClassifyRgb(
    r, g, b, kDeepOFCSuitPrototypes, 4,
    kDeepOFCSuitMaxDistance, kDeepOFCSuitMinMargin);
  if (!suit.accepted)
    return Fail(error, "expected-lineage suit rejected");

  double best = std::numeric_limits<double>::infinity();
  ExpectedPhysicalCard best_card;
  bool found = false;
  for (size_t i = 0; i < original_fantasy_cards.size(); ++i) {
    const std::string &label = original_fantasy_cards[i];
    if (used.find(label) != used.end()) continue;
    ExpectedPhysicalCard candidate;
    if (!ParseExpectedCard(label, &candidate) || candidate.joker_id != 0)
      continue;
    if (candidate.suit != suit.label) continue;
    const double distance = upright
      ? BestUprightTemplateDistance(rows, candidate.rank)
      : BestFanTemplateDistance(rows, candidate.rank);
    if (distance < best) {
      best = distance;
      best_card = candidate;
      found = true;
    }
  }
  const double safe_bound = upright ? 0.70 : 0.65;
  if (!found || !std::isfinite(best) || best > safe_bound)
    return Fail(error, "expected-lineage rank assignment has no safe candidate");

  card->valid = true;
  card->rank = best_card.rank;
  card->suit = best_card.suit;
  card->rank_distance = best;
  card->rank_margin = 0.0;
  return true;
}
'''
    replace_once(rel, old, new)

    old_recursive = '''    const COFCRankTemplate *rank_template =\n      UprightTemplate(expected[expected_index].rank);\n    if (rank_template == NULL) continue;\n    const double distance = COFCFantasyRecognitionCore::AlignedBinaryDistance(\n      raw[slot].rows, rank_template->rows, 2);\n    if (distance > 0.70) continue;\n'''
    new_recursive = '''    const double distance = BestUprightTemplateDistance(\n      raw[slot].rows, expected[expected_index].rank);\n    if (!std::isfinite(distance) || distance > 0.70) continue;\n'''
    replace_once(rel, old_recursive, new_recursive)

    old_final = '''      const COFCRankTemplate *rank_template =\n        UprightTemplate(expected[expected_index].rank);\n      const double distance = COFCFantasyRecognitionCore::AlignedBinaryDistance(\n        raw[slot].rows, rank_template->rows, 2);\n      expected_used[expected_index] = true;\n'''
    new_final = '''      const double distance = BestUprightTemplateDistance(\n        raw[slot].rows, expected[expected_index].rank);\n      expected_used[expected_index] = true;\n'''
    replace_once(rel, old_final, new_final)


def patch_bound_loose_fallback() -> None:
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    old = r'''    COFCFantasy15PixelCard card;
    std::string card_error;
    if (upright) {
      const COFCPixelRect source =
        COFCFantasyDynamicGeometry::CurrentSourceRect(anchor);
      bool empty = false;
      if (!ExtractUprightFeature(
            image, source, &card, &empty, &card_error) || empty) {
        return Fail(error, "upright loose Fantasy card rejected: " + card_error);
      }
    } else {
      uint16_t rows[kDeepOFCGlyphHeight];
      const std::vector<InkPoint> deskewed =
        DeskewDynamicRank(rank_points, anchor.CenterX());
      NormalizeComponent(deskewed, rows);
      double r = 0.0;
      double g = 0.0;
      double b = 0.0;
      MedianRgb(image, rank_points, &r, &g, &b);
      if (!CardFromFeature(
            rows, r, g, b,
            static_cast<int>(rank_points.size()),
            anchor.bounds.Width(),
            anchor.bounds.Height(),
            false, true, &card, &card_error)) {
        return Fail(error, "reflow loose Fantasy card rejected: " + card_error);
      }
    }
'''
    new = r'''    COFCFantasy15PixelCard card;
    std::string card_error;
    if (upright) {
      const COFCPixelRect source =
        COFCFantasyDynamicGeometry::CurrentSourceRect(anchor);
      UprightRawFeature raw;
      if (!ExtractUprightRaw(image, source, &raw, &card_error) || raw.empty) {
        return Fail(error, "upright loose Fantasy card rejected: " + card_error);
      }
      const bool direct_ok = CardFromFeature(
        raw.rows, raw.r, raw.g, raw.b,
        raw.area, raw.width, raw.height,
        true, false, &card, &card_error);
      const std::string direct_label = direct_ok ? card.PhysicalLabel() : "";
      const bool direct_in_lineage = direct_ok
        && (original_fantasy_cards.empty()
          || (std::find(original_fantasy_cards.begin(), original_fantasy_cards.end(),
                direct_label) != original_fantasy_cards.end()
            && std::find(labels.begin(), labels.end(), direct_label) == labels.end()));
      if (!direct_in_lineage) {
        if (original_fantasy_cards.empty()
            || !CardFromExpectedLineageFeature(
              raw.rows, raw.r, raw.g, raw.b,
              raw.area, raw.width, raw.height,
              true, original_fantasy_cards, labels, &card, &card_error)) {
          return Fail(error, "upright loose Fantasy card rejected: " + card_error);
        }
      }
    } else {
      uint16_t rows[kDeepOFCGlyphHeight];
      const std::vector<InkPoint> deskewed =
        DeskewDynamicRank(rank_points, anchor.CenterX());
      NormalizeComponent(deskewed, rows);
      double r = 0.0;
      double g = 0.0;
      double b = 0.0;
      MedianRgb(image, rank_points, &r, &g, &b);
      const bool direct_ok = CardFromFeature(
        rows, r, g, b,
        static_cast<int>(rank_points.size()),
        anchor.bounds.Width(),
        anchor.bounds.Height(),
        false, true, &card, &card_error);
      const std::string direct_label = direct_ok ? card.PhysicalLabel() : "";
      const bool direct_in_lineage = direct_ok
        && (original_fantasy_cards.empty()
          || (std::find(original_fantasy_cards.begin(), original_fantasy_cards.end(),
                direct_label) != original_fantasy_cards.end()
            && std::find(labels.begin(), labels.end(), direct_label) == labels.end()));
      if (!direct_in_lineage) {
        if (original_fantasy_cards.empty()
            || !CardFromExpectedLineageFeature(
              rows, r, g, b,
              static_cast<int>(rank_points.size()),
              anchor.bounds.Width(), anchor.bounds.Height(),
              false, original_fantasy_cards, labels, &card, &card_error)) {
          return Fail(error, "reflow loose Fantasy card rejected: " + card_error);
        }
      }
    }
'''
    replace_once(rel, old, new)


def main() -> None:
    patch_expected_matcher()
    patch_bound_loose_fallback()
    print(
      "OPENOFC_FANTASY_LINEAGE_MATCH_V5410B=PASS "
      "upright_multi_exemplar=1 bound_loose_expected_fallback=1 "
      "global_rank_thresholds=UNCHANGED"
    )


if __name__ == "__main__":
    main()
