from __future__ import annotations

import unittest

from engine import Board, full_deck, parse_cards
from generate_r3_dealer_corpus import generate_dealer_r3_state
from teacher_search_r3_dealer import (
    BELIEF,
    R3DealerWorld,
    sample_r3_dealer_worlds,
    solve_r3_dealer_sampled_backup,
)


def board(top: str, middle: str, bottom: str) -> Board:
    return Board(parse_cards(top), parse_cards(middle), parse_cards(bottom))


class DealerR3BackupTests(unittest.TestCase):
    def setUp(self) -> None:
        # Dealer has only Bottom capacity.  R3 therefore has exactly three
        # legal actions (one for each discard), keeping the full nested R4
        # information-set test fast without replacing either real teacher.
        self.dealer = board(
            "2c 3c 4c",
            "5c 6c 7c 8c 9c",
            "Tc",
        )
        self.opponent = board(
            "2d 3d",
            "4d 5d 6d 7d",
            "8d 9d Td Jd Qd",
        )
        self.incoming = parse_cards("Jc Qc Kc")
        self.discards = parse_cards("Ac 2h")
        self.world = R3DealerWorld(
            parse_cards("JK1 JK2 3h"),
            parse_cards("4h 5h 6h"),
            parse_cards("7h 8h 9h"),
        )

    def test_one_world_backs_up_every_r3_action_through_both_r4_teachers(self):
        result = solve_r3_dealer_sampled_backup(
            self.dealer,
            self.opponent,
            self.incoming,
            self.discards,
            sample_count=1,
            seed=17,
            worlds=(self.world,),
        )
        self.assertEqual(result.known_count, 25)
        self.assertEqual(result.unseen_count, 29)
        self.assertEqual(result.samples, 1)
        self.assertEqual(result.belief_model, BELIEF)
        self.assertEqual(len(result.all_actions), 3)
        self.assertTrue(result.empirical_robust_best)
        self.assertIsNone(result.certified_unique_best)
        for value in result.all_actions:
            self.assertEqual(value.lower_points_sum, value.lower_mean)
            self.assertEqual(value.upper_points_sum, value.upper_mean)
            self.assertLessEqual(value.lower_mean, value.upper_mean)
            self.assertGreaterEqual(value.observed_min, -103)
            self.assertLessEqual(value.observed_max, 103)

        repeated = solve_r3_dealer_sampled_backup(
            self.dealer,
            self.opponent,
            self.incoming,
            self.discards,
            worlds=(self.world,),
        )
        self.assertEqual(result.all_actions, repeated.all_actions)

    def test_common_random_world_sampler_is_reproducible_and_disjoint(self):
        known = set(
            self.dealer.top + self.dealer.middle + self.dealer.bottom
            + self.opponent.top + self.opponent.middle + self.opponent.bottom
            + self.incoming + self.discards
        )
        unseen = tuple(sorted(set(full_deck(2)) - known))
        first = sample_r3_dealer_worlds(unseen, 8, 20260825)
        second = sample_r3_dealer_worlds(unseen, 8, 20260825)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        for world in first:
            physical = (
                world.opponent_hidden_discards
                + world.opponent_r4_packet
                + world.dealer_r4_packet
            )
            self.assertEqual(len(physical), 9)
            self.assertEqual(len(set(physical)), 9)
            self.assertTrue(set(physical).issubset(set(unseen)))

    def test_information_set_and_hidden_world_validation_fail_closed(self):
        with self.assertRaises(ValueError):
            solve_r3_dealer_sampled_backup(
                self.dealer,
                self.opponent,
                self.incoming,
                parse_cards("Ac 2c"),
                worlds=(self.world,),
            )
        bad_world = R3DealerWorld(
            parse_cards("JK1 JK2 3h"),
            parse_cards("3h 5h 6h"),
            parse_cards("7h 8h 9h"),
        )
        with self.assertRaises(ValueError):
            solve_r3_dealer_sampled_backup(
                self.dealer,
                self.opponent,
                self.incoming,
                self.discards,
                worlds=(bad_world,),
            )

    def test_corpus_row_never_persists_the_sampled_hidden_world(self):
        row = generate_dealer_r3_state(20260825, 700001, 1, 0.01)
        self.assertEqual(row["known_card_count"], 25)
        self.assertEqual(row["unseen_count"], 29)
        self.assertFalse(row["hidden_world_persisted"])
        self.assertEqual(
            row["informative_action_values"],
            row["distinct_action_interval_count"] > 1,
        )
        forbidden = {
            "opponent_hidden_discards",
            "opponent_r3_packet",
            "opponent_r4_packet",
            "dealer_r4_packet",
            "actual_hidden_worlds",
            "sampled_hidden_worlds",
        }
        self.assertTrue(forbidden.isdisjoint(row))
        self.assertEqual(row["legal_action_count"], len(row["action_values"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
