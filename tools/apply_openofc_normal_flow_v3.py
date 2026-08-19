from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
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
        raise RuntimeError(f"{rel}: expected one target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_soft_slot_failures():
    rel = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = read_source(rel)
    old = "if (rc < 0) { all_slots_ok = false; continue; }"
    count = text.count(old)
    if count < 4:
        raise RuntimeError(
            f"{rel}: expected at least four strict slot-failure sites after v2, got {count}"
        )
    new = '''if (rc < 0) {
        // OPENOFC_TRANSIENT_SLOT_TOLERANCE: a vacated source rectangle can
        // briefly fail its background/empty transform after a drag. Treat the
        // slot as UNKNOWN for this frame instead of poisoning the entire OFC
        // observation. Decision-critical Hero card completeness is still
        // enforced later by the exact 5/3 incoming-card and 5/8/11/14/17
        // total-dealt contracts, so an unreadable real incoming card cannot
        // authorize a decision.
        write_log(true,
          "[OpenOFC SLOT] transient_unknown=%s tolerated=1\\n",
          base.GetString());
        continue;
      }'''
    text = text.replace(old, new)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: softened {count} slot-failure sites")


def patch_partial_opponent_progression():
    rel = "OpenHoldem/COFCScraper.cpp"
    old = '''    const int opponent_known_board = player->visual_board.CountKnownCards();
    if (opponent_known_board == 0) {
      if (player->hidden_incoming_count != 0
          && player->hidden_incoming_count != 5) {
        write_log(k_always_log_errors,
          "[DeepOFC] Invalid opponent initial hidden-incoming count: p=%d backs=%d\\n",
          p, player->hidden_incoming_count);
        all_slots_ok = false;
      }
      player->hidden_discard_count = 0;
    } else if (opponent_known_board >= 5 && opponent_known_board <= 13
        && ((opponent_known_board - 5) % 2 == 0)) {
      player->hidden_discard_count = (opponent_known_board - 5) / 2;
    } else {
      write_log(k_always_log_errors,
        "[DeepOFC] Impossible opponent public-board progression: p=%d known=%d backs=%d\\n",
        p, opponent_known_board, player->hidden_incoming_count);
      all_slots_ok = false;
    }
'''
    new = '''    // OPENOFC_PARTIAL_OPPONENT_PROGRESS: OFC placements are simultaneous.
    // During the opponent animation/public arrangement we can legitimately see
    // 1..4 opening cards or an intermediate 6/8/10/12-card board. Those are
    // observations in progress, not impossible game states. Keep the public
    // cards we actually know and derive only the minimum already-implied hidden
    // discard count. Final dealer-side authority is decided separately from
    // timer/opponent-completion evidence.
    const int opponent_known_board = player->visual_board.CountKnownCards();
    if (opponent_known_board < 0 || opponent_known_board > 13) {
      write_log(k_always_log_errors,
        "[OpenOFC OPPONENT] impossible_public=%d p=%d backs=%d\\n",
        opponent_known_board, p, player->hidden_incoming_count);
      all_slots_ok = false;
    } else {
      player->hidden_discard_count = opponent_known_board <= 5
        ? 0 : (opponent_known_board - 5) / 2;
      const bool stable_public_boundary = opponent_known_board == 0
        || (opponent_known_board >= 5
            && ((opponent_known_board - 5) % 2 == 0));
      if (!stable_public_boundary) {
        write_log(true,
          "[OpenOFC OPPONENT] partial_public=%d p=%d tolerated=1 hidden_discards_min=%d\\n",
          opponent_known_board, p, player->hidden_discard_count);
      }
    }
'''
    replace_once(rel, old, new)


def patch_contract_v3():
    replace_once(
        "OpenHoldem/CHeartbeatThread.cpp",
        "const int kOpenOFCContractVersion = 2;\n",
        "const int kOpenOFCContractVersion = 3;\n",
    )


def patch_confirm_deadline_trace():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    old = '''  write_log(true,
    "[DeepOFC CONFIRM] sending region=%s rect=(%ld,%ld,%ld,%ld) round=%d fantasy=%d\\n",
    region.GetString(), rect.left, rect.top, rect.right, rect.bottom,
    state.round_index, state.players[state.hero_chair].fantasy ? 1 : 0);
'''
    new = '''  write_log(true,
    "[OpenOFC DEADLINE] confirm_ready=1 finalizable=%d timer=%d round=%d fantasy=%d\\n",
    state.decision_finalizable ? 1 : 0,
    state.hero_timer_active ? 1 : 0,
    state.round_index, state.players[state.hero_chair].fantasy ? 1 : 0);
  write_log(true,
    "[DeepOFC CONFIRM] sending region=%s rect=(%ld,%ld,%ld,%ld) round=%d fantasy=%d\\n",
    region.GetString(), rect.left, rect.top, rect.right, rect.bottom,
    state.round_index, state.players[state.hero_chair].fantasy ? 1 : 0);
'''
    replace_once(rel, old, new)


def main():
    patch_soft_slot_failures()
    patch_partial_opponent_progression()
    patch_contract_v3()
    patch_confirm_deadline_trace()
    print("OpenOFC normal-flow v3 repair applied successfully")


if __name__ == "__main__":
    main()
