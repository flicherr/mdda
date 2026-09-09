from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.criteria import (
    CHANGED_OR_UNKNOWN,
    UNCHANGED,
    classify,
    evaluate_all,
    interface_criterion,
    used_declaration_criterion,
)
from orchestrator.manifest import load_scenario
from orchestrator.matching import (
    DeclarationIndex,
    compare_declarations,
    visible_surface,
)


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = load_scenario(
    ROOT / "scenarios/direct_and_controls/comment_only/scenario.json"
)


def declaration(
    identity: str,
    *,
    module: str = "Provider",
    normalized_value: int = 1,
    exported: bool = True,
) -> dict:
    return {
        "stable_id": identity,
        "usr": identity.removeprefix("usr:"),
        "structural_key": f"key:{identity}",
        "owning_module": module,
        "exported": exported,
        "normalized": {"value": normalized_value},
    }


class MatchingTests(unittest.TestCase):
    def test_usr_match_is_preferred(self) -> None:
        current = declaration("usr:f")
        match = DeclarationIndex([current]).match(declaration("usr:f"))
        self.assertEqual("matched", match["status"])
        self.assertEqual("stable_id", match["method"])

    def test_ambiguity_is_not_resolved_silently(self) -> None:
        first = declaration("usr:a")
        second = declaration("usr:b")
        first["structural_key"] = "shared"
        second["structural_key"] = "shared"
        previous = declaration("usr:missing")
        previous["structural_key"] = "shared"
        match = DeclarationIndex([first, second]).match(previous)
        self.assertEqual("ambiguous", match["status"])

    def test_structural_key_disambiguates_a_usr_collision(self) -> None:
        first = declaration("usr:shared")
        first["structural_key"] = "Provider|Function|f|int ()|0"
        second = declaration("usr:shared")
        second["structural_key"] = "Provider|Function|f|long ()|0"
        previous = declaration("usr:shared")
        previous["structural_key"] = second["structural_key"]
        match = DeclarationIndex([first, second]).match(previous)
        self.assertEqual("matched", match["status"])
        self.assertEqual("stable_id+structural_key", match["method"])

    def test_reexport_surface_follows_only_exported_edges(self) -> None:
        scans = {
            "Base": {
                "declarations": [declaration("usr:base", module="Base")],
                "imports": [],
            },
            "Provider": {
                "declarations": [declaration("usr:provider")],
                "imports": [{"module": "Base", "exported": False}],
            },
        }
        self.assertEqual(
            ["usr:provider"],
            [entry["stable_id"] for entry in visible_surface(scans, "Provider")],
        )
        scans["Provider"]["imports"][0]["exported"] = True
        self.assertEqual(
            ["usr:base", "usr:provider"],
            [entry["stable_id"] for entry in visible_surface(scans, "Provider")],
        )

    def test_fingerprint_mismatch_skips_normalized_comparison(self) -> None:
        previous = declaration("usr:f", normalized_value=1)
        current = declaration("usr:f", normalized_value=2)

        with patch(
            "orchestrator.matching.canonical_json",
            side_effect=AssertionError("normalized representations were compared"),
        ):
            comparison = compare_declarations(previous, current)

        self.assertFalse(comparison["fingerprints_equal"])
        self.assertFalse(comparison["normalized_comparison_performed"])
        self.assertFalse(comparison["equal"])

    def test_fingerprint_match_is_verified_by_normalized_comparison(self) -> None:
        previous = declaration("usr:f", normalized_value=1)
        current = declaration("usr:f", normalized_value=1)

        comparison = compare_declarations(previous, current)

        self.assertTrue(comparison["fingerprints_equal"])
        self.assertTrue(comparison["normalized_comparison_performed"])
        self.assertTrue(comparison["equal"])

    def test_fingerprint_collision_does_not_hide_a_change(self) -> None:
        previous = declaration("usr:f", normalized_value=1)
        current = declaration("usr:f", normalized_value=2)

        with patch(
            "orchestrator.matching.stable_hash",
            return_value="sha256:simulated-collision",
        ):
            comparison = compare_declarations(previous, current)

        self.assertTrue(comparison["fingerprints_equal"])
        self.assertTrue(comparison["normalized_comparison_performed"])
        self.assertFalse(comparison["equal"])


class CriteriaTests(unittest.TestCase):
    def test_used_declaration_equal_is_unchanged(self) -> None:
        previous = declaration("usr:f")
        before_consumer = {"uses": [{"declaration": previous}]}
        after_scans = {
            "Provider": {"declarations": [declaration("usr:f")], "imports": []}
        }
        result = used_declaration_criterion(SCENARIO, before_consumer, after_scans)
        self.assertEqual(UNCHANGED, result["prediction"])

    def test_changed_normalized_declaration_triggers(self) -> None:
        previous = declaration("usr:f", normalized_value=1)
        before_consumer = {"uses": [{"declaration": previous}]}
        after_scans = {
            "Provider": {
                "declarations": [declaration("usr:f", normalized_value=2)],
                "imports": [],
            }
        }
        result = used_declaration_criterion(SCENARIO, before_consumer, after_scans)
        self.assertEqual(CHANGED_OR_UNKNOWN, result["prediction"])

    def test_interface_detects_added_declaration(self) -> None:
        before = {
            "Provider": {"declarations": [declaration("usr:f")], "imports": []}
        }
        after = {
            "Provider": {
                "declarations": [declaration("usr:f"), declaration("usr:g")],
                "imports": [],
            }
        }
        result = interface_criterion(SCENARIO, before, after)
        self.assertEqual(CHANGED_OR_UNKNOWN, result["prediction"])
        self.assertEqual(["usr:g"], result["added"])

    def test_interface_preserves_declarations_with_colliding_usr(self) -> None:
        generic = declaration("usr:overload", normalized_value=1)
        constrained = declaration("usr:overload", normalized_value=2)
        before = {"Provider": {"declarations": [generic], "imports": []}}
        after = {
            "Provider": {
                "declarations": [generic, constrained],
                "imports": [],
            }
        }
        result = interface_criterion(SCENARIO, before, after)
        self.assertEqual(CHANGED_OR_UNKNOWN, result["prediction"])
        self.assertEqual(1, result["before_count"])
        self.assertEqual(2, result["after_count"])
        self.assertEqual(["usr:overload"], result["modified"])

    def test_classification_matrix(self) -> None:
        self.assertEqual("correct_skip", classify(UNCHANGED, False))
        self.assertEqual("unsafe_skip", classify(UNCHANGED, True))
        self.assertEqual(
            "conservative_trigger", classify(CHANGED_OR_UNKNOWN, False)
        )
        self.assertEqual("correct_trigger", classify(CHANGED_OR_UNKNOWN, True))

    def test_predictor_api_cannot_accept_after_consumer(self) -> None:
        parameters = set(inspect.signature(evaluate_all).parameters)
        self.assertNotIn("after_consumer", parameters)
        self.assertEqual(
            {"scenario", "before_scans", "after_scans", "before_consumer"},
            parameters,
        )


if __name__ == "__main__":
    unittest.main()
