from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .aggregate import write_publication_outputs
from .determinism import compare_runs
from .errors import StandError
from .manifest import discover_scenarios, select_scenarios
from .pipeline import run_experiment
from .toolchain import doctor, load_toolchain


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrator",
        description="C++20 module declaration dependency experiment orchestrator",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate", help="validate scenario corpus")
    validate.add_argument("--scenarios", type=Path, default=Path("scenarios"))

    doctor_parser = subcommands.add_parser("doctor", help="check pinned toolchain")
    doctor_parser.add_argument("--config", type=Path, required=True)

    run = subcommands.add_parser("run", help="execute the experiment")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--scenarios", type=Path, default=Path("scenarios"))
    run.add_argument("--scenario", action="append", default=[])
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--fail-fast", action="store_true")

    aggregate = subcommands.add_parser(
        "aggregate", help="generate publication-oriented outputs"
    )
    aggregate.add_argument("--run", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)

    compare = subcommands.add_parser(
        "compare", help="compare two runs after removing volatile fields"
    )
    compare.add_argument("--left", type=Path, required=True)
    compare.add_argument("--right", type=Path, required=True)
    return parser


def _validate(scenarios_path: Path) -> int:
    scenarios = discover_scenarios(scenarios_path)
    families = Counter(scenario.family for scenario in scenarios)
    result = {
        "valid": True,
        "scenario_count": len(scenarios),
        "families": dict(sorted(families.items())),
        "ids": [scenario.scenario_id for scenario in scenarios],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args.scenarios)
        if args.command == "doctor":
            snapshot = doctor(load_toolchain(args.config))
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
            return 0
        if args.command == "run":
            all_scenarios = discover_scenarios(args.scenarios)
            selected = select_scenarios(all_scenarios, set(args.scenario))
            summary = run_experiment(
                selected,
                load_toolchain(args.config),
                args.output,
                fail_fast=args.fail_fast,
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if summary["harness_failures"] == 0 else 2
        if args.command == "aggregate":
            summary = write_publication_outputs(args.run, args.output)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        if args.command == "compare":
            comparison = compare_runs(args.left, args.right)
            print(json.dumps(comparison, ensure_ascii=False, indent=2))
            return 0 if comparison["equal"] else 1
    except (StandError, OSError, ValueError) as exc:
        print(f"orchestrator: {exc}", file=sys.stderr)
        return 2
    return 2
