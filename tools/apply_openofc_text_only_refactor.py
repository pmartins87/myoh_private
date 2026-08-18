from pathlib import Path


PATH = Path("OpenHoldem/COFCScraper.cpp")
START = "  RECT rank_rect;"
END = "\n}\n\nstatic bool DeepOFCRegisterKnownCard"

REPLACEMENT = r'''  // Standard OpenOFC cards are decoded exclusively by TableMap text
  // transforms. Reuse the mature OpenHoldem rank/suit primitive so the OFC
  // runtime consumes exactly the same Tn transform results as OpenScrape.
  // Native pixel recognition remains reserved for the isolated Fantasy route.
  const int tablemap_card = ScrapeCardByRankAndSuit(base_name);
  if ((tablemap_card >= 0) && (tablemap_card <= 51)) {
    card->value = tablemap_card;
    DeepOFCLogSlot(base_name, "TABLEMAP_TEXT", card->value,
      CString(""), CString(""), empty, back, joker1, joker2,
      "shared=ScrapeCardByRankAndSuit");
    return 1;
  }

  // On failure, evaluate the exact text-transform outputs once more only for
  // diagnostics. This path never substitutes OCR or a native pixel guess.
  CString rank_result;
  CString suit_result;
  const bool suit_evaluated = EvaluateRegion(suit_region, &suit_result);
  const bool suit_valid = suit_evaluated && IsSuitString(suit_result);
  bool rank_evaluated = false;
  bool rank_valid = false;
  if (suit_valid) {
    rank_evaluated = EvaluateRegion(rank_region, &rank_result);
    rank_valid = rank_evaluated && IsRankString(rank_result);
  }

  std::ostringstream failure_detail;
  failure_detail
    << "suit_eval=" << (suit_evaluated ? 1 : 0)
    << " suit_valid=" << (suit_valid ? 1 : 0)
    << " rank_eval=" << (rank_evaluated ? 1 : 0)
    << " rank_valid=" << (rank_valid ? 1 : 0)
    << " shared=ScrapeCardByRankAndSuit";
  DeepOFCLogSlot(base_name, "REJECTED", kOFCCardUnknown,
    rank_result, suit_result, empty, back, joker1, joker2,
    failure_detail.str());
  write_log(k_always_log_errors,
    "[DeepOFC] Non-empty slot rejected by TableMap text transforms: %s "
    "rank=\"%s\" suit=\"%s\"\n",
    base_name.GetString(), rank_result.GetString(), suit_result.GetString());
  return -3;'''


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    if "shared=ScrapeCardByRankAndSuit" in text and "TABLEMAP_TEXT" in text:
        print("OpenOFC standard card path is already text-transform only")
        return 0
    start = text.find(START)
    if start < 0:
        raise SystemExit("start marker not found")
    end = text.find(END, start)
    if end < 0:
        raise SystemExit("end marker not found")
    old = text[start:end]
    required_old_tokens = [
        "DetectPersistentJoker",
        "RecognizeUprightCard",
        "TABLEMAP_OCR",
        "native_error",
    ]
    missing = [token for token in required_old_tokens if token not in old]
    if missing:
        raise SystemExit("unexpected source shape; missing: " + ", ".join(missing))
    new_text = text[:start] + REPLACEMENT + text[end:]
    PATH.write_text(new_text, encoding="utf-8")
    print("Patched COFCScraper::ScrapeOFCSlot to TableMap-text-only standard recognition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
