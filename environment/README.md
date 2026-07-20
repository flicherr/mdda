# Environment

`toolchain.example.json` is the portable template. Copy it to
`toolchain.json`, then set `clangxx` and `analyzer` to the exact binaries used
for the run. Both must report LLVM/Clang 22.1.8. The reference configuration
uses Full BMI.

Distribution-specific package examples and CMake path guidance are in the
root `README.md`. The optional container configures the root CMake project and
builds `manalyzer`:

```bash
docker build -f environment/Containerfile \
  -t module-declaration-dependency-analysis .
docker run --rm module-declaration-dependency-analysis
```

To persist experimental output:

```bash
docker run --rm \
  -v "$PWD/results:/artifact/results" \
  module-declaration-dependency-analysis \
  python3 -m orchestrator run \
    --config environment/toolchain.json \
    --scenarios scenarios \
    --output results/runs/container-run
```

Before a paper run, record the image digest and installed package versions.
Package repositories are mutable; `orchestrator doctor` still enforces the
required LLVM/Clang patch version, while every run stores the full toolchain
snapshot.
