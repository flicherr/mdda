from __future__ import annotations

from typing import Any

from .diagnostics import diagnostic_class, normalized_diagnostic
from .errors import AnalyzerOutputError
from .model import CommandResult, ObservationSpec


_SELECTION_NORMALIZED_FIELDS = (
    "canonical_type",
    "return_type",
    "template_arguments",
    "template_requires",
    "trailing_requires",
    "constraint_expression",
    "deduced_template",
)


def _selection_identity(record: dict[str, Any]) -> dict[str, Any]:
    """Return declaration data that identifies a selection, not its body."""

    identity = {
        key: record[key]
        for key in ("stable_id", "structural_key")
        if record.get(key) is not None
    }
    normalized = record.get("normalized")
    if isinstance(normalized, dict):
        discriminators = {
            key: normalized[key]
            for key in _SELECTION_NORMALIZED_FIELDS
            if key in normalized
        }
        if discriminators:
            identity["semantic_discriminators"] = discriminators

    primary = record.get("primary_template")
    if isinstance(primary, dict):
        identity["primary_template"] = _selection_identity(primary)
    return identity


def _compile_state(result: CommandResult) -> str:
    return "success" if result.returncode == 0 else "semantic_failure"


def extract_outcome(
    observation: ObservationSpec,
    compile_result: CommandResult,
    analyzer_output: dict[str, Any] | None,
) -> dict[str, Any]:
    compile_state = _compile_state(compile_result)
    if observation.kind in {"compile_status", "name_reachability"}:
        return {"kind": observation.kind, "value": compile_state}
    if observation.kind == "diagnostic_class":
        return {
            "kind": observation.kind,
            "value": "none"
            if compile_state == "success"
            else diagnostic_class(compile_result.stderr),
            "diagnostic": normalized_diagnostic(compile_result.stderr),
        }

    if compile_state != "success":
        return {
            "kind": observation.kind,
            "value": None,
            "availability": "semantic_failure",
            "diagnostic_class": diagnostic_class(compile_result.stderr),
            "diagnostic": normalized_diagnostic(compile_result.stderr),
        }
    if analyzer_output is None:
        raise AnalyzerOutputError("successful compilation has no analyzer output")

    probes = analyzer_output.get("probes", [])
    probe = next(
        (
            value
            for value in probes
            if isinstance(value, dict) and value.get("id") == observation.probe_id
        ),
        None,
    )
    if probe is None:
        raise AnalyzerOutputError(
            f"probe {observation.probe_id!r} was not found in analyzer output"
        )

    if observation.kind == "selected_declaration":
        selected = probe.get("selected_declaration")
        value = _selection_identity(selected) if isinstance(selected, dict) else None
        if value == {}:
            value = None
    elif observation.kind == "selected_specialization":
        selected = probe.get("selected_specialization")
        value = _selection_identity(selected) if isinstance(selected, dict) else None
        if value == {}:
            value = None
    elif observation.kind == "expression_type":
        value = probe.get("expression_type")
    elif observation.kind == "deduced_type":
        value = probe.get("deduced_type")
    elif observation.kind == "constraint_result":
        value = probe.get("constant_value")
    else:
        raise AnalyzerOutputError(f"unsupported observation: {observation.kind}")

    if value is None:
        raise AnalyzerOutputError(
            f"probe {observation.probe_id!r} has no value for {observation.kind}"
        )
    return {"kind": observation.kind, "value": value}


def outcomes_equal(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return before.get("kind") == after.get("kind") and before.get("value") == after.get(
        "value"
    )
