from pathlib import Path

path = Path("DLLs/User_DLL/deeppot_userdll_failsoft.cpp")
text = path.read_text(encoding="utf-8")

old_version = 'const char* kAdapterVersion = "failsoft-v3-action-history-20260909";'
new_version = 'const char* kAdapterVersion = "failsoft-v4-anchor-evidence-20260909";'
if old_version in text:
    text = text.replace(old_version, new_version, 1)
elif new_version not in text:
    raise SystemExit("adapter version marker not found")

old = r'''void ApplyHandAnchor(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {
  if (!g_hand.have_anchor) return;

  const deeppot_runtime::LiveScrapeSnapshot& a = g_hand.anchor;
  if (current->nchairs != a.nchairs) {
    current->nchairs = a.nchairs;
    if (reasons) reasons->push_back("nchairs_from_hand_anchor");
  }
  if (current->userchair != a.userchair) {
    current->userchair = a.userchair;
    if (reasons) reasons->push_back("userchair_from_hand_anchor");
  }
  if (current->dealerchair != a.dealerchair) {
    current->dealerchair = a.dealerchair;
    if (reasons) reasons->push_back("dealer_from_hand_anchor");
  }
  const std::uint32_t anchored_dealt = a.playersdealtbits & SeatMask(a.nchairs);
  if ((current->playersdealtbits & SeatMask(a.nchairs)) != anchored_dealt) {
    current->playersdealtbits = anchored_dealt;
    if (reasons) reasons->push_back("dealt_from_hand_anchor");
  } else {
    current->playersdealtbits = anchored_dealt;
  }
  const int anchored_n = BitCount(anchored_dealt);
  if (current->nplayersdealt != anchored_n) {
    current->nplayersdealt = anchored_n;
    if (reasons) reasons->push_back("nplayersdealt_from_hand_anchor");
  }
}
'''

new = r'''void ApplyHandAnchor(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {
  if (!g_hand.have_anchor) return;

  const deeppot_runtime::LiveScrapeSnapshot& a = g_hand.anchor;
  const std::uint32_t anchored_dealt = a.playersdealtbits & SeatMask(a.nchairs);

  // v4 live-safety rule: if current playing/fold evidence contains a seat that
  // the old frozen anchor says was never dealt, the anchor is incomplete/stale
  // and must not overwrite the live public geometry.
  const std::uint32_t live_action_evidence =
      (current->playersplayingbits | current->foldbits2) & SeatMask(a.nchairs);
  if ((live_action_evidence & ~anchored_dealt) != 0) {
    if (reasons) reasons->push_back("anchor_rejected_by_live_action_evidence");
    return;
  }

  if (current->nchairs != a.nchairs) {
    current->nchairs = a.nchairs;
    if (reasons) reasons->push_back("nchairs_from_hand_anchor");
  }
  if (current->userchair != a.userchair) {
    current->userchair = a.userchair;
    if (reasons) reasons->push_back("userchair_from_hand_anchor");
  }
  if (current->dealerchair != a.dealerchair) {
    current->dealerchair = a.dealerchair;
    if (reasons) reasons->push_back("dealer_from_hand_anchor");
  }
  if ((current->playersdealtbits & SeatMask(a.nchairs)) != anchored_dealt) {
    current->playersdealtbits = anchored_dealt;
    if (reasons) reasons->push_back("dealt_from_hand_anchor");
  } else {
    current->playersdealtbits = anchored_dealt;
  }
  const int anchored_n = BitCount(anchored_dealt);
  if (current->nplayersdealt != anchored_n) {
    current->nplayersdealt = anchored_n;
    if (reasons) reasons->push_back("nplayersdealt_from_hand_anchor");
  }
}
'''

if old in text:
    text = text.replace(old, new, 1)
elif "anchor_rejected_by_live_action_evidence" not in text:
    raise SystemExit("ApplyHandAnchor block not found")

path.write_text(text, encoding="utf-8")
print("DeepPot v4 anchor evidence patch applied")
