from __future__ import annotations

import datetime as dt
import shutil
import traceback
from pathlib import Path
from typing import Any, Iterable

from .build import analyze_consumer, prepare_state
from .criteria import classify, evaluate_all
from .diagnostics import looks_like_compiler_crash
from .errors import StandError
from .jsonio import file_hash, write_json
from .model import Scenario, Toolchain
from .outcome import extract_outcome, outcomes_equal
from .process import CommandRunner
from .toolchain import doctor, process_environment


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def run_scenario(
    scenario: Scenario,
    toolchain: Toolchain,
    output_root: Path,
    toolchain_snapshot: dict[str, Any],
) -> dict[str, Any]:
    scenario_directory = output_root / scenario.scenario_id
    if scenario_directory.exists():
        shutil.rmtree(scenario_directory)
    scenario_directory.mkdir(parents=True)
    shutil.copy2(
        scenario.manifest_path,
        scenario_directory / f"scenario-manifest{scenario.manifest_path.suffix}",
    )
    runner = CommandRunner(
        scenario_directory / "commands", process_environment(toolchain)
    )
    started_at = _utc_now()

    try:
        before = prepare_state(
            scenario,
            "before",
            scenario.before,
            scenario_directory / "before",
            toolchain,
            runner,
        )
        analyze_consumer(
            scenario, scenario.before, before, toolchain, runner
        )
        if before.consumer_compile is not None and (
            before.consumer_compile.timed_out
            or looks_like_compiler_crash(
                before.consumer_compile.returncode, before.consumer_compile.stderr
            )
        ):
            raise StandError("compiler crash or timeout in the before consumer")
        if before.consumer_compile is None or before.consumer_compile.returncode != 0:
            raise StandError("the before consumer must compile successfully")
        if before.consumer_scan is None:
            raise StandError("the before consumer has no analyzer output")
        before_outcome = extract_outcome(
            scenario.observation, before.consumer_compile, before.consumer_scan
        )

        after = prepare_state(
            scenario,
            "after",
            scenario.after,
            scenario_directory / "after",
            toolchain,
            runner,
        )

        # The prediction is serialized before the after-consumer is compiled or
        # analyzed. This is the enforced anti-circularity boundary.
        prediction = evaluate_all(
            scenario,
            before.module_scans,
            after.module_scans,
            before.consumer_scan,
        )
        prediction["written_at"] = _utc_now()
        prediction_path = scenario_directory / "prediction.json"
        write_json(prediction_path, prediction)
        prediction_hash = file_hash(prediction_path)

        analyze_consumer(scenario, scenario.after, after, toolchain, runner)
        if after.consumer_compile is None:
            raise StandError("the after consumer compile command was not executed")
        if after.consumer_compile.timed_out or looks_like_compiler_crash(
            after.consumer_compile.returncode, after.consumer_compile.stderr
        ):
            raise StandError("compiler crash or timeout in the after consumer")
        after_outcome = extract_outcome(
            scenario.observation, after.consumer_compile, after.consumer_scan
        )
        outcome_changed = not outcomes_equal(before_outcome, after_outcome)

        criterion_results: dict[str, Any] = {}
        for name, detail in prediction["criteria"].items():
            criterion_results[name] = {
                "prediction": detail["prediction"],
                "classification": classify(detail["prediction"], outcome_changed),
            }

        result = {
            "schema_version": 1,
            "scenario_id": scenario.scenario_id,
            "family": scenario.family,
            "description": scenario.description,
            "mutation": scenario.mutation,
            "language_rules": list(scenario.language_rules),
            "status": "completed",
            "started_at": started_at,
            "completed_at": _utc_now(),
            "toolchain": toolchain_snapshot,
            "observation": {
                "specification": {
                    "kind": scenario.observation.kind,
                    "probe_id": scenario.observation.probe_id,
                },
                "before": before_outcome,
                "after": after_outcome,
                "changed": outcome_changed,
            },
            "prediction_file": "prediction.json",
            "prediction_sha256": prediction_hash,
            "prediction_written_before_oracle": True,
            "criteria": criterion_results,
            "compiler_status": {
                "before": "success",
                "after": "success"
                if after.consumer_compile.returncode == 0
                else "semantic_failure",
            },
        }
    except Exception as exc:  # preserve partial artifacts for diagnosis
        result = {
            "schema_version": 1,
            "scenario_id": scenario.scenario_id,
            "family": scenario.family,
            "description": scenario.description,
            "status": "harness_failure",
            "started_at": started_at,
            "completed_at": _utc_now(),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        }
    write_json(scenario_directory / "result.json", result)
    return result


def run_experiment(
    scenarios: Iterable[Scenario],
    toolchain: Toolchain,
    output_root: Path,
    *,
    fail_fast: bool = False,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot = doctor(toolchain)
    write_json(output_root / "toolchain.json", snapshot)

    values = list(scenarios)
    run_manifest = {
        "schema_version": 1,
        "started_at": _utc_now(),
        "scenario_ids": [scenario.scenario_id for scenario in values],
        "scenario_count": len(values),
        "protocol": "predict-before-after-consumer-oracle",
    }
    write_json(output_root / "run.json", run_manifest)

    results = []
    for scenario in values:
        result = run_scenario(scenario, toolchain, output_root, snapshot)
        results.append(result)
        if fail_fast and result["status"] != "completed":
            break

    summary = {
        "schema_version": 1,
        "completed_at": _utc_now(),
        "requested": len(values),
        "executed": len(results),
        "completed": sum(value["status"] == "completed" for value in results),
        "harness_failures": sum(
            value["status"] == "harness_failure" for value in results
        ),
    }
    write_json(output_root / "run-summary.json", summary)
    return summary
