from __future__ import annotations

import re
from pathlib import Path


PATH_LOCATION = re.compile(
    r"(?:[A-Za-z]:)?[^\s:]+\.(?:cppm|ccm|cxxm|cpp|cc|cxx|h|hpp):\d+(?::\d+)?"
)
NUMBER = re.compile(r"\b\d+\b")
SPACE = re.compile(r"\s+")


def diagnostic_class(stderr: str) -> str:
    lowered = stderr.lower()
    patterns = (
        ("ambiguous", "ambiguous_lookup_or_overload"),
        ("use of undeclared identifier", "undeclared_identifier"),
        ("undeclared", "undeclared_identifier"),
        ("no matching function", "no_matching_function"),
        ("constraints not satisfied", "constraints_not_satisfied"),
        ("failed requirement", "constraints_not_satisfied"),
        ("not visible", "unreachable_declaration"),
        ("module", "module_error"),
    )
    for needle, category in patterns:
        if needle in lowered:
            return category
    return "semantic_error" if stderr.strip() else "unknown_failure"


def looks_like_compiler_crash(returncode: int, stderr: str) -> bool:
    if returncode < 0:
        return True
    lowered = stderr.lower()
    return any(
        marker in lowered
        for marker in (
            "please submit a bug report",
            "clang frontend command failed due to signal",
            "segmentation fault",
            "stack dump:",
        )
    )


def normalized_diagnostic(stderr: str) -> str:
    first_error = ""
    for line in stderr.splitlines():
        if "error:" in line.lower():
            first_error = line
            break
    if not first_error:
        first_error = stderr.splitlines()[0] if stderr.splitlines() else ""
    value = PATH_LOCATION.sub("<source>:<line>:<column>", first_error)
    value = NUMBER.sub("<n>", value)
    return SPACE.sub(" ", value).strip()
