from __future__ import annotations

import unittest

from engine import Board, ROW_BOTTOM, ROW_MIDDLE, ROW_TOP, full_deck, legal_actions, parse_cards, resolve_board, score_heads_up
from teacher_search_nondealer import _score_points_from_resolved, solve_r4_nondealer_uniform_belief


def b(top: str, middle: str, bottom: str) -> Board:
    return Board(parse_cards(top), parse_cards(middle), parse_cards(bottom))


class NonDealerInformationSetContractTests(unittest.TestCase):
    def test_uniform_legal_sampler_is_discard_index_symmetric_for_all_capacity_shapes(self):
        deck = full_deck(2)
        for round_index, before_count in ((1, 5), (2, 7), (3, 9), (4, 11)):
            for top_n in range(4):
                for middle_n in range(6):
                    bottom_n = before_count - top_n - middle_n
                    if bottom_n < 0 or bottom_n > 5:
                        continue
                    cards = iter(deck)
                    board = Board(
                        tuple(next(cards) for _ in range(top_n)),
                        tuple(next(cards) for _ in range(middle_n)),
                        tuple(next(cards) for _ in range(bottom_n)),
                    )
                    incoming = tuple(next(cards) for _ in range(3))
                    actions = legal_actions(board, incoming, round_index)
                    if not actions:
                        continue
                    discard_counts = [
                        sum(1 for action in actions if action.discard_index == idx)
                        for idx in range(3)
                    ]
                    self.assertEqual(
                        discard_counts[0], discard_counts[1],
                        (round_index, top_n, middle_n, bottom_n, discard_counts),
                    )
                    self.assertEqual(
                        discard_counts[1], discard_counts[2],
                        (round_index, top_n, middle_n, bottom_n, discard_counts),
                    )

    def test_cached_terminal_point_projection_matches_canonical_engine(self):
        hero = b("Qc Qd 2h", "2c 3c 4c 5c 6c", "9h Th Jh Qh Kh")
        opp = b("Jc Jd 3h", "4h 5d 6h 7d 8c", "9c Tc Jh Qs Kd")
        self.assertEqual(
            _score_points_from_resolved(resolve_board(hero), resolve_board(opp)),
            score_heads_up(hero, opp).points,
        )
        self.assertEqual(
            _score_points_from_resolved(resolve_board(opp), resolve_board(hero)),
            score_heads_up(opp, hero).points,
        )
        self.assertEqual(score_heads_up(hero, opp).points, -score_heads_up(opp, hero).points)

    def test_exact_uniform_unseen_expectimax_enumerates_all_2600_packets(self):
        # Both Jokers are in Hero's remembered prior discards. That keeps this
        # unit test fast while still exercising the full 54-card information-set
        # accounting and exact 26-choose-3 chance enumeration.
        hero = b("2c 3c", "4c 5c 6c 7c", "8c 9c Tc Jc Qc")
        opp = b("2d 3d", "4d 5d 6d 7d", "8d 9d Td Jd Qd")
        incoming = parse_cards("Kc Ac 2h")
        known_discards = parse_cards("JK1 JK2 3h")

        result = solve_r4_nondealer_uniform_belief(
            hero, opp, incoming, known_discards
        )
        self.assertEqual(result.unseen_count, 26)
        self.assertEqual(result.opponent_packet_count, 2600)
        self.assertEqual(result.best_expected_points_den, 2600)
        self.assertEqual(len(result.all_actions), len(legal_actions(hero, incoming, 4)))
        self.assertEqual(len(result.all_actions), 6)
        self.assertTrue(result.optimal_actions)
        self.assertTrue(all(v.expected_points_den == 2600 for v in result.all_actions))
        self.assertTrue(all(
            v.expected_points_num <= result.best_expected_points_num
            for v in result.all_actions
        ))
        self.assertTrue(all(v.packet_min_points <= v.packet_max_points for v in result.all_actions))

    def test_information_set_rejects_duplicate_or_missing_private_discard_memory(self):
        hero = b("2c 3c", "4c 5c 6c 7c", "8c 9c Tc Jc Qc")
        opp = b("2d 3d", "4d 5d 6d 7d", "8d 9d Td Jd Qd")
        incoming = parse_cards("Kc Ac 2h")
        with self.assertRaises(ValueError):
            solve_r4_nondealer_uniform_belief(hero, opp, incoming, parse_cards("JK1 JK2"))
        with self.assertRaises(ValueError):
            solve_r4_nondealer_uniform_belief(
                hero, opp, incoming, parse_cards("JK1 JK2 2c")
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
