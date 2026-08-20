from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def card_label(value: int) -> str:
    if 0 <= value <= 51:
        return RANKS[value % 13] + SUITS[value // 13]
    if value == 52:
        return "JK1"
    if value == 53:
        return "JK2"
    if value == 54:
        return "JK"
    return ""


def known_cards(values: Sequence[int]) -> List[int]:
    return [int(v) for v in values if int(v) >= 0]


def board_sets(board: dict) -> Tuple[Set[int], Dict[int, str]]:
    all_cards: Set[int] = set()
    rows: Dict[int, str] = {}
    for row in ("top", "middle", "bottom"):
        for value in known_cards(board.get(row, [])):
            all_cards.add(value)
            rows[value] = row
    return all_cards, rows


def cards_text(values: Iterable[int]) -> str:
    labels = [card_label(v) for v in sorted(set(int(x) for x in values))]
    return ",".join(x for x in labels if x)


def row_text(board: dict, row: str) -> str:
    return cards_text(known_cards(board.get(row, [])))


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def load_aliases(conn: sqlite3.Connection) -> Dict[str, str]:
    if not table_exists(conn, "PlayerAliases"):
        return {}
    cols = {row[1] for row in conn.execute("PRAGMA table_info(PlayerAliases)")}
    if not {"RawName", "CanonicalID"}.issubset(cols):
        return {}
    return {
        str(raw): str(canon)
        for raw, canon in conn.execute("SELECT RawName, CanonicalID FROM PlayerAliases")
    }


def resolve_actor(raw: str, quality: str, aliases: Dict[str, str]) -> Tuple[str, str]:
    raw = (raw or "").strip()
    quality = (quality or "").strip() or "MISSING"
    if not raw:
        return "UNKNOWN", "MISSING"
    if raw in aliases:
        canon = aliases[raw]
        return canon, "ALIAS" if canon != raw else quality
    return raw, quality


def ensure_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def load_latest_records(jsonl: Path) -> Dict[str, dict]:
    latest: Dict[str, dict] = {}
    with jsonl.open("r", encoding="utf-8-sig") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("schema") != "openofc_opponent_hand_v1":
                continue
            hand_id = str(record.get("hand_id", "")).strip()
            if not hand_id:
                raise ValueError(f"line {line_no}: missing hand_id")
            # Runtime may write REVEAL_EDGE_PARTIAL first and a complete upgrade
            # later. Last writer wins, making the import idempotent.
            latest[hand_id] = record
    return latest


def upsert_audit(
    conn: sqlite3.Connection,
    record: dict,
    actor_id: str,
    name_quality: str,
    status: str,
    reason: str,
) -> None:
    conn.execute(
        """
        INSERT INTO OFCHandAudit
        (HandID, RawName, Actor_ID, NameQuality, HeroChair, OpponentChair,
         DealerChair, HighestRoundSeen, RevealMask, RevealCount,
         HeroResultFantasy, OpponentResultFantasy, ResultFrame, Status, Reason,
         SourceSchema, LastEmittedLocal, Last_Updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(HandID) DO UPDATE SET
          RawName=excluded.RawName,
          Actor_ID=excluded.Actor_ID,
          NameQuality=excluded.NameQuality,
          HeroChair=excluded.HeroChair,
          OpponentChair=excluded.OpponentChair,
          DealerChair=excluded.DealerChair,
          HighestRoundSeen=excluded.HighestRoundSeen,
          RevealMask=excluded.RevealMask,
          RevealCount=excluded.RevealCount,
          HeroResultFantasy=excluded.HeroResultFantasy,
          OpponentResultFantasy=excluded.OpponentResultFantasy,
          ResultFrame=excluded.ResultFrame,
          Status=excluded.Status,
          Reason=excluded.Reason,
          SourceSchema=excluded.SourceSchema,
          LastEmittedLocal=excluded.LastEmittedLocal,
          Last_Updated=CURRENT_TIMESTAMP
        """,
        (
            record["hand_id"],
            str(record.get("opponent_raw_name", "")),
            actor_id,
            name_quality,
            int(record.get("hero_chair", -1)),
            int(record.get("opponent_chair", -1)),
            int(record.get("dealer_chair", -1)),
            int(record.get("highest_round_seen", -1)),
            int(record.get("reveal_mask", 0)),
            int(record.get("reveal_count", 0)),
            int(record.get("hero_result_fantasy", 0)),
            int(record.get("opponent_result_fantasy", 0)),
            str(record.get("result_frame", "")),
            status,
            reason,
            str(record.get("schema", "")),
            str(record.get("emitted_local", "")),
        ),
    )


def reconstruct_actions(record: dict) -> Tuple[List[dict], str, str]:
    rounds = record.get("rounds", [])
    if len(rounds) != 5:
        return [], "BAD_ROUND_ARRAY", f"expected 5 round snapshots, got {len(rounds)}"

    revealed = [int(x) for x in record.get("revealed_discards", [])]
    all_rounds_seen = all(int(r.get("seen", 0)) == 1 for r in rounds)
    all_discards_known = len(revealed) >= 4 and all(v >= 0 for v in revealed[:4])
    source_complete = str(record.get("status", "")) == "COMPLETE_REVEAL"
    hand_base_eligible = all_rounds_seen and all_discards_known and source_complete

    actions: List[dict] = []
    prior_cards: Set[int] = set()
    problems: List[str] = []

    for round_index, snap in enumerate(rounds):
        if int(snap.get("seen", 0)) != 1:
            problems.append(f"R{round_index}_MISSING")
            continue
        board = snap.get("opponent_board", {})
        current_cards, row_by_card = board_sets(board)
        hero_board = snap.get("hero_board", {})

        if round_index == 0:
            added = set(current_cards)
            discard: Optional[int] = None
            round_ok = len(current_cards) == 5
            evidence = "ROUND0_COMPLETE_PUBLIC_BOARD"
            if not round_ok:
                problems.append(f"R0_EXPECTED5_GOT{len(current_cards)}")
        else:
            added = current_cards - prior_cards
            discard = revealed[round_index - 1] if len(revealed) >= round_index else -1
            round_ok = len(added) == 2 and discard >= 0 and discard not in current_cards
            evidence = f"BOARD_DELTA_PLUS_FACEUP_DISCARD_SLOT_{round_index - 1}"
            if len(added) != 2:
                problems.append(f"R{round_index}_ADDED_{len(added)}")
            if discard < 0:
                problems.append(f"R{round_index}_DISCARD_UNKNOWN")
            elif discard in current_cards:
                problems.append(f"R{round_index}_DISCARD_STILL_ON_BOARD")

        incoming = set(added)
        if discard is not None and discard >= 0:
            incoming.add(discard)
        added_top = {c for c in added if row_by_card.get(c) == "top"}
        added_middle = {c for c in added if row_by_card.get(c) == "middle"}
        added_bottom = {c for c in added if row_by_card.get(c) == "bottom"}

        eligible = hand_base_eligible and round_ok
        reason = "OK" if eligible else (
            "HAND_INCOMPLETE" if not hand_base_eligible else "ROUND_RECONSTRUCTION_FAILED"
        )
        actions.append(
            {
                "round": round_index,
                "incoming": cards_text(incoming),
                "added_top": cards_text(added_top),
                "added_middle": cards_text(added_middle),
                "added_bottom": cards_text(added_bottom),
                "discard": "" if discard is None or discard < 0 else card_label(discard),
                "hero_top": row_text(hero_board, "top"),
                "hero_middle": row_text(hero_board, "middle"),
                "hero_bottom": row_text(hero_board, "bottom"),
                "opp_top": row_text(board, "top"),
                "opp_middle": row_text(board, "middle"),
                "opp_bottom": row_text(board, "bottom"),
                "evidence": evidence,
                "eligible": 1 if eligible else 0,
                "eligible_reason": reason,
                "confidence": "HIGH" if eligible else "PARTIAL",
            }
        )
        prior_cards = current_cards

    if len(actions) == 5 and all(a["eligible"] for a in actions):
        return actions, "OK", "five exact round actions reconstructed"
    source_status = str(record.get("status", "")) or "UNRECONSTRUCTED"
    detail = ";".join(problems) if problems else str(record.get("reason", ""))
    return actions, source_status, detail


def import_record(
    conn: sqlite3.Connection,
    record: dict,
    aliases: Dict[str, str],
) -> Tuple[str, int]:
    raw_name = str(record.get("opponent_raw_name", ""))
    actor_id, name_quality = resolve_actor(
        raw_name, str(record.get("name_quality", "")), aliases
    )
    actions, audit_status, audit_reason = reconstruct_actions(record)
    upsert_audit(conn, record, actor_id, name_quality, audit_status, audit_reason)

    hand_id = str(record["hand_id"])
    conn.execute("DELETE FROM OFCReconstructedActions WHERE HandID=?", (hand_id,))
    opponent_chair = int(record.get("opponent_chair", -1))
    dealer_chair = int(record.get("dealer_chair", -1))
    is_dealer = 1 if opponent_chair >= 0 and opponent_chair == dealer_chair else 0
    for action in actions:
        conn.execute(
            """
            INSERT INTO OFCReconstructedActions
            (HandID, Actor_ID, RawName, NameQuality, OpponentChair, DealerChair,
             IsDealer, RoundIndex, IncomingCards, AddedTop, AddedMiddle,
             AddedBottom, DiscardCard, HeroPublicTop, HeroPublicMiddle,
             HeroPublicBottom, OpponentBoardTop, OpponentBoardMiddle,
             OpponentBoardBottom, Evidence, Confidence, ActionStatsEligible,
             StatsEligibleReason, ResultFrame)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hand_id,
                actor_id,
                raw_name,
                name_quality,
                opponent_chair,
                dealer_chair,
                is_dealer,
                action["round"],
                action["incoming"],
                action["added_top"],
                action["added_middle"],
                action["added_bottom"],
                action["discard"],
                action["hero_top"],
                action["hero_middle"],
                action["hero_bottom"],
                action["opp_top"],
                action["opp_middle"],
                action["opp_bottom"],
                action["evidence"],
                action["confidence"],
                action["eligible"],
                action["eligible_reason"],
                str(record.get("result_frame", "")),
            ),
        )
    return audit_status, len(actions)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import OpenOFC opponent reveal/history JSONL into oppdb.db"
    )
    parser.add_argument(
        "--jsonl", default="OpenOFC_Data/opponent_hands.jsonl", help="runtime JSONL outbox"
    )
    parser.add_argument("--db", default="oppdb.db", help="SQLite database")
    parser.add_argument(
        "--schema",
        default=str(Path(__file__).with_name("openofc_opponent_history_schema.sql")),
    )
    args = parser.parse_args()

    jsonl = Path(args.jsonl)
    schema = Path(args.schema)
    if not jsonl.exists():
        raise SystemExit(f"JSONL not found: {jsonl}")
    if not schema.exists():
        raise SystemExit(f"schema not found: {schema}")

    records = load_latest_records(jsonl)
    conn = sqlite3.connect(args.db)
    try:
        ensure_schema(conn, schema)
        aliases = load_aliases(conn)
        status_counts: Dict[str, int] = {}
        action_count = 0
        for hand_id in sorted(records):
            status, n_actions = import_record(conn, records[hand_id], aliases)
            status_counts[status] = status_counts.get(status, 0) + 1
            action_count += n_actions
        conn.commit()
    finally:
        conn.close()

    print(
        f"OpenOFC opponent history import: hands={len(records)} actions={action_count} "
        f"status={status_counts} db={args.db}"
    )


if __name__ == "__main__":
    main()
