from __future__ import annotations

import unittest

from engine import (
    Board, CAT_FLUSH, CAT_FULL_HOUSE, CAT_PAIR, CAT_QUADS, CAT_STRAIGHT,
    CAT_STRAIGHT_FLUSH, CAT_TRIPS, ROW_BOTTOM, ROW_MIDDLE, ROW_TOP,
    HandRank, card_from_runtime_value, fantasy_award_from_top, legal_actions,
    parse_cards, resolve_board, royalty, score_heads_up,
)
from teacher_search import solve_r4_exact


def b(top: str, middle: str, bottom: str) -> Board:
    return Board(parse_cards(top), parse_cards(middle), parse_cards(bottom))


class RuleContractTests(unittest.TestCase):
    def test_royalty_table(self):
        self.assertEqual(royalty(HandRank(CAT_PAIR, (6, 14)), ROW_TOP), 1)
        self.assertEqual(royalty(HandRank(CAT_PAIR, (14, 13)), ROW_TOP), 9)
        self.assertEqual(royalty(HandRank(CAT_TRIPS, (2,)), ROW_TOP), 10)
        self.assertEqual(royalty(HandRank(CAT_TRIPS, (14,)), ROW_TOP), 22)
        self.assertEqual(royalty(HandRank(CAT_TRIPS, (8, 7, 2)), ROW_MIDDLE), 2)
        self.assertEqual(royalty(HandRank(CAT_STRAIGHT, (9,)), ROW_MIDDLE), 4)
        self.assertEqual(royalty(HandRank(CAT_FLUSH, (14, 9, 8, 4, 2)), ROW_MIDDLE), 8)
        self.assertEqual(royalty(HandRank(CAT_FULL_HOUSE, (10, 7)), ROW_MIDDLE), 12)
        self.assertEqual(royalty(HandRank(CAT_QUADS, (9, 2)), ROW_MIDDLE), 20)
        self.assertEqual(royalty(HandRank(CAT_STRAIGHT_FLUSH, (9,)), ROW_MIDDLE), 30)
        self.assertEqual(royalty(HandRank(CAT_STRAIGHT_FLUSH, (14,), True), ROW_MIDDLE), 50)
        self.assertEqual(royalty(HandRank(CAT_STRAIGHT, (9,)), ROW_BOTTOM), 2)
        self.assertEqual(royalty(HandRank(CAT_FLUSH, (14, 9, 8, 4, 2)), ROW_BOTTOM), 4)
        self.assertEqual(royalty(HandRank(CAT_FULL_HOUSE, (10, 7)), ROW_BOTTOM), 6)
        self.assertEqual(royalty(HandRank(CAT_QUADS, (9, 2)), ROW_BOTTOM), 10)
        self.assertEqual(royalty(HandRank(CAT_STRAIGHT_FLUSH, (9,)), ROW_BOTTOM), 15)
        self.assertEqual(royalty(HandRank(CAT_STRAIGHT_FLUSH, (14,), True), ROW_BOTTOM), 25)

    def test_runtime_value_mapping(self):
        self.assertEqual(str(card_from_runtime_value(0)), "2h")
        self.assertEqual(str(card_from_runtime_value(12)), "Ah")
        self.assertEqual(str(card_from_runtime_value(13)), "2d")
        self.assertEqual(str(card_from_runtime_value(30)), "6c")
        self.assertEqual(str(card_from_runtime_value(51)), "As")
        self.assertEqual(str(card_from_runtime_value(52)), "JK1")
        self.assertEqual(str(card_from_runtime_value(53)), "JK2")

    def test_ultimate_progressive_fantasy_entry(self):
        self.assertEqual(fantasy_award_from_top(HandRank(CAT_PAIR, (12, 11))), 14)
        self.assertEqual(fantasy_award_from_top(HandRank(CAT_PAIR, (13, 11))), 15)
        self.assertEqual(fantasy_award_from_top(HandRank(CAT_PAIR, (14, 11))), 16)
        self.assertEqual(fantasy_award_from_top(HandRank(CAT_TRIPS, (2,))), 17)

    def test_opening_action_count_from_empty_board(self):
        cards = parse_cards("Ac Kd Qh Js Tc")
        self.assertEqual(len(legal_actions(Board(), cards, 0)), 232)

    def test_later_round_action_count_with_space(self):
        board = b("Ac", "Kd Qd", "2c 3c")
        cards = parse_cards("7h 8h 9h")
        self.assertEqual(len(legal_actions(board, cards, 1)), 27)

    def test_foul_is_detected(self):
        board = b("Ac Ad 2h", "Kc Kd 9h 7s 3c", "2c 3d 4h 5s 6c")
        self.assertIsNone(resolve_board(board))

    def test_scoop_and_royalty_difference(self):
        hero = b("Qc Qd 2h", "2c 3c 4c 5c 6c", "9h Th Jh Qh Kh")
        opp = b("Jc Jd 3h", "4h 5d 6h 7d 8c", "9c Tc Jh Qs Kd")
        res = score_heads_up(hero, opp)
        self.assertIsInstance(res.points, int)

    def test_joker_can_complete_valid_strong_board(self):
        board = b("Ac Ad JK1", "2c 3c 4c 5c 6c", "9h Th Jh Qh Kh")
        resolved = resolve_board(board)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.ranks[0].category, CAT_TRIPS)
        self.assertEqual(resolved.fantasy_cards, 17)


class R4OracleTests(unittest.TestCase):
    def test_live_20260823_exact_label(self):
        hero = b("Td Ks", "2h 3d 6d 2s", "3c 4c 5c 6c 7c")
        opp = b("Qh 8s As", "4h 5h 6h 4d 7d", "Jh Jd Tc Kc Js")
        incoming = parse_cards("Th 6s 7s")
        result = solve_r4_exact(hero, opp, incoming)
        self.assertEqual(result.best_points, 26)
        self.assertEqual(len(result.optimal_actions), 1)
        action = result.optimal_actions[0].action
        self.assertEqual(action.discard_index, 2)
        self.assertEqual(action.placements, ((0, ROW_TOP), (1, ROW_MIDDLE)))

    def test_exact_r4_enumerates_all_legal_actions(self):
        hero = b("Qc Qd", "2c 2d 3h 3s", "4c 5c 6d 7d 8h")
        opp = b("Jc Jd 9s", "4h 5h 6h 7h 8h", "9c Tc Jh Qs Kd")
        incoming = parse_cards("Qh 9d As")
        result = solve_r4_exact(hero, opp, incoming)
        self.assertGreater(len(result.all_actions), 0)
        self.assertTrue(all(v.points <= result.best_points for v in result.all_actions))
        self.assertTrue(result.optimal_actions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
