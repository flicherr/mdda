from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_OBSERVATIONS = frozenset(
    {
        "selected_declaration",
        "expression_type",
        "selected_specialization",
        "deduced_type",
        "constraint_result",
        "name_reachability",
        "compile_status",
        "diagnostic_class",
    }
)


@dataclass(frozen=True)
class ModuleUnit:
    name: str
    source: Path
    imports: tuple[str, ...] = ()


@dataclass(frozen=True)
class StateSpec:
    modules: tuple[ModuleUnit, ...]
    consumer: Path

    @property
    def module_names(self) -> tuple[str, ...]:
        return tuple(unit.name for unit in self.modules)

    def module(self, name: str) -> ModuleUnit:
        for unit in self.modules:
            if unit.name == name:
                return unit
        raise KeyError(name)


@dataclass(frozen=True)
class ObservationSpec:
    kind: str
    probe_id: str | None = None


@dataclass(frozen=True)
class Scenario:
    schema_version: int
    scenario_id: str
    family: str
    description: str
    language_rules: tuple[str, ...]
    mutation: str
    primary_module: str
    tracked_modules: tuple[str, ...]
    observation: ObservationSpec
    before: StateSpec
    after: StateSpec
    root: Path
    manifest_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Toolchain:
    schema_version: int
    clangxx: str
    analyzer: Path
    required_clang_version: str
    cxx_standard: str
    bmi_mode: str
    target: str | None
    extra_compile_flags: tuple[str, ...]
    extra_analyzer_flags: tuple[str, ...]
    environment: dict[str, str]
    config_path: Path


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "cwd": self.cwd,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
        }
