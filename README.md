# C++ Module Declaration Dependency Analysis

This repository contains a reproducible experiment for studying whether a
consumer of a C++20 named module must be semantically re-analysed after its
providers change. The central object of evaluation is a declaration-level
criterion: can the consumer be skipped when every declaration it previously
used can still be matched with an equal normalized representation?

The project does not present all three implemented criteria as equal research
contributions. It evaluates one target criterion against two reference
baselines:

| Identifier | Role | Re-analysis is requested when... |
|---|---|---|
| `C_module` | maximally conservative baseline | any tracked provider source changes |
| `C_interface` | exported-interface baseline | the recursively exported interface changes |
| `C_used` | evaluated declaration-level criterion | a previously used declaration is missing, ambiguous, unsupported, or changed |

The baselines are necessary to quantify what declaration-level tracking gains
in selectivity and where it becomes unsafe. Removing them would leave only a
list of `C_used` successes and failures, with no meaningful comparison against
coarser dependency models.

## Repository layout

- `analyzer/` contains the C++ LibTooling implementation; its executable and
  CMake target are named `manalyzer`;
- `python/orchestrator/` contains the dependency-free experiment orchestrator;
- `scenarios/` contains the version-controlled 28-scenario corpus;
- `environment/` contains the pinned toolchain configuration and optional
  container definition;
- `schemas/` defines the exchanged JSON formats;
- `docs/` separates methodology, architecture, corpus description,
  reproduction, and verification;
- `results/` is the default location for raw runs and publication outputs.

The root `CMakeLists.txt` owns project-wide C++ settings and adds
`analyzer/`. The nested `analyzer/CMakeLists.txt` declares `manalyzer`, locates
LLVM/Clang, and selects its link libraries. Python packaging is independent of
CMake and is configured by the root `pyproject.toml`.

## Prerequisites

- Python 3.11 or newer;
- CMake 3.20 or newer and Make (or another CMake build tool);
- LLVM and Clang 22.1.8 development files, including `LLVMConfig.cmake` and
  `ClangConfig.cmake`;
- `clang++` 22.1.8 from the same LLVM installation used by `manalyzer`.

Package names and configuration paths depend on the distribution. Typical
installations are:

### Arch Linux

```bash
sudo pacman -S --needed clang llvm cmake python make
```

Common CMake package directories are `/usr/lib/cmake/llvm` and
`/usr/lib/cmake/clang`. Arch is rolling-release, so verify that the installed
packages are exactly 22.1.8 before producing a reference dataset.

### Debian/Ubuntu with apt.llvm.org packages

```bash
sudo apt install clang-22 llvm-22-dev libclang-22-dev \
  cmake python3 python3-venv make
```

Common CMake package directories are `/usr/lib/llvm-22/lib/cmake/llvm` and
`/usr/lib/llvm-22/lib/cmake/clang`.

For another distribution or a custom LLVM build, locate `LLVMConfig.cmake`
and `ClangConfig.cmake`, then pass their parent directories through
`LLVM_DIR` and `Clang_DIR`. The analyzer build prefers monolithic
`clang-cpp`/`LLVM` targets and falls back to component libraries when needed.

The reference protocol uses Full BMI. Reduced BMI is a separate experimental
condition and must be recorded in a separate run.

## Build `manalyzer`

From the repository root, the normal build is:

```bash
make build
```

The Makefile configures the root CMake project and places the executable at
`analyzer/build/manalyzer`. Its relevant variables are:

- `BUILD_DIR` — CMake build directory, default `analyzer/build`;
- `BUILD_TYPE` — CMake build type, default `RelWithDebInfo`;
- `CMAKE` — CMake executable, default `cmake`;
- `CMAKE_ARGS` — additional configure arguments.

For example:

```bash
make build BUILD_TYPE=Release \
  CMAKE_ARGS="-DLLVM_DIR=/path/to/llvm/lib/cmake/llvm -DClang_DIR=/path/to/clang/lib/cmake/clang"
```

Other targets are `make configure`, `make test`, `make validate`,
`make doctor`, and `make clean`. Direct CMake commands remain available for
unusual generators, but duplicating them is unnecessary for the normal path.

## Install the Python orchestrator

The root `pyproject.toml` maps the package to `python/orchestrator`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

This installs the `orchestrator` command. Installation is optional; a command
can instead be invoked as `PYTHONPATH=python python3 -m orchestrator ...`.

Copy and review the native toolchain configuration:

```bash
cp environment/toolchain.example.json environment/toolchain.json
orchestrator doctor --config environment/toolchain.json
```

`doctor` verifies both executables and rejects a mismatch in the required
LLVM/Clang patch version.

## Validate and run

```bash
orchestrator validate --scenarios scenarios

orchestrator run \
  --config environment/toolchain.json \
  --scenarios scenarios \
  --output results/runs/final-01

orchestrator aggregate \
  --run results/runs/final-01 \
  --output results/publication/final-01

orchestrator run \
  --config environment/toolchain.json \
  --scenarios scenarios \
  --output results/runs/final-02

orchestrator compare \
  --left results/runs/final-01 \
  --right results/runs/final-02
```

`final-02` is an independent repetition of the complete experiment. It is
created by the second `run` command and is used only to check determinism
against `final-01`.

During development, run one named scenario:

```bash
orchestrator run \
  --config environment/toolchain.json \
  --scenarios scenarios \
  --scenario overload.add_better_candidate \
  --output results/runs/single-scenario
```

`single-scenario` is only a descriptive output-directory name; `--output` may
point to any new directory. Earlier documentation used the conventional name
`smoke`, but that term carried no special behavior and has been removed.

## Result files

`run` writes raw artifacts. Every completed scenario receives:

```text
results/runs/final-01/<scenario_id>/prediction.json
results/runs/final-01/<scenario_id>/result.json
```

`prediction.json` requires no additional flag. It is written after provider
scans and before the after-consumer is compiled or analysed. `result.json`
then records both semantic observations, classifications, compiler status,
and the prediction hash.

`aggregate` produces four publication files:

- `results.csv` — one semicolon-delimited row per scenario;
- `results.jsonl` — complete scenario result objects;
- `summary.json` — aggregate counts and rates;
- `summary.md` — a readable rendering of the same summary.

Important CSV columns are:

- `scenario_status` — whether the harness completed the protocol or failed;
- `semantic_outcome_kind` — the consumer property used as the reference
  observation;
- `outcome_before` and `outcome_after` — that property's values;
- `outcome_changed` — whether those two values differ;
- `<criterion>_prediction` and `<criterion>_classification` — each criterion's
  decision and its comparison with the reference observation.

A semantic error in the after-consumer is a valid completed scenario, not a
harness failure. For example, `direct.remove_used_declaration` has
`scenario_status=completed`, `semantic_outcome_kind=compile_status`, and
`outcome_after=semantic_failure`.

## Tests and documentation

```bash
make test
make validate
```

Read the documents according to their distinct purpose:

- `docs/protocol.md` — research question, controls, criteria, and
  classification rules;
- `docs/architecture.md` — component boundaries and data flow;
- `docs/scenario_catalog.md` — scenario coverage and corpus invariants;
- `docs/reproduction.md` — execution and archiving checklist;
- `docs/verification.md` — current verification status and known invalidated
  results.

## Research context

[WG21 P3057R0](https://wg21.link/P3057R0) discusses a declaration-hash
direction that is relevant to used-declaration dependency tracking. It is one
piece of related context, not the centre of this experiment, not a source of
expected classifications, and not a specification implemented by this
repository. The experiment is centred on an independently stated empirical
question and uses clean compiler observations to evaluate the target
declaration-level criterion.
