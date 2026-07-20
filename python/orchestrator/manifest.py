from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .errors import ManifestError
from .model import (
    SUPPORTED_OBSERVATIONS,
    ModuleUnit,
    ObservationSpec,
    Scenario,
    StateSpec,
)


ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def _require_object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{where} must be an object")
    return value


def _require_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{where} must be a non-empty string")
    return value


def _relative_file(root: Path, raw: Any, where: str) -> Path:
    value = _require_string(raw, where)
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManifestError(f"{where} must be a safe relative path")
    resolved = root / relative
    if not resolved.is_file():
        raise ManifestError(f"{where} does not exist: {resolved}")
    return resolved


def _parse_state(root: Path, raw: Any, where: str) -> StateSpec:
    value = _require_object(raw, where)
    modules_raw = value.get("modules")
    if not isinstance(modules_raw, list) or not modules_raw:
        raise ManifestError(f"{where}.modules must be a non-empty array")

    modules: list[ModuleUnit] = []
    seen: set[str] = set()
    for index, item_raw in enumerate(modules_raw):
        item = _require_object(item_raw, f"{where}.modules[{index}]")
        name = _require_string(item.get("name"), f"{where}.modules[{index}].name")
        if name in seen:
            raise ManifestError(f"duplicate module {name!r} in {where}")
        imports_raw = item.get("imports", [])
        if not isinstance(imports_raw, list) or not all(
            isinstance(entry, str) and entry for entry in imports_raw
        ):
            raise ManifestError(f"{where}.modules[{index}].imports must be strings")
        missing = [entry for entry in imports_raw if entry not in seen]
        if missing:
            raise ManifestError(
                f"{where}.modules must be topologically ordered; {name!r} "
                f"depends on later or missing modules: {missing}"
            )
        modules.append(
            ModuleUnit(
                name=name,
                source=_relative_file(
                    root, item.get("source"), f"{where}.modules[{index}].source"
                ),
                imports=tuple(imports_raw),
            )
        )
        seen.add(name)

    consumer = _relative_file(root, value.get("consumer"), f"{where}.consumer")
    return StateSpec(modules=tuple(modules), consumer=consumer)


def _load_manifest_document(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        try:
            with path.open("r", encoding="utf-8") as source:
                return _require_object(json.load(source), str(path))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"invalid JSON in {path}: {exc}") from exc

    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ManifestError(
            f"{path} requires optional PyYAML; JSON manifests need no dependency"
        ) from exc
    with path.open("r", encoding="utf-8") as source:
        return _require_object(yaml.safe_load(source), str(path))


def load_scenario(path: Path) -> Scenario:
    path = path.resolve()
    root = path.parent
    raw = _load_manifest_document(path)

    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise ManifestError(f"{path}: unsupported schema_version {schema_version!r}")

    scenario_id = _require_string(raw.get("id"), f"{path}.id")
    if not ID_PATTERN.fullmatch(scenario_id):
        raise ManifestError(f"{path}.id has an invalid format: {scenario_id!r}")

    family = _require_string(raw.get("family"), f"{path}.family")
    description = _require_string(raw.get("description"), f"{path}.description")
    mutation = _require_string(raw.get("mutation"), f"{path}.mutation")
    primary_module = _require_string(
        raw.get("primary_module"), f"{path}.primary_module"
    )

    language_rules_raw = raw.get("language_rules")
    if not isinstance(language_rules_raw, list) or not language_rules_raw or not all(
        isinstance(value, str) and value for value in language_rules_raw
    ):
        raise ManifestError(f"{path}.language_rules must be non-empty strings")

    tracked_raw = raw.get("tracked_modules")
    if not isinstance(tracked_raw, list) or not tracked_raw or not all(
        isinstance(value, str) and value for value in tracked_raw
    ):
        raise ManifestError(f"{path}.tracked_modules must be non-empty strings")

    observation_raw = _require_object(raw.get("observation"), f"{path}.observation")
    observation_kind = _require_string(
        observation_raw.get("kind"), f"{path}.observation.kind"
    )
    if observation_kind not in SUPPORTED_OBSERVATIONS:
        raise ManifestError(
            f"{path}.observation.kind {observation_kind!r} is unsupported"
        )
    probe_raw = observation_raw.get("probe_id")
    probe_id = None if probe_raw is None else _require_string(
        probe_raw, f"{path}.observation.probe_id"
    )
    if observation_kind not in {
        "compile_status",
        "diagnostic_class",
        "name_reachability",
    } and not probe_id:
        raise ManifestError(f"{path}: observation {observation_kind} needs probe_id")

    states = _require_object(raw.get("states"), f"{path}.states")
    before = _parse_state(root, states.get("before"), f"{path}.states.before")
    after = _parse_state(root, states.get("after"), f"{path}.states.after")

    if before.module_names != after.module_names:
        raise ManifestError(f"{path}: before/after module names or order differ")
    if primary_module not in before.module_names:
        raise ManifestError(f"{path}: primary module {primary_module!r} is absent")
    unknown_tracked = set(tracked_raw) - set(before.module_names)
    if unknown_tracked:
        raise ManifestError(f"{path}: unknown tracked modules: {sorted(unknown_tracked)}")
    if before.consumer.read_bytes() != after.consumer.read_bytes():
        raise ManifestError(f"{path}: consumer must be byte-identical before/after")

    known = {
        "schema_version",
        "id",
        "family",
        "description",
        "language_rules",
        "mutation",
        "primary_module",
        "tracked_modules",
        "observation",
        "states",
    }
    metadata = {key: value for key, value in raw.items() if key not in known}

    return Scenario(
        schema_version=1,
        scenario_id=scenario_id,
        family=family,
        description=description,
        language_rules=tuple(language_rules_raw),
        mutation=mutation,
        primary_module=primary_module,
        tracked_modules=tuple(tracked_raw),
        observation=ObservationSpec(kind=observation_kind, probe_id=probe_id),
        before=before,
        after=after,
        root=root,
        manifest_path=path,
        metadata=metadata,
    )


def discover_scenarios(root: Path) -> list[Scenario]:
    root = root.resolve()
    candidates = sorted(root.rglob("scenario.json")) + sorted(
        root.rglob("scenario.yaml")
    )
    scenarios = [load_scenario(path) for path in candidates]
    identifiers: set[str] = set()
    duplicates: set[str] = set()
    for scenario in scenarios:
        if scenario.scenario_id in identifiers:
            duplicates.add(scenario.scenario_id)
        identifiers.add(scenario.scenario_id)
    if duplicates:
        raise ManifestError(f"duplicate scenario ids: {sorted(duplicates)}")
    if not scenarios:
        raise ManifestError(f"no scenario manifests found below {root}")
    return scenarios


def select_scenarios(
    scenarios: Iterable[Scenario], identifiers: set[str] | None
) -> list[Scenario]:
    values = list(scenarios)
    if not identifiers:
        return values
    selected = [item for item in values if item.scenario_id in identifiers]
    missing = identifiers - {item.scenario_id for item in selected}
    if missing:
        raise ManifestError(f"unknown scenario ids: {sorted(missing)}")
    return selected
