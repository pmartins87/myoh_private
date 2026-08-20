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
        raise RuntimeError(f"{rel}: expected one target, got {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_visual_observation():
    rel = "OpenHoldem/COFCVisualObservation.h"
    replace_once(
        rel,
        """    hidden_incoming_count = 0;\n    hidden_discard_count = 0;\n    board_source_geometry_known = false;\n    visual_board.Reset();\n""",
        """    hidden_incoming_count = 0;\n    hidden_discard_count = 0;\n    raw_name[0] = 0;\n    revealed_discard_mask = 0;\n    revealed_discard_count = 0;\n    for (int i = 0; i < kOFCMaxDiscards; ++i) revealed_discards[i].Clear();\n    board_source_geometry_known = false;\n    visual_board.Reset();\n""",
    )
    replace_once(
        rel,
        """  int hidden_incoming_count;\n  int hidden_discard_count;\n  COFCPlayerBoard visual_board;\n""",
        """  int hidden_incoming_count;\n  int hidden_discard_count;\n\n  // OPENOFC_OPPONENT_HISTORY_V52: passive identity/evidence fields. These are\n  // never canonical action gates. Opponent discards are hidden during play and\n  // are populated only when the result UI turns them face-up.\n  char raw_name[64];\n  COFCCard revealed_discards[kOFCMaxDiscards];\n  int revealed_discard_mask;\n  int revealed_discard_count;\n\n  COFCPlayerBoard visual_board;\n""",
    )


def patch_scraper_passive_evidence():
    rel = "OpenHoldem/COFCScraper.cpp"
    anchor = """  OpenOFCScrapePhaseMarkers(this, obs, player_count, hero_chair);\n\n  // Route Fantasy BEFORE touching normal Hero row/incoming geometry.\n"""
    block = r'''  OpenOFCScrapePhaseMarkers(this, obs, player_count, hero_chair);

  // OPENOFC_OPPONENT_HISTORY_V52: player names and revealed opponent discards
  // are passive evidence. Failure to read either must never poison gameplay.
  for (int p = 0; p < player_count; ++p) {
    CString name_region;
    name_region.Format("ofc_p%d_name", p);
    if (DeepOFCRegionExists(name_region)) {
      CString raw_name;
      if (EvaluateRegion(name_region, &raw_name)) {
        raw_name.Trim();
        if (!raw_name.IsEmpty()) {
          strncpy_s(obs->players[p].raw_name,
            sizeof(obs->players[p].raw_name), raw_name.GetString(), _TRUNCATE);
        }
      }
    }
  }

  // The first face-up discard is the durable end-of-hand evidence edge. Read
  // every available identity, but do not make result/history OCR a state gate.
  if (player_count == 2 && hero_chair >= 0 && hero_chair < 2
      && obs->opponent_result_faceup_discards > 0) {
    const int opponent = 1 - hero_chair;
    COFCVisualPlayerObservation *player = &obs->players[opponent];
    for (int i = 0; i < kOFCMaxDiscards; ++i) {
      CString base;
      base.Format("ofc_p%d_discard%d", opponent, i);
      const CString empty_region = base + "empty";
      const CString back_region = base + "back";
      const CString rank_region = base + "rank";
      if (!DeepOFCRegionExists(empty_region)
          || !DeepOFCRegionExists(back_region)
          || !DeepOFCRegionExists(rank_region)) {
        continue;
      }
      COFCCard discard_face;
      bool back = false;
      int joker_id = 0;
      const int rc = ScrapeOFCSlot(base, &discard_face, &back, &joker_id);
      if (rc > 0 && !back && discard_face.IsKnownPhysicalCard()) {
        player->revealed_discards[i] = discard_face;
        player->revealed_discard_mask |= (1 << i);
      }
    }
    player->revealed_discard_count = 0;
    for (int i = 0; i < kOFCMaxDiscards; ++i) {
      if ((player->revealed_discard_mask & (1 << i)) != 0)
        ++player->revealed_discard_count;
    }
    write_log(true,
      "[OpenOFC HISTORY] reveal_scrape opponent=%d faceup_marker=%d identities=%d mask=0x%X name=\"%s\" passive=1\n",
      opponent, obs->opponent_result_faceup_discards,
      player->revealed_discard_count, player->revealed_discard_mask,
      player->raw_name);
  }

  // Route Fantasy BEFORE touching normal Hero row/incoming geometry.
'''
    replace_once(rel, anchor, block)


def patch_lazy_scraper_history_hook():
    rel = "OpenHoldem/CLazyScraper.cpp"
    replace_once(
        rel,
        '#include "COFCReconstructor.h"\n',
        '#include "COFCReconstructor.h"\n#include "COFCOpponentHistoryRecorder.h"\n',
    )
    replace_once(
        rel,
        'CLazyScraper *p_lazyscraper = NULL;\n',
        '''CLazyScraper *p_lazyscraper = NULL;\n\nnamespace {\nCOFCOpponentHistoryRecorder g_openofc_opponent_history;\n}\n''',
    )

    replace_once(
        rel,
        '''    if (!p_scraper->ScrapeOFCVisualObservation()) {\n      // A drag animation may legitimately produce one ambiguous intermediate\n''',
        '''    if (!p_scraper->ScrapeOFCVisualObservation()) {\n      const COFCVisualObservation *rejected_raw =\n        p_table_state->OFCVisualObservation();\n      if (rejected_raw != NULL\n          && rejected_raw->opponent_result_faceup_discards > 0) {\n        g_openofc_opponent_history.ObserveTerminalReveal(\n          *rejected_raw, previous_state.valid ? &previous_state : NULL);\n      }\n      // A drag animation may legitimately produce one ambiguous intermediate\n''',
    )

    replace_once(
        rel,
        '''    *p_table_state->OFCState() = rebuilt;\n    std::string snapshot = COFCReconstructor::DiagnosticSnapshot(rebuilt);\n''',
        '''    *p_table_state->OFCState() = rebuilt;\n    g_openofc_opponent_history.ObserveCanonical(rebuilt, *raw);\n    std::string snapshot = COFCReconstructor::DiagnosticSnapshot(rebuilt);\n''',
    )


def patch_project():
    replace_once(
        "OpenHoldem/OpenHoldem.vcxproj",
        '    <ClCompile Include="COFCFantasyBatchExecutor.cpp" />\n',
        '    <ClCompile Include="COFCFantasyBatchExecutor.cpp" />\n    <ClCompile Include="COFCOpponentHistoryRecorder.cpp" />\n',
    )


def selftest_sources():
    recorder = (ROOT / "OpenHoldem/COFCOpponentHistoryRecorder.cpp").read_text(
        encoding="utf-8-sig"
    )
    required = [
        "REVEAL_EDGE_PARTIAL",
        "COMPLETE_REVEAL",
        "opponent_hands.jsonl",
        "result_frame_saved=1",
        "round_snapshot=",
    ]
    missing = [x for x in required if x not in recorder]
    if missing:
        raise RuntimeError("opponent history recorder contract missing: " + ", ".join(missing))


def main():
    selftest_sources()
    patch_visual_observation()
    patch_scraper_passive_evidence()
    patch_lazy_scraper_history_hook()
    patch_project()
    print("OpenOFC opponent-history v5.2 runtime patch applied")


if __name__ == "__main__":
    main()
