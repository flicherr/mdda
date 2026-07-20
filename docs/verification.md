# Verification state

## Audit of the supplied pre-fix runs

The supplied x86-64 Linux audit bundle contains two LLVM/Clang 22.1.8 Full-BMI
runs. Both contain 28 completed scenarios, zero harness failures, and 28
scenario-level `prediction.json` files. `orchestrator compare` reports no
scientific-artifact differences between the runs.

Determinism alone did not establish semantic correctness. Review found two
issues that invalidate the supplied publication matrix:

1. the outcome extractor compared selected declarations only by Clang USR;
   three constrained-overload scenarios selected a different function and
   changed `int` to `long`, but their instantiated functions shared a USR, so
   the old code produced a false `outcome_changed=false`;
2. consumer scans materialized implicit constructors absent from provider
   scans; those constructors appeared as missing dependencies and also changed
   normalized class records, producing artificial `C_used` triggers.

The affected constrained scenarios are:

- `constraints.add_requires_expression_candidate`;
- `constraints.add_subsuming_candidate`;
- `overload.add_constrained_candidate`.

This source revision uses composite selection identities, preserves colliding
declarations, excludes on-demand implicit special members from dependency
records, and includes regression tests. The old
`results/publication/final-01` files must not be cited as final results.

Source-only verification of the semantic fixes validated all 28 manifests,
replayed the corrected outcome extractor over the supplied consumer scans, and
confirmed that exactly those three scenarios change from `false` to `true`.
The historical audit environment did not contain LLVM/Clang 22.1.8 development
files, so it could not rebuild the C++ executable.

## Revision 0.4.0 source and packaging checks

For the renamed source revision:

- all 28 Python unit tests pass;
- `orchestrator validate` accepts all 28 scenarios and reports the expected six
  families;
- the root `pyproject.toml` builds a wheel containing `orchestrator`, and the
  installed console entry point validates the corpus;
- the generated `results.csv` regression test verifies a semicolon delimiter;
- Makefile dry runs configure the root CMake project and preserve the documented
  `analyzer/build/manalyzer` path.

The verification workspace did not provide CMake or LLVM/Clang 22.1.8
development files, so the renamed C++ target still requires a clean build on
the target Arch or Debian-family environment before a new empirical run.

## Required final verification

After building the renamed `manalyzer`, create two new clean runs and regenerate
the publication directory. Record the following in this document or an
associated experiment log:

- host, distribution, architecture, and exact package versions;
- `manalyzer --version` and CMake configuration paths;
- Python test and manifest-validation results;
- 28/28 scenario completion and one prediction per scenario in both runs;
- deterministic comparison output;
- reviewed final matrix for both baselines and `C_used`;
- confirmation that `results.csv` is semicolon-delimited.

No final reference matrix is embedded in this revision because the supplied
raw runs were produced before the semantic fixes and before the executable and
orchestrator renaming.
