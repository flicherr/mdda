# MDDA — Module Declaration Dependency Analysis

![C++20](https://img.shields.io/badge/C%2B%2B-20-00599C?logo=cplusplus&logoColor=white)
![Clang 22.1.8](https://img.shields.io/badge/Clang-22.1.8-262D3A?logo=llvm&logoColor=white)
[![MIT License](https://img.shields.io/badge/license-MIT-2EA44F)](LICENSE)

MDDA is a reproducible experiment harness for analysing declaration-level
dependencies between consumers and providers of C++20 named modules. It
evaluates whether a consumer must be semantically re-analysed after a provider
change and records the complete evidence needed to inspect that decision.

The project is a research implementation, not a production incremental build
system. Its fixed corpus targets language mechanisms that can invalidate a
decision based only on declarations used during the previous consumer
analysis.

## Components

| Path | Purpose |
|---|---|
| `analyzer/` | `manalyzer`, a C++/Clang LibTooling executable that extracts exported declarations, uses, and semantic observations |
| `python/orchestrator/` | dependency-free Python package and CLI that builds isolated states, evaluates criteria, and aggregates results |
| `scenarios/` | version-controlled corpus of 28 controlled provider changes |
| `schemas/` | JSON schemas for scenario manifests and generated artifacts |
| `environment/` | toolchain configuration and container entrypoint |
| `docs/` | protocol, architecture, scenario catalog, reproduction checklist, and verification state |

The C++ analyzer and Python orchestrator exchange versioned JSON documents.
Compiler-specific AST processing remains in `manalyzer`; process execution,
comparison, and result generation remain in the orchestrator.

## How the experiment works

The harness evaluates one declaration-level criterion against two coarser
baselines:

| Criterion | Re-analysis is requested when... |
|---|---|
| <i>C</i><sub>module</sub> | any tracked provider source changes |
| <i>C</i><sub>interface</sub> | the recursively exported provider interface changes |
| <i>C</i><sub>used</sub> | a previously used declaration is missing, ambiguous, unsupported, or has changed |

For each scenario, MDDA:

1. builds fresh module interfaces for the original provider state;
2. analyses the unchanged consumer and records its used declarations and
   selected semantic observation;
3. builds the changed providers and writes all criterion predictions to
   `prediction.json`;
4. performs a clean analysis of the consumer against the changed providers;
5. classifies each prediction by comparing the two observation values.

The prediction is written before the changed consumer is analysed, so the
reference result cannot affect criterion evaluation. The complete procedure is
defined in the [experiment protocol](docs/protocol.md).

## Requirements

- LLVM/Clang 22.1.8 development files and a matching `clang++` executable;
- CMake 3.20 or newer;
- Python 3.11 or newer;
- Ninja and GNU Make.

The reference configuration uses Full BMI and rejects a different Clang
version. Environment setup is documented for:

- [native Linux toolchains](environment/README.md#native-environment);
- [Docker on Linux and Windows](environment/README.md#docker).

Neither execution path is preferred by the project. Docker provides the
pinned Linux environment; native execution is useful when developing or
debugging the analyzer.

## Build and validate

After configuring `environment/toolchain.json` for the selected environment:

```bash
make build
make test
make validate
make doctor
```

`make build` configures the root CMake project and produces
`build/manalyzer`. The remaining commands run the Python tests, validate the
scenario corpus, and verify the compiler/analyzer configuration.

## Command-line interface

Installing the Python package exposes the `orchestrator` command:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Without installation, replace `orchestrator` with
`PYTHONPATH=python python3 -m orchestrator`.

| Command | Purpose |
|---|---|
| `validate` | validate scenario manifests and corpus invariants |
| `doctor` | verify the compiler, analyzer, target, and BMI configuration |
| `run` | execute the full corpus or selected scenarios in a new directory |
| `compare` | compare two runs after removing documented volatile fields |
| `aggregate` | generate CSV, JSON, JSONL, and Markdown summaries |

The full reference sequence and platform-specific commands are kept in the
[environment guide](environment/README.md). Use
`orchestrator <command> --help` for all CLI options.

## Results

A complete run stores raw scenario artifacts under `results/runs/`. Every
completed scenario contains:

- `prediction.json`, written before the changed consumer is analysed;
- `result.json`, containing both observations, compiler status, predictions,
  and classifications;
- exact compiler and analyzer commands with their standard streams;
- separate provider and consumer scans for both states.

Aggregation produces `results.csv`, `results.jsonl`, `summary.json`, and
`summary.md`. CSV uses a semicolon delimiter. A semantic error in the changed
consumer is a valid observation; `scenario_status=completed` only means that
the experimental pipeline completed successfully.

Generated runs and summaries are excluded from version control.

## Documentation

- [Environment and execution](environment/README.md)
- [Experiment protocol](docs/protocol.md)
- [Architecture](docs/architecture.md)
- [Scenario catalog](docs/scenario_catalog.md)
- [Reproduction checklist](docs/reproduction.md)
- [Verification state](docs/verification.md)
- [JSON schemas](schemas/)

## Scope

The corpus is deliberately constructed around selected C++ language
mechanisms. Its counts do not estimate change frequency or build-time savings
in industrial projects, and a successful run does not establish that
<i>C</i><sub>used</sub> is sufficient for arbitrary C++ programs.

[WG21 P3057R0](https://wg21.link/P3057R0) discusses a related direction based
on declaration hashes and dependency tracking. It is research context, not a
specification implemented by MDDA.

## License

MDDA is distributed under the [MIT License](LICENSE).
