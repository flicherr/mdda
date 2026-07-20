from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .errors import StandError
from .jsonio import canonical_json, read_json, write_json, write_text


CRITERIA = ("module", "full_interface", "used_declarations")
CLASSES = (
    "correct_skip",
    "unsafe_skip",
    "conservative_trigger",
    "correct_trigger",
)


def load_results(run_directory: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for path in sorted(run_directory.glob("*/result.json")):
        raw = read_json(path)
        if isinstance(raw, dict):
            values.append(raw)
    if not values:
        raise StandError(f"no scenario result files in {run_directory}")
    return values


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": None if denominator == 0 else numerator / denominator,
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [value for value in results if value.get("status") == "completed"]
    failures = [value for value in results if value.get("status") != "completed"]
    criterion_counts: dict[str, Counter[str]] = {
        name: Counter() for name in CRITERIA
    }
    family_counts: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {name: Counter() for name in CRITERIA}
    )

    for result in completed:
        family = str(result.get("family", "unknown"))
        for criterion in CRITERIA:
            classification = result["criteria"][criterion]["classification"]
            criterion_counts[criterion][classification] += 1
            family_counts[family][criterion][classification] += 1

    criteria_summary: dict[str, Any] = {}
    for criterion in CRITERIA:
        counts = criterion_counts[criterion]
        predicted_skip = counts["correct_skip"] + counts["unsafe_skip"]
        outcome_changed = counts["correct_trigger"] + counts["unsafe_skip"]
        outcome_unchanged = (
            counts["correct_skip"] + counts["conservative_trigger"]
        )
        criteria_summary[criterion] = {
            "counts": {name: counts[name] for name in CLASSES},
            "unsafe_skip_rate": _rate(counts["unsafe_skip"], predicted_skip),
            "miss_rate": _rate(counts["unsafe_skip"], outcome_changed),
            "conservative_rate": _rate(
                counts["conservative_trigger"], outcome_unchanged
            ),
        }

    family_summary: dict[str, Any] = {}
    for family in sorted(family_counts):
        family_summary[family] = {
            criterion: {
                name: family_counts[family][criterion][name] for name in CLASSES
            }
            for criterion in CRITERIA
        }

    return {
        "schema_version": 1,
        "total_results": len(results),
        "completed": len(completed),
        "harness_failures": len(failures),
        "outcome_changed": sum(
            bool(value["observation"]["changed"]) for value in completed
        ),
        "outcome_unchanged": sum(
            not bool(value["observation"]["changed"]) for value in completed
        ),
        "criteria": criteria_summary,
        "families": family_summary,
        "failed_scenarios": [value.get("scenario_id") for value in failures],
    }


def _percentage(rate: dict[str, Any]) -> str:
    if rate["value"] is None:
        return f"n/a (0/{rate['denominator']})"
    return f"{rate['value'] * 100:.1f}% ({rate['numerator']}/{rate['denominator']})"


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Experiment summary",
        "",
        f"Completed scenarios: **{summary['completed']} / {summary['total_results']}**.",
        f"Harness failures: **{summary['harness_failures']}**.",
        "",
        "## Criterion matrix",
        "",
        "| Criterion | Correct skip | Unsafe skip | Conservative | Correct trigger | Unsafe-skip rate | Miss rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for criterion in CRITERIA:
        value = summary["criteria"][criterion]
        counts = value["counts"]
        lines.append(
            "| {criterion} | {correct_skip} | {unsafe_skip} | "
            "{conservative_trigger} | {correct_trigger} | {unsafe_rate} | {miss_rate} |".format(
                criterion=criterion,
                **counts,
                unsafe_rate=_percentage(value["unsafe_skip_rate"]),
                miss_rate=_percentage(value["miss_rate"]),
            )
        )
    lines.extend(
        [
            "",
            "Percentages describe this deliberately constructed corpus only; they are not",
            "estimates of change frequency in industrial projects.",
            "",
        ]
    )
    return "\n".join(lines)


def write_publication_outputs(
    run_directory: Path, output_directory: Path
) -> dict[str, Any]:
    results = load_results(run_directory)
    summary = aggregate_results(results)
    output_directory.mkdir(parents=True, exist_ok=True)

    write_json(output_directory / "summary.json", summary)
    write_text(output_directory / "summary.md", render_markdown(summary))
    write_text(
        output_directory / "results.jsonl",
        "".join(canonical_json(value) + "\n" for value in results),
    )

    with (output_directory / "results.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        fieldnames = [
            "scenario_id",
            "family",
            "scenario_status",
            "semantic_outcome_kind",
            "outcome_before",
            "outcome_after",
            "outcome_changed",
            *[
                f"{criterion}_{suffix}"
                for criterion in CRITERIA
                for suffix in ("prediction", "classification")
            ],
        ]
        writer = csv.DictWriter(
            destination,
            fieldnames=fieldnames,
            delimiter=";",
            lineterminator="\n",
        )
        writer.writeheader()
        for result in results:
            row: dict[str, Any] = {
                "scenario_id": result.get("scenario_id"),
                "family": result.get("family"),
                "scenario_status": result.get("status"),
                "semantic_outcome_kind": None,
                "outcome_before": None,
                "outcome_after": None,
                "outcome_changed": None,
            }
            if result.get("status") == "completed":
                observation = result["observation"]
                row["semantic_outcome_kind"] = observation["specification"]["kind"]
                for state in ("before", "after"):
                    value = observation[state].get("value")
                    row[f"outcome_{state}"] = (
                        canonical_json(value)
                        if isinstance(value, (dict, list))
                        else value
                    )
                row["outcome_changed"] = result["observation"]["changed"]
                for criterion in CRITERIA:
                    row[f"{criterion}_prediction"] = result["criteria"][criterion][
                        "prediction"
                    ]
                    row[f"{criterion}_classification"] = result["criteria"][
                        criterion
                    ]["classification"]
            writer.writerow(row)
    return summary
