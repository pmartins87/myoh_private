from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from run_r3_dealer_shards import (
    MANIFEST_VERSION,
    build_specs,
    sha256_file,
    validate_existing,
)


class DealerR3ScalingTests(unittest.TestCase):
    def test_multi_seed_specs_are_contiguous_and_collision_free(self):
        specs = build_specs(Path("out"), [11, 22], 100, 5, 2)
        self.assertEqual(len(specs), 6)
        self.assertEqual([spec.index for spec in specs], list(range(6)))
        self.assertEqual(
            [(spec.seed, spec.start_deal, spec.attempts) for spec in specs],
            [
                (11, 100, 2), (11, 102, 2), (11, 104, 1),
                (22, 100, 2), (22, 102, 2), (22, 104, 1),
            ],
        )
        self.assertEqual(len({spec.path.name for spec in specs}), len(specs))

    def test_duplicate_seeds_and_invalid_attempts_fail_closed(self):
        with self.assertRaises(ValueError):
            build_specs(Path("out"), [11, 11], 0, 1, 1)
        with self.assertRaises(ValueError):
            build_specs(Path("out"), [11], 0, 0, 1)

    def test_resume_rejects_changed_sample_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            spec = build_specs(Path(temp_dir), [11], 5, 1, 1)[0]
            row = {
                "schema": "openofc-r3-dealer-sampled-backup-v1",
                "base_seed": 11,
                "deal_id": 5,
                "sample_count": 4,
                "confidence_delta": 0.01,
                "informative_action_values": False,
                "certified_unique_best": False,
                "contains_known_joker": False,
                "action_values": [
                    {"opponent_r4_tie_worlds": 0},
                ],
            }
            spec.path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            marker = spec.path.with_suffix(spec.path.suffix + ".done.json")
            meta = {
                "schema": MANIFEST_VERSION,
                "status": "PASS",
                "shard_index": 0,
                "seed_index": 0,
                "base_seed": 11,
                "start_deal": 5,
                "attempts": 1,
                "samples_per_action": 4,
                "confidence_delta": 0.01,
                "records": 1,
                "informative_records": 0,
                "certified_records": 0,
                "known_joker_records": 0,
                "opponent_tie_records": 0,
                "legal_action_world_evaluations": 4,
                "first_key": [11, 5],
                "last_key": [11, 5],
                "sha256": sha256_file(spec.path),
            }
            marker.write_text(json.dumps(meta) + "\n", encoding="utf-8")
            self.assertIsNotNone(validate_existing(spec, 4, 0.01))
            self.assertIsNone(validate_existing(spec, 8, 0.01))
            self.assertIsNone(validate_existing(spec, 4, 0.02))


if __name__ == "__main__":
    unittest.main(verbosity=2)
