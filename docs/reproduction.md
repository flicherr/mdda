# Reproduction checklist

The root `README.md` is the authoritative command reference. This checklist
records the evidence that must accompany a reproducible paper run rather than
duplicating those commands.

1. Record the operating system, distribution, architecture, Clang full
   version, target triple, and standard library.
2. Install LLVM/Clang 22.1.8 development files from one coherent toolchain.
3. Build `manalyzer` from the root project and record `manalyzer --version`.
4. Copy and review `environment/toolchain.example.json`, then run `doctor`.
5. Run the Python tests and validate the 28-scenario corpus.
6. Execute one named scenario and inspect its `prediction.json` and
   `result.json`.
7. Execute the full corpus twice in independent output directories.
8. Compare those runs and investigate every differing scientific artifact or
   harness failure.
9. Aggregate only a complete, reviewed run.
10. Verify the constrained-candidate scenarios: the selected declaration must
    change even when Clang supplies a colliding instantiated-function USR.
11. Archive the source tree, both raw runs, publication outputs, toolchain
    snapshot, and exact article revision together.

Every state must use dedicated BMI and module-cache directories. Full and
Reduced BMI runs must be archived and reported as separate experimental
conditions. The arbitrary output label used for a one-scenario check does not
change the protocol.
