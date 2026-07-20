from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from orchestrator.aggregate import (
    aggregate_results,
    render_markdown,
    write_publication_outputs,
)
from orchestrator.jsonio import write_json


def result(
    scenario_id: str,
    *,
    outcome_changed: bool,
    used_classification: str,
) -> dict:
    return {
        "scenario_id": scenario_id,
        "family": "test",
        "status": "completed",
        "observation": {"changed": outcome_changed},
        "criteria": {
            "module": {
                "prediction": "changed_or_unknown",
                "classification": "correct_trigger"
                if outcome_changed
                else "conservative_trigger",
            },
            "full_interface": {
                "prediction": "changed_or_unknown",
                "classification": "correct_trigger"
                if outcome_changed
                else "conservative_trigger",
            },
            "used_declarations": {
                "prediction": "unchanged"
                if used_classification in {"unsafe_skip", "correct_skip"}
                else "changed_or_unknown",
                "classification": used_classification,
            },
        },
    }


class AggregateTests(unittest.TestCase):
    def test_rates_keep_absolute_denominators(self) -> None:
        summary = aggregate_results(
            [
                result("a", outcome_changed=True, used_classification="unsafe_skip"),
                result("b", outcome_changed=False, used_classification="correct_skip"),
            ]
        )
        rate = summary["criteria"]["used_declarations"]["unsafe_skip_rate"]
        self.assertEqual(1, rate["numerator"])
        self.assertEqual(2, rate["denominator"])
        self.assertEqual(0.5, rate["value"])
        self.assertIn("50.0% (1/2)", render_markdown(summary))

    def test_csv_names_scenario_and_semantic_status_explicitly(self) -> None:
        value = result(
            "a", outcome_changed=True, used_classification="unsafe_skip"
        )
        value["observation"] = {
            "specification": {"kind": "compile_status", "probe_id": None},
            "before": {"kind": "compile_status", "value": "success"},
            "after": {"kind": "compile_status", "value": "semantic_failure"},
            "changed": True,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run" / "a"
            run.mkdir(parents=True)
            write_json(run / "result.json", value)
            output = root / "publication"
            write_publication_outputs(root / "run", output)
            with (output / "results.csv").open(newline="", encoding="utf-8") as source:
                header = source.readline()
                source.seek(0)
                row = next(csv.DictReader(source, delimiter=";"))

        self.assertIn("scenario_id;family;scenario_status", header)
        self.assertNotIn(",", header)
        self.assertEqual("completed", row["scenario_status"])
        self.assertEqual("compile_status", row["semantic_outcome_kind"])
        self.assertEqual("success", row["outcome_before"])
        self.assertEqual("semantic_failure", row["outcome_after"])


if __name__ == "__main__":
    unittest.main()
