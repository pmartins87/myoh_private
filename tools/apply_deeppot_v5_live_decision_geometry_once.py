from pathlib import Path

path = Path("DLLs/User_DLL/deeppot_userdll_failsoft.cpp")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "// DeepPot OpenHoldem user.dll adapter — fail-soft recovery v3",
    "// DeepPot OpenHoldem user.dll adapter — fail-soft recovery v5",
    1,
)
old_version = 'const char* kAdapterVersion = "failsoft-v4-anchor-evidence-20260909";'
new_version = 'const char* kAdapterVersion = "failsoft-v5-live-decision-geometry-20260909";'
if old_version in text:
    text = text.replace(old_version, new_version, 1)
elif new_version not in text:
    raise SystemExit("adapter version marker not found")

helper = r'''bool StrongLiveDecisionGeometry(const deeppot_runtime::LiveScrapeSnapshot& s) {
  if (!CoherentAnchorSnapshot(s)) return false;
  const std::uint32_t seat_mask = SeatMask(s.nchairs);
  const std::uint32_t dealt = s.playersdealtbits & seat_mask;
  const std::uint32_t playing = s.playersplayingbits & seat_mask;
  const std::uint32_t folded = s.foldbits2 & seat_mask;
  const std::uint32_t hero_bit = static_cast<std::uint32_t>(1) << s.userchair;
  if ((playing & ~dealt) != 0 || (folded & ~dealt) != 0) return false;
  if ((playing & folded) != 0) return false;
  if ((playing | folded) != dealt) return false;
  if ((playing & hero_bit) == 0 || (folded & hero_bit) != 0) return false;
  return true;
}

'''
if "bool StrongLiveDecisionGeometry(" not in text:
    marker = "void ApplyHandAnchor(\n"
    if marker not in text:
        raise SystemExit("ApplyHandAnchor marker not found")
    text = text.replace(marker, helper + marker, 1)

old_sig = r'''void ApplyHandAnchor(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {'''
new_sig = r'''void ApplyHandAnchor(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons,
    bool prefer_current_geometry) {'''
if old_sig in text:
    text = text.replace(old_sig, new_sig, 1)
elif new_sig not in text:
    raise SystemExit("ApplyHandAnchor signature not found")

needle = "  const std::uint32_t anchored_dealt = a.playersdealtbits & SeatMask(a.nchairs);\n\n"
insert = r'''  const std::uint32_t anchored_dealt = a.playersdealtbits & SeatMask(a.nchairs);

  // v5: a complete decision-time public snapshot paired with live exact cards
  // outranks an older anchor. The anchor remains recovery evidence only.
  if (prefer_current_geometry && StrongLiveDecisionGeometry(*current)) {
    const std::uint32_t current_dealt = current->playersdealtbits & SeatMask(current->nchairs);
    const bool differs_from_anchor =
        current->nchairs != a.nchairs ||
        current->userchair != a.userchair ||
        current->dealerchair != a.dealerchair ||
        current_dealt != anchored_dealt ||
        current->nplayersdealt != BitCount(anchored_dealt);
    if (differs_from_anchor && reasons) {
      reasons->push_back("live_decision_geometry_preferred_over_anchor");
    }
    return;
  }

'''
if "live_decision_geometry_preferred_over_anchor" not in text:
    if needle not in text:
        raise SystemExit("anchored_dealt insertion point not found")
    text = text.replace(needle, insert, 1)

old_norm = r'''bool NormalizeSnapshotForRecovery(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {
  ApplyHandAnchor(current, reasons);'''
new_norm = r'''bool NormalizeSnapshotForRecovery(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons,
    bool prefer_current_geometry) {
  ApplyHandAnchor(current, reasons, prefer_current_geometry);'''
if old_norm in text:
    text = text.replace(old_norm, new_norm, 1)
elif new_norm not in text:
    raise SystemExit("NormalizeSnapshotForRecovery block not found")

old_decision_call = "NormalizeSnapshotForRecovery(&current, &normalization_reasons);"
new_decision_call = "NormalizeSnapshotForRecovery(&current, &normalization_reasons, !cards_from_cache);"
if old_decision_call in text:
    text = text.replace(old_decision_call, new_decision_call, 1)
elif new_decision_call not in text:
    raise SystemExit("decision normalization call not found")

text = text.replace("ApplyHandAnchor(&historical, NULL);", "ApplyHandAnchor(&historical, NULL, false);")
if "ApplyHandAnchor(current, reasons);" in text or "ApplyHandAnchor(&historical, NULL);" in text:
    raise SystemExit("legacy ApplyHandAnchor call remains")

path.write_text(text, encoding="utf-8")
print("DeepPot v5 live decision geometry patch applied")
