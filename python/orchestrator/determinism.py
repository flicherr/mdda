from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import StandError
from .jsonio import canonical_json, read_json


VOLATILE_FIELDS = frozenset(
    {"started_at", "completed_at", "written_at", "prediction_sha256"}
)


def _without_volatile_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_volatile_fields(item)
            for key, item in value.items()
            if key not in VOLATILE_FIELDS
        }
    if isinstance(value, list):
        return [_without_volatile_fields(item) for item in value]
    return value


def _scenario_directories(root: Path) -> dict[str, Path]:
    values = {
        path.parent.name: path.parent for path in sorted(root.glob("*/result.json"))
    }
    if not values:
        raise StandError(f"no scenario result files in {root}")
    return values


def compare_runs(left: Path, right: Path) -> dict[str, Any]:
    """Compare scientific artifacts while ignoring documented volatile fields."""

    left = left.resolve()
    right = right.resolve()
    left_scenarios = _scenario_directories(left)
    right_scenarios = _scenario_directories(right)
    differences: list[dict[str, str]] = []

    left_ids = set(left_scenarios)
    right_ids = set(right_scenarios)
    for scenario_id in sorted(left_ids - right_ids):
        differences.append({"scenario_id": scenario_id, "artifact": "missing_right"})
    for scenario_id in sorted(right_ids - left_ids):
        differences.append({"scenario_id": scenario_id, "artifact": "missing_left"})

    for scenario_id in sorted(left_ids & right_ids):
        for artifact in ("result.json", "prediction.json"):
            left_path = left_scenarios[scenario_id] / artifact
            right_path = right_scenarios[scenario_id] / artifact
            if left_path.is_file() != right_path.is_file():
                differences.append(
                    {"scenario_id": scenario_id, "artifact": artifact}
                )
                continue
            if not left_path.is_file():
                continue
            left_value = _without_volatile_fields(read_json(left_path))
            right_value = _without_volatile_fields(read_json(right_path))
            if canonical_json(left_value) != canonical_json(right_value):
                differences.append(
                    {"scenario_id": scenario_id, "artifact": artifact}
                )

    return {
        "equal": not differences,
        "left": str(left),
        "right": str(right),
        "scenario_count": len(left_ids & right_ids),
        "volatile_fields_ignored": sorted(VOLATILE_FIELDS),
        "differences": differences,
    }
