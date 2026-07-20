from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator.determinism import compare_runs
from orchestrator.jsonio import write_json


class DeterminismTests(unittest.TestCase):
    def test_volatile_fields_do_not_make_runs_different(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / "left" / "scenario.one"
            right = root / "right" / "scenario.one"
            write_json(
                left / "result.json",
                {
                    "status": "completed",
                    "completed_at": "first",
                    "prediction_sha256": "first-hash",
                    "observation": {"changed": True},
                },
            )
            write_json(
                right / "result.json",
                {
                    "status": "completed",
                    "completed_at": "second",
                    "prediction_sha256": "second-hash",
                    "observation": {"changed": True},
                },
            )
            write_json(left / "prediction.json", {"written_at": "first", "x": 1})
            write_json(
                right / "prediction.json", {"written_at": "second", "x": 1}
            )

            result = compare_runs(root / "left", root / "right")

            self.assertTrue(result["equal"])
            self.assertEqual([], result["differences"])

    def test_scientific_difference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / "left" / "scenario.one"
            right = root / "right" / "scenario.one"
            write_json(left / "result.json", {"observation": {"changed": False}})
            write_json(right / "result.json", {"observation": {"changed": True}})

            result = compare_runs(root / "left", root / "right")

            self.assertFalse(result["equal"])
            self.assertEqual(
                [{"scenario_id": "scenario.one", "artifact": "result.json"}],
                result["differences"],
            )


if __name__ == "__main__":
    unittest.main()
