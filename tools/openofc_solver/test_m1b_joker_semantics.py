from __future__ import annotations

import unittest

from engine import Board, CAT_FLUSH, CAT_PAIR, CAT_TRIPS, parse_cards, resolve_board


def b(top: str, middle: str, bottom: str) -> Board:
    return Board(parse_cards(top), parse_cards(middle), parse_cards(bottom))


class JokerRuleContractTests(unittest.TestCase):
    def test_cross_row_card_identity_may_be_reused_by_joker(self):
        # This is the first two-Joker mismatch isolated by the field-parity gate.
        # The physical 7s are in other rows, but Middle is scored independently;
        # its two Jokers may represent two distinct sevens and make 77.
        board = b(
            "7s 5h 3s",
            "JK1 3h 6h JK2 Jc",
            "9c 7d 2c 7h Ah",
        )
        resolved = resolve_board(board)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.ranks[1].category, CAT_PAIR)
        self.assertEqual(resolved.ranks[1].tie[0], 7)

    def test_cross_row_reuse_can_complete_bottom_trips(self):
        # Second mismatch from the original diagnostic. Eights already appear
        # in Middle, but Bottom's Joker is still free to represent another 8.
        board = b(
            "As Jc Tc",
            "6h 8h 9h 8d JK1",
            "8c 8s 2h JK2 3c",
        )
        resolved = resolve_board(board)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.ranks[2].category, CAT_TRIPS)
        self.assertEqual(resolved.ranks[2].tie[0], 8)

    def test_joker_cannot_duplicate_exact_card_inside_same_flush(self):
        # Traditional poker hand semantics prohibit an impossible double-Ah
        # flush. With Ah already in Middle, JK1 must use another heart. The
        # strongest legal flush is A-K-9-8-5, not A-A-9-8-5.
        board = b(
            "2c 3d 4s",
            "Ah 9h 8h 5h JK1",
            "9c Tc Jc Qc Kc",
        )
        resolved = resolve_board(board)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.ranks[1].category, CAT_FLUSH)
        self.assertEqual(resolved.ranks[1].tie, (14, 13, 9, 8, 5))

    def test_two_jokers_in_same_row_are_distinct_playing_cards(self):
        # Two Jokers may share a rank using different suits, but may not both
        # become the exact same card. Here the best legal heart flush is
        # A-K-Q-9-8.
        board = b(
            "2c 3d 4s",
            "Ah 9h 8h JK1 JK2",
            "9c Tc Jc Qc Kc",
        )
        resolved = resolve_board(board)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.ranks[1].category, CAT_FLUSH)
        self.assertEqual(resolved.ranks[1].tie, (14, 13, 12, 9, 8))


if __name__ == "__main__":
    unittest.main(verbosity=2)
