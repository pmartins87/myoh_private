from __future__ import annotations

import unittest

from generate_r4_dealer_corpus import generate_corpus, generate_dealer_r4_state


class DealerR4CorpusTests(unittest.TestCase):
    def test_single_state_is_exact_information_set(self):
        row = generate_dealer_r4_state(20260823, 0)
        self.assertEqual(row["schema"], "openofc-r4-dealer-exact-v1")
        self.assertEqual(row["position"], "dealer_button_acts_second")
        self.assertEqual(row["information_set"], "opponent_r4_final_public")
        self.assertEqual(sum(len(row["hero_before"][r]) for r in ("top", "middle", "bottom")), 11)
        self.assertEqual(sum(len(row["opponent_final"][r]) for r in ("top", "middle", "bottom")), 13)
        self.assertEqual(len(row["incoming"]), 3)
        self.assertGreater(row["legal_action_count"], 0)
        self.assertEqual(row["legal_action_count"], len(row["action_values"]))
        self.assertTrue(row["point_optimal_actions"])
        self.assertEqual(
            row["best_current_hand_points"],
            max(v["points"] for v in row["action_values"]),
        )
        # The export intentionally contains no opponent private packet/discard
        # or undealt-deck field. A dealer R4 label needs only the public final
        # opponent board, Hero's public board and Hero's own incoming cards.
        forbidden = {"opponent_incoming", "opponent_discard", "deck", "undealt", "hidden_cards"}
        self.assertTrue(forbidden.isdisjoint(row.keys()))
        self.assertEqual(
            row["reachability_sampler"],
            "UNIFORM_LEGAL_REACHABILITY_ONLY_NOT_TEACHER",
        )

    def test_generation_is_deterministic_per_deal_id(self):
        a = generate_dealer_r4_state(987654321, 17)
        b = generate_dealer_r4_state(987654321, 17)
        self.assertEqual(a, b)

    def test_small_corpus_keeps_unique_deal_ids_and_nonfoul_filter(self):
        rows = generate_corpus(20260823, 100, 24, 1, require_nonfoul_option=True)
        self.assertTrue(rows)
        ids = [row["deal_id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(not row["all_actions_foul"] for row in rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
