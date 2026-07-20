from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import ToolchainError
from .jsonio import read_json
from .model import Toolchain


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ToolchainError(f"{where} must be an array of strings")
    return tuple(value)


def load_toolchain(path: Path) -> Toolchain:
    path = path.resolve()
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ToolchainError(f"{path}: unsupported toolchain schema")
    clangxx = raw.get("clangxx")
    analyzer_raw = raw.get("analyzer")
    required_clang_version = raw.get("required_clang_version", "22.1.8")
    standard = raw.get("cxx_standard", "c++20")
    bmi_mode = raw.get("bmi_mode", "full")
    if not isinstance(clangxx, str) or not clangxx:
        raise ToolchainError(f"{path}: clangxx must be a non-empty string")
    if not isinstance(analyzer_raw, str) or not analyzer_raw:
        raise ToolchainError(f"{path}: analyzer must be a non-empty string")
    if not isinstance(standard, str) or not standard:
        raise ToolchainError(f"{path}: cxx_standard must be a string")
    if not isinstance(required_clang_version, str) or not re.fullmatch(
        r"\d+\.\d+\.\d+", required_clang_version
    ):
        raise ToolchainError(
            f"{path}: required_clang_version must have MAJOR.MINOR.PATCH form"
        )
    if bmi_mode not in {"full", "reduced"}:
        raise ToolchainError(f"{path}: bmi_mode must be 'full' or 'reduced'")

    project_root = path.parent.parent
    analyzer = Path(analyzer_raw)
    if not analyzer.is_absolute():
        analyzer = project_root / analyzer

    environment_raw = raw.get("environment", {})
    if not isinstance(environment_raw, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in environment_raw.items()
    ):
        raise ToolchainError(f"{path}: environment must map strings to strings")

    target = raw.get("target")
    if target is not None and not isinstance(target, str):
        raise ToolchainError(f"{path}: target must be null or string")

    return Toolchain(
        schema_version=1,
        clangxx=clangxx,
        analyzer=analyzer.resolve(),
        required_clang_version=required_clang_version,
        cxx_standard=standard,
        bmi_mode=bmi_mode,
        target=target,
        extra_compile_flags=_strings(
            raw.get("extra_compile_flags", []), "extra_compile_flags"
        ),
        extra_analyzer_flags=_strings(
            raw.get("extra_analyzer_flags", []), "extra_analyzer_flags"
        ),
        environment=dict(environment_raw),
        config_path=path,
    )


def process_environment(toolchain: Toolchain) -> dict[str, str]:
    result = os.environ.copy()
    result.update(toolchain.environment)
    result.setdefault("LC_ALL", "C")
    result.setdefault("LANG", "C")
    result.setdefault("TZ", "UTC")
    return result


def _version(executable: str | Path, environment: dict[str, str]) -> str:
    completed = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
        env=environment,
    )
    text = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise ToolchainError(f"{executable} --version failed: {text}")
    return text


def _clang_version_tuple(text: str) -> tuple[int, int, int] | None:
    match = re.search(
        r"clang version\s+(\d+)\.(\d+)\.(\d+)", text, re.IGNORECASE
    )
    if match is None:
        return None
    return tuple(int(value) for value in match.groups())


def doctor(toolchain: Toolchain) -> dict[str, Any]:
    environment = process_environment(toolchain)
    clang_path = shutil.which(toolchain.clangxx, path=environment.get("PATH"))
    if clang_path is None:
        raise ToolchainError(f"clang executable not found: {toolchain.clangxx}")
    if not toolchain.analyzer.is_file():
        raise ToolchainError(f"analyzer executable not found: {toolchain.analyzer}")
    if not os.access(toolchain.analyzer, os.X_OK):
        raise ToolchainError(f"analyzer is not executable: {toolchain.analyzer}")

    clang_version = _version(clang_path, environment)
    analyzer_version = _version(toolchain.analyzer, environment)
    version = _clang_version_tuple(clang_version)
    required_version = tuple(
        int(value) for value in toolchain.required_clang_version.split(".")
    )
    if version != required_version:
        raise ToolchainError(
            f"the artifact is pinned to Clang {toolchain.required_clang_version}, got: "
            f"{clang_version.splitlines()[0]}"
        )
    analyzer_version_number = _clang_version_tuple(analyzer_version)
    if analyzer_version_number != version:
        raise ToolchainError(
            "clang++ and manalyzer use different LLVM/Clang versions: "
            f"{version!r} vs {analyzer_version_number!r}"
        )

    return {
        "clangxx": str(Path(clang_path).resolve()),
        "clang_version": clang_version,
        "clang_version_number": ".".join(str(value) for value in version),
        "clang_major": version[0],
        "required_clang_version": toolchain.required_clang_version,
        "analyzer": str(toolchain.analyzer),
        "analyzer_version": analyzer_version,
        "analyzer_clang_version_number": ".".join(
            str(value) for value in analyzer_version_number
        ),
        "analyzer_clang_major": analyzer_version_number[0],
        "standard": toolchain.cxx_standard,
        "bmi_mode": toolchain.bmi_mode,
        "target": toolchain.target,
        "extra_compile_flags": list(toolchain.extra_compile_flags),
        "extra_analyzer_flags": list(toolchain.extra_analyzer_flags),
    }
