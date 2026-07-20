from __future__ import annotations

import unittest

from orchestrator.diagnostics import diagnostic_class, normalized_diagnostic
from orchestrator.model import CommandResult, ObservationSpec
from orchestrator.outcome import extract_outcome, outcomes_equal


def command(returncode: int, stderr: str = "") -> CommandResult:
    return CommandResult(
        argv=("clang++",),
        cwd="/tmp/work",
        returncode=returncode,
        stdout="",
        stderr=stderr,
        duration_ms=1,
    )


class DiagnosticTests(unittest.TestCase):
    def test_ambiguous_diagnostic_class(self) -> None:
        text = "/tmp/x.cpp:7:3: error: call to 'f' is ambiguous"
        self.assertEqual("ambiguous_lookup_or_overload", diagnostic_class(text))
        normalized = normalized_diagnostic(text)
        self.assertNotIn("/tmp/x.cpp", normalized)
        self.assertNotIn(":7:3", normalized)


class OutcomeTests(unittest.TestCase):
    def test_compile_status(self) -> None:
        spec = ObservationSpec(kind="compile_status")
        self.assertEqual(
            "success", extract_outcome(spec, command(0), None)["value"]
        )
        self.assertEqual(
            "semantic_failure", extract_outcome(spec, command(1, "error"), None)["value"]
        )

    def test_probe_selected_declaration(self) -> None:
        spec = ObservationSpec(kind="selected_declaration", probe_id="result")
        analyzer = {
            "probes": [
                {
                    "id": "result",
                    "selected_declaration": {
                        "stable_id": "usr:f",
                        "structural_key": "Provider|Function|f|int ()|0",
                        "normalized": {"return_type": "int", "body": "return 1;"},
                    },
                }
            ]
        }
        outcome = extract_outcome(spec, command(0), analyzer)
        self.assertEqual(
            {
                "kind": "selected_declaration",
                "value": {
                    "stable_id": "usr:f",
                    "structural_key": "Provider|Function|f|int ()|0",
                    "semantic_discriminators": {"return_type": "int"},
                },
            },
            outcome,
        )

    def test_selected_declarations_with_colliding_usr_are_distinct(self) -> None:
        spec = ObservationSpec(kind="selected_declaration", probe_id="result")

        def analyzer(return_type: str, constraint: str | None) -> dict:
            primary_normalized = {}
            if constraint is not None:
                primary_normalized["template_requires"] = constraint
            return {
                "probes": [
                    {
                        "id": "result",
                        "selected_declaration": {
                            "stable_id": "usr:colliding",
                            "structural_key": (
                                f"Provider|Function|serialize|{return_type} ()|0"
                            ),
                            "normalized": {"return_type": return_type},
                            "primary_template": {
                                "stable_id": "usr:template",
                                "structural_key": (
                                    "Provider|FunctionTemplate|serialize||1"
                                ),
                                "normalized": primary_normalized,
                            },
                        },
                    }
                ]
            }

        before = extract_outcome(spec, command(0), analyzer("int", None))
        after = extract_outcome(
            spec,
            command(0),
            analyzer("long", "requires(const T &value) { value.encode(); }"),
        )
        self.assertFalse(outcomes_equal(before, after))

    def test_selected_declaration_body_is_not_part_of_identity(self) -> None:
        spec = ObservationSpec(kind="selected_declaration", probe_id="result")

        def analyzer(body: str) -> dict:
            return {
                "probes": [
                    {
                        "id": "result",
                        "selected_declaration": {
                            "stable_id": "usr:f",
                            "structural_key": "Provider|Function|f|int ()|0",
                            "normalized": {"return_type": "int", "body": body},
                        },
                    }
                ]
            }

        before = extract_outcome(spec, command(0), analyzer("return 1;"))
        after = extract_outcome(spec, command(0), analyzer("return 2;"))
        self.assertTrue(outcomes_equal(before, after))

    def test_equality_uses_kind_and_value(self) -> None:
        self.assertTrue(
            outcomes_equal(
                {"kind": "expression_type", "value": "int"},
                {"kind": "expression_type", "value": "int"},
            )
        )
        self.assertFalse(
            outcomes_equal(
                {"kind": "expression_type", "value": "int"},
                {"kind": "expression_type", "value": "long"},
            )
        )


if __name__ == "__main__":
    unittest.main()
