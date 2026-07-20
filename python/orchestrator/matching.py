from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .jsonio import canonical_json, stable_hash


def with_fingerprint(declaration: dict[str, Any]) -> dict[str, Any]:
    result = dict(declaration)
    normalized = result.get("normalized", {})
    result["fingerprint"] = stable_hash(normalized)
    return result


def declarations_from_scans(
    scans: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for module_name in sorted(scans):
        for declaration in scans[module_name].get("declarations", []):
            if isinstance(declaration, dict):
                value = with_fingerprint(declaration)
                value.setdefault("owning_module", module_name)
                result.append(value)
    return result


def visible_surface(
    scans: dict[str, dict[str, Any]], primary_module: str
) -> list[dict[str, Any]]:
    """Resolve exported declarations through explicit export-import edges."""

    declarations: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit(module_name: str) -> None:
        if module_name in visited:
            return
        visited.add(module_name)
        scan = scans.get(module_name)
        if scan is None:
            return
        for raw in scan.get("declarations", []):
            if not isinstance(raw, dict) or not raw.get("exported", False):
                continue
            declaration = with_fingerprint(raw)
            declarations.append(declaration)
        for import_record in scan.get("imports", []):
            if not isinstance(import_record, dict) or not import_record.get("exported"):
                continue
            imported = import_record.get("module")
            if isinstance(imported, str):
                visit(imported)

    visit(primary_module)
    return sorted(
        declarations,
        key=lambda declaration: (
            str(declaration.get("stable_id", "")),
            str(declaration.get("structural_key", "")),
            canonical_json(declaration.get("normalized", {})),
        ),
    )


class DeclarationIndex:
    def __init__(self, declarations: Iterable[dict[str, Any]]) -> None:
        self.by_stable_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_structural_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for declaration in declarations:
            stable_id = declaration.get("stable_id")
            structural_key = declaration.get("structural_key")
            if isinstance(stable_id, str) and stable_id:
                self.by_stable_id[stable_id].append(declaration)
            if isinstance(structural_key, str) and structural_key:
                self.by_structural_key[structural_key].append(declaration)

    def match(self, previous: dict[str, Any]) -> dict[str, Any]:
        stable_id = previous.get("stable_id")
        if isinstance(stable_id, str) and stable_id:
            candidates = self.by_stable_id.get(stable_id, [])
            if len(candidates) == 1:
                return {"status": "matched", "method": "stable_id", "value": candidates[0]}
            if len(candidates) > 1:
                structural_key = previous.get("structural_key")
                structural_matches = [
                    candidate
                    for candidate in candidates
                    if candidate.get("structural_key") == structural_key
                ]
                if len(structural_matches) == 1:
                    return {
                        "status": "matched",
                        "method": "stable_id+structural_key",
                        "value": structural_matches[0],
                    }
                normalized = canonical_json(previous.get("normalized", {}))
                normalized_matches = [
                    candidate
                    for candidate in structural_matches or candidates
                    if canonical_json(candidate.get("normalized", {})) == normalized
                ]
                if len(normalized_matches) == 1:
                    return {
                        "status": "matched",
                        "method": "stable_id+normalized",
                        "value": normalized_matches[0],
                    }
                return {
                    "status": "ambiguous",
                    "method": "stable_id",
                    "count": len(candidates),
                }

        structural_key = previous.get("structural_key")
        if isinstance(structural_key, str) and structural_key:
            candidates = self.by_structural_key.get(structural_key, [])
            if len(candidates) == 1:
                return {
                    "status": "matched",
                    "method": "structural_key",
                    "value": candidates[0],
                }
            if len(candidates) > 1:
                return {
                    "status": "ambiguous",
                    "method": "structural_key",
                    "count": len(candidates),
                }
        return {"status": "missing", "method": None}


def compare_declarations(
    previous: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    previous_normalized = previous.get("normalized", {})
    current_normalized = current.get("normalized", {})
    equal = canonical_json(previous_normalized) == canonical_json(current_normalized)
    return {
        "equal": equal,
        "before_fingerprint": stable_hash(previous_normalized),
        "after_fingerprint": stable_hash(current_normalized),
    }
