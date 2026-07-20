from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import canonical_json, file_hash
from .matching import (
    DeclarationIndex,
    compare_declarations,
    declarations_from_scans,
    visible_surface,
)
from .model import Scenario


UNCHANGED = "unchanged"
CHANGED_OR_UNKNOWN = "changed_or_unknown"


def _source_hashes(scenario: Scenario, state: str) -> dict[str, str]:
    specification = scenario.before if state == "before" else scenario.after
    return {unit.name: file_hash(unit.source) for unit in specification.modules}


def module_criterion(scenario: Scenario) -> dict[str, Any]:
    before = _source_hashes(scenario, "before")
    after = _source_hashes(scenario, "after")
    changed_modules = sorted(name for name in before if before[name] != after[name])
    return {
        "prediction": UNCHANGED if not changed_modules else CHANGED_OR_UNKNOWN,
        "changed_modules": changed_modules,
        "before_hashes": before,
        "after_hashes": after,
    }


def interface_criterion(
    scenario: Scenario,
    before_scans: dict[str, dict[str, Any]],
    after_scans: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_surface = visible_surface(before_scans, scenario.primary_module)
    after_surface = visible_surface(after_scans, scenario.primary_module)

    def normalized_map(values: list[dict[str, Any]]) -> dict[str, Any]:
        buckets: dict[str, list[Any]] = {}
        for declaration in values:
            identity = declaration.get("stable_id") or declaration.get(
                "structural_key"
            )
            if isinstance(identity, str):
                buckets.setdefault(identity, []).append(
                    declaration.get("normalized", {})
                )
        return {
            identity: sorted(values, key=canonical_json)
            for identity, values in sorted(buckets.items())
        }

    before_map = normalized_map(before_surface)
    after_map = normalized_map(after_surface)
    equal = canonical_json(before_map) == canonical_json(after_map)
    return {
        "prediction": UNCHANGED if equal else CHANGED_OR_UNKNOWN,
        "before_count": sum(len(values) for values in before_map.values()),
        "after_count": sum(len(values) for values in after_map.values()),
        "added": sorted(set(after_map) - set(before_map)),
        "removed": sorted(set(before_map) - set(after_map)),
        "modified": sorted(
            identity
            for identity in set(before_map) & set(after_map)
            if canonical_json(before_map[identity]) != canonical_json(after_map[identity])
        ),
    }


def used_declaration_criterion(
    scenario: Scenario,
    before_consumer: dict[str, Any],
    after_scans: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    after_declarations = [
        declaration
        for declaration in declarations_from_scans(after_scans)
        if declaration.get("owning_module") in scenario.tracked_modules
    ]
    index = DeclarationIndex(after_declarations)

    unique_uses: dict[str, dict[str, Any]] = {}
    for use in before_consumer.get("uses", []):
        if not isinstance(use, dict):
            continue
        declaration = use.get("declaration")
        if not isinstance(declaration, dict):
            continue
        if declaration.get("owning_module") not in scenario.tracked_modules:
            continue
        identity = declaration.get("stable_id") or declaration.get("structural_key")
        if isinstance(identity, str):
            deduplication_key = canonical_json(
                {
                    "stable_id": declaration.get("stable_id"),
                    "structural_key": declaration.get("structural_key"),
                    "normalized": declaration.get("normalized", {}),
                }
            )
            unique_uses[deduplication_key] = declaration

    details: list[dict[str, Any]] = []
    safe = True
    for deduplication_key in sorted(unique_uses):
        previous = unique_uses[deduplication_key]
        identity = previous.get("stable_id") or previous.get("structural_key")
        match = index.match(previous)
        detail: dict[str, Any] = {
            "identity": identity,
            "match_status": match["status"],
            "match_method": match.get("method"),
        }
        if match["status"] != "matched":
            safe = False
        else:
            comparison = compare_declarations(previous, match["value"])
            detail.update(comparison)
            if not comparison["equal"]:
                safe = False
        details.append(detail)

    return {
        "prediction": UNCHANGED if safe else CHANGED_OR_UNKNOWN,
        "used_declaration_count": len(unique_uses),
        "details": details,
    }


def evaluate_all(
    scenario: Scenario,
    before_scans: dict[str, dict[str, Any]],
    after_scans: dict[str, dict[str, Any]],
    before_consumer: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate predictors without accepting any after-consumer information."""

    return {
        "schema_version": 1,
        "scenario_id": scenario.scenario_id,
        "oracle_fields_available": False,
        "criteria": {
            "module": module_criterion(scenario),
            "full_interface": interface_criterion(
                scenario, before_scans, after_scans
            ),
            "used_declarations": used_declaration_criterion(
                scenario, before_consumer, after_scans
            ),
        },
    }


def classify(prediction: str, outcome_changed: bool) -> str:
    if prediction == UNCHANGED:
        return "unsafe_skip" if outcome_changed else "correct_skip"
    return "correct_trigger" if outcome_changed else "conservative_trigger"
