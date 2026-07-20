from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import AnalyzerOutputError, ProcessFailure
from .jsonio import read_json
from .model import CommandResult, Scenario, StateSpec, Toolchain
from .process import CommandRunner


@dataclass
class StateArtifacts:
    state: str
    directory: Path
    pcm_files: dict[str, Path]
    module_scans: dict[str, dict[str, Any]]
    consumer_compile: CommandResult | None = None
    consumer_scan: dict[str, Any] | None = None
    consumer_analyzer_result: CommandResult | None = None


def _base_flags(toolchain: Toolchain, cache_directory: Path) -> list[str]:
    flags = [
        f"-std={toolchain.cxx_standard}",
        f"-fmodules-cache-path={cache_directory}",
        "-fno-modules-reduced-bmi"
        if toolchain.bmi_mode == "full"
        else "-fmodules-reduced-bmi",
        *toolchain.extra_compile_flags,
    ]
    if toolchain.target:
        flags.append(f"--target={toolchain.target}")
    return flags


def _module_flags(pcm_files: dict[str, Path], names: tuple[str, ...]) -> list[str]:
    return [f"-fmodule-file={name}={pcm_files[name]}" for name in names]


def prepare_state(
    scenario: Scenario,
    state_name: str,
    state: StateSpec,
    directory: Path,
    toolchain: Toolchain,
    command_runner: CommandRunner,
) -> StateArtifacts:
    if directory.exists():
        shutil.rmtree(directory)
    pcm_directory = directory / "pcm"
    scan_directory = directory / "scans"
    cache_directory = directory / "module-cache"
    pcm_directory.mkdir(parents=True)
    scan_directory.mkdir(parents=True)
    cache_directory.mkdir(parents=True)

    pcm_files: dict[str, Path] = {}
    scans: dict[str, dict[str, Any]] = {}
    for unit in state.modules:
        # Clang requires explicit mappings not only for a unit's direct
        # imports, but also for the imported BMIs' transitive dependencies.
        # The manifest is topologically ordered, so every previously built
        # module is a safe and complete mapping set for the current unit.
        available_modules = tuple(pcm_files)
        pcm = pcm_directory / f"{unit.name.replace(':', '-')}.pcm"
        build_command = [
            toolchain.clangxx,
            *_base_flags(toolchain, cache_directory),
            *_module_flags(pcm_files, available_modules),
            str(unit.source),
            "--precompile",
            "-o",
            str(pcm),
        ]
        built = command_runner.run(
            build_command,
            cwd=directory,
            label=f"{state_name}-build-{unit.name}",
        )
        if built.returncode != 0 or not pcm.is_file():
            raise ProcessFailure(
                f"failed to build module {unit.name} in {scenario.scenario_id}: "
                f"{built.stderr.strip()}"
            )
        pcm_files[unit.name] = pcm

        scan_path = scan_directory / f"{unit.name.replace(':', '-')}.json"
        analyzer_command = [
            str(toolchain.analyzer),
            "--mode=provider",
            f"--output={scan_path}",
            f"--logical-module={unit.name}",
            *toolchain.extra_analyzer_flags,
            str(unit.source),
            "--",
            *_base_flags(toolchain, cache_directory),
            *_module_flags(pcm_files, available_modules),
        ]
        analyzed = command_runner.run(
            analyzer_command,
            cwd=directory,
            label=f"{state_name}-scan-{unit.name}",
        )
        if analyzed.returncode != 0 or not scan_path.is_file():
            raise ProcessFailure(
                f"failed to scan module {unit.name} in {scenario.scenario_id}: "
                f"{analyzed.stderr.strip()}"
            )
        raw = read_json(scan_path)
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise AnalyzerOutputError(f"invalid analyzer output: {scan_path}")
        scans[unit.name] = raw

    return StateArtifacts(
        state=state_name,
        directory=directory,
        pcm_files=pcm_files,
        module_scans=scans,
    )


def analyze_consumer(
    scenario: Scenario,
    state: StateSpec,
    artifacts: StateArtifacts,
    toolchain: Toolchain,
    command_runner: CommandRunner,
) -> None:
    cache_directory = artifacts.directory / "module-cache"
    module_names = state.module_names
    compile_command = [
        toolchain.clangxx,
        *_base_flags(toolchain, cache_directory),
        *_module_flags(artifacts.pcm_files, module_names),
        "-fsyntax-only",
        str(state.consumer),
    ]
    compile_result = command_runner.run(
        compile_command,
        cwd=artifacts.directory,
        label=f"{artifacts.state}-compile-consumer",
    )
    artifacts.consumer_compile = compile_result

    scan_path = artifacts.directory / "consumer-scan.json"
    analyzer_command = [
        str(toolchain.analyzer),
        "--mode=consumer",
        f"--output={scan_path}",
        f"--probe-id={scenario.observation.probe_id or ''}",
        *[f"--tracked-module={name}" for name in scenario.tracked_modules],
        *toolchain.extra_analyzer_flags,
        str(state.consumer),
        "--",
        *_base_flags(toolchain, cache_directory),
        *_module_flags(artifacts.pcm_files, module_names),
    ]
    analyzer_result = command_runner.run(
        analyzer_command,
        cwd=artifacts.directory,
        label=f"{artifacts.state}-scan-consumer",
    )
    artifacts.consumer_analyzer_result = analyzer_result
    if scan_path.is_file():
        raw = read_json(scan_path)
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise AnalyzerOutputError(f"invalid analyzer output: {scan_path}")
        artifacts.consumer_scan = raw
