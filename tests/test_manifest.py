from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from orchestrator.manifest import discover_scenarios


ROOT = Path(__file__).resolve().parents[1]


class ManifestCorpusTests(unittest.TestCase):
    def test_core_corpus_contains_28_scenarios(self) -> None:
        scenarios = discover_scenarios(ROOT / "scenarios")
        self.assertEqual(28, len(scenarios))
        self.assertEqual(
            {
                "direct_and_controls": 5,
                "lookup_overload": 5,
                "adl_conversions": 5,
                "templates_constraints": 5,
                "specializations_guides": 4,
                "reexport_reachability": 4,
            },
            Counter(scenario.family for scenario in scenarios),
        )

    def test_consumers_are_byte_identical(self) -> None:
        for scenario in discover_scenarios(ROOT / "scenarios"):
            with self.subTest(scenario=scenario.scenario_id):
                self.assertEqual(
                    scenario.before.consumer.read_bytes(),
                    scenario.after.consumer.read_bytes(),
                )

    def test_each_scenario_changes_at_least_one_provider_source(self) -> None:
        for scenario in discover_scenarios(ROOT / "scenarios"):
            before = {
                unit.name: unit.source.read_bytes() for unit in scenario.before.modules
            }
            after = {
                unit.name: unit.source.read_bytes() for unit in scenario.after.modules
            }
            with self.subTest(scenario=scenario.scenario_id):
                self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
