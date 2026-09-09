# Environment and execution

This document is the authoritative reference for platform-specific setup and
for executing the complete experiment. The root README introduces the project,
its components, and the command-line interface without duplicating the Docker
and operating-system package instructions below.

Two execution paths are available:

| Path | Platforms | Toolchain management |
|---|---|---|
| Docker | x86-64 Linux; x86-64 Windows through Docker Desktop | provided by the pinned image |
| Native | Linux installations with LLVM/Clang 22.1.8 development packages | managed by the user |

The container image is Linux/amd64. Other Docker hosts may run it through
architecture emulation, but that configuration has not been verified and
should not be used for a reference dataset without a separate validation.

## Docker

### Requirements

- on Linux: Docker Engine with permission to run containers;
- on Windows: Docker Desktop switched to Linux-container mode;
- enough free space for the Arch Linux image, LLVM/Clang development packages,
  the analyzer build, and two complete result directories.

Run all commands from the repository root.

### Build the image

The build command is the same on Linux and Windows:

```text
docker build --platform linux/amd64 -t mdda-experiment .
```

The image build:

1. installs packages from a dated Arch Linux repository snapshot;
2. verifies that `clang++` reports version 22.1.8;
3. builds `manalyzer` through the existing Makefile and CMake files;
4. runs all Python tests, validates the scenario corpus, and executes
   `orchestrator doctor`.

The build fails before an experiment starts if the analyzer cannot be linked,
tests fail, manifests are invalid, or the toolchain version is wrong.

### Run on Linux

In Bash or another POSIX-compatible shell:

```bash
mkdir -p results

docker run --rm --platform linux/amd64 \
  --mount "type=bind,source=${PWD}/results,target=/workspace/results" \
  mdda-experiment
```

### Run on Windows

In PowerShell:

```powershell
New-Item -ItemType Directory -Force results | Out-Null

docker run --rm --platform linux/amd64 `
  --mount "type=bind,source=$($PWD.Path)\results,target=/workspace/results" `
  mdda-experiment
```

The difference is limited to host-shell syntax. Both commands start the same
Linux image and execute the same protocol.

### What the default run does

The container entrypoint:

1. records the toolchain and installed package versions;
2. validates all 28 scenario manifests;
3. executes the complete corpus twice in independent output directories;
4. compares the runs after removing documented volatile fields;
5. aggregates the first run into publication-oriented artifacts.

The host receives:

```text
results/runs/run-01
results/runs/run-02
results/publication
```

The publication directory contains:

```text
summary.json
summary.md
results.csv
results.jsonl
toolchain.json
packages.txt
comparison.json
```

Existing output directories are never overwritten. Before another default
container run, move the previous `results` directory or mount a new empty one.
Custom one-off runs may use explicit `--output` paths through the CLI.

### Run an individual command

Any command supplied after the image name replaces the default full protocol.
For example, corpus validation requires no result mount:

```bash
docker run --rm --platform linux/amd64 mdda-experiment \
  python3 -m orchestrator validate --scenarios scenarios
```

An interactive shell is available with:

```bash
docker run --rm -it --platform linux/amd64 \
  --entrypoint /bin/bash mdda-experiment
```

The same commands work in PowerShell when written on one line or continued
with PowerShell backticks instead of backslashes.

## Native environment

The native path is useful for analyzer development and manual scenario runs.
Reference runs require one coherent LLVM/Clang 22.1.8 installation: `clang++`,
LLVM headers, Clang headers, `LLVMConfig.cmake`, and `ClangConfig.cmake` must
come from that installation.

Additional requirements:

- Python 3.11 or newer;
- CMake 3.20 or newer;
- Ninja;
- GNU Make for the provided Makefile wrapper.

### Install packages on Arch Linux

```bash
sudo pacman -S --needed clang llvm cmake ninja python make
```

Common package configuration directories are `/usr/lib/cmake/llvm` and
`/usr/lib/cmake/clang`. Arch Linux is rolling-release, so check the exact
package version before producing a reference dataset.

### Install packages on Debian or Ubuntu

With the apt.llvm.org repository configured:

```bash
sudo apt install clang-22 llvm-22-dev libclang-22-dev \
  cmake ninja-build python3 python3-venv make
```

Common configuration directories are `/usr/lib/llvm-22/lib/cmake/llvm` and
`/usr/lib/llvm-22/lib/cmake/clang`.

### Configure the toolchain

The repository contains a working reference configuration and a portable
template:

```bash
cp environment/toolchain.example.json environment/toolchain.json
```

Review at least these fields:

| Field | Meaning |
|---|---|
| `clangxx` | path or command used to invoke `clang++` |
| `analyzer` | path to `manalyzer`, normally `build/manalyzer` |
| `required_clang_version` | exact accepted version, `22.1.8` |
| `bmi_mode` | module representation, `full` for the reference condition |
| `target` | optional explicit target triple |

### Build and verify

```bash
make build
make test
make validate
make doctor
```

If CMake cannot locate LLVM or Clang, pass their package directories without
changing the project files:

```bash
make build CMAKE_ARGS="-G Ninja \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=1 \
  -DCMAKE_CXX_COMPILER=clang++ \
  -DCMAKE_C_COMPILER=clang \
  -DLLVM_DIR=/path/to/llvm/lib/cmake/llvm \
  -DClang_DIR=/path/to/clang/lib/cmake/clang"
```

### Install the orchestrator

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Installation is optional. Every command can instead be invoked as
`PYTHONPATH=python python3 -m orchestrator ...`.

### Execute the reference protocol

```bash
orchestrator doctor --config environment/toolchain.json
orchestrator validate --scenarios scenarios

orchestrator run \
  --config environment/toolchain.json \
  --scenarios scenarios \
  --output results/runs/run-01

orchestrator run \
  --config environment/toolchain.json \
  --scenarios scenarios \
  --output results/runs/run-02

orchestrator compare \
  --left results/runs/run-01 \
  --right results/runs/run-02

orchestrator aggregate \
  --run results/runs/run-01 \
  --output results/publication
```

Aggregate only after the deterministic comparison succeeds and both runs have
been reviewed for harness failures.

## Common problems

- **Docker uses Windows containers.** Switch Docker Desktop to Linux
  containers. The image cannot run as a Windows container.
- **An output directory already exists.** Move the existing results or mount
  an empty results directory. The entrypoint deliberately does not delete or
  overwrite experimental data.
- **The bind mount is empty.** Run the command from the repository root and
  create the local `results` directory before `docker run`.
- **The toolchain check rejects Clang.** Both `clang++` and the LibTooling
  libraries linked into `manalyzer` must be version 22.1.8.
- **CMake finds another LLVM installation.** Pass explicit `LLVM_DIR` and
  `Clang_DIR` values that point to the same 22.1.8 installation.
- **A native Windows build fails to locate LLVM dependencies.** The supported
  Windows reproduction path is the Linux container. Native Windows builds
  require additional MSVC and LLVM package-path configuration and are not the
  reference environment documented here.
