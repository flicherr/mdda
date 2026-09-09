# Experiment protocol

This document defines the scientific procedure. Installation and command-line
usage belong in the root `README.md`; implementation details belong in
`architecture.md`.

## Research question

For which controlled changes to C++20 module providers does equality of the
declarations previously used by a consumer agree with equality of a clean
semantic-analysis result, and for which language mechanisms is that
declaration-level criterion insufficient?

## Unit of analysis

One scenario contains byte-identical consumers and two provider states,
`before` and `after`. The provider ecosystem receives one documented mutation.
All module units are listed in topological build order.

## Controlled conditions

- The reference dataset uses LLVM/Clang 22.1.8 for both `clang++` and
  `manalyzer`.
- The reference dataset uses Full BMI. Reduced BMI is a different experimental
  condition and must be reported separately.
- Each state receives fresh PCM and module-cache directories; no BMI is shared
  between scenarios or between `before` and `after`.
- The consumer source is byte-identical across the two states.
- A scenario changes at least one provider source and declares one primary
  semantic observation.

## Reference baselines and evaluated criterion

The experiment has one evaluated criterion and two baselines:

- <i>C</i><sub>module</sub> is the maximally conservative source-change
  baseline. It returns `unchanged` only when every tracked provider source is
  byte-identical.
- <i>C</i><sub>interface</sub> is the exported-interface baseline. It returns
  `unchanged` only when the recursively exported surface of the primary
  provider is equal after AST normalization.
- <i>C</i><sub>used</sub> is the evaluated declaration-level criterion. It
  returns `unchanged` only when every unique declaration used in the previous
  consumer is matched unambiguously, has the same semantic fingerprint, and
  has an equal normalized representation. A fingerprint mismatch establishes
  a change without comparing the representations; matching fingerprints are
  verified by direct comparison so a hash collision cannot produce a false
  equality.

The first two criteria are retained because the research question concerns the
relative selectivity and safety of <i>C</i><sub>used</sub>. They are reference
points, not three equal centres of the study.

Missing, ambiguous, or unsupported declaration matches are classified as
`changed_or_unknown`. Declarations generated implicitly on demand are
represented through their explicit owning declaration and are not counted as
separate provider dependencies.

## Prediction and reference-observation boundary

A **reference observation** is the clean compiler result used to judge a
prediction. Some implementation fields and older research terminology call it
an *oracle result*; it is not another prediction algorithm.

For every scenario the experiment:

1. builds fresh `before` BMIs and verifies that the before-consumer compiles;
2. records the before-consumer observation `O0` and its used declarations;
3. builds and scans the `after` providers;
4. evaluates all criteria and writes `prediction.json`;
5. only then compiles or analyses the after-consumer with fresh BMIs and cache
   to obtain the reference observation `O1`;
6. sets `outcome_changed` to `O0 != O1` and classifies each prediction.

Writing and hashing the prediction before step 5 prevents the after-consumer
result from leaking into the predictor.

## Semantic observations

A scenario selects one of these consumer properties:

- selected declaration;
- expression type;
- selected specialization;
- deduced type;
- constraint result;
- name reachability or compilation status;
- normalized diagnostic class.

Selected declarations use a composite identity rather than a bare Clang USR.
The identity includes the structural declaration key, semantic selection
fields, and the primary template and constraints when applicable. Function
bodies are excluded because they do not determine overload selection.

`compile_status` states whether the consumer is well-formed against one
provider state. It is independent of `scenario_status`, which reports whether
the experimental pipeline itself completed successfully.

## Classification matrix

| Prediction | Outcome unchanged | Outcome changed |
|---|---|---|
| `unchanged` | `correct_skip` | `unsafe_skip` |
| `changed_or_unknown` | `conservative_trigger` | `correct_trigger` |

## Failure policy

- A failing after-consumer is a valid semantic observation.
- A failing before-consumer invalidates the scenario run.
- A module build failure, missing analyzer JSON, timeout, or compiler crash is
  a `harness_failure` and is excluded from scientific counts.
- `scenario_status=completed` means the protocol completed; it does not imply
  that the after-consumer compiled successfully.
- Raw commands, standard output, and standard error remain available for
  review.

## Interpretation limits

The corpus is deliberately constructed to cover language mechanisms. Its
rates do not estimate change frequency, prevalence, or build-time savings in
industrial repositories. Paired depth variants, such as the direct and
intermediate re-export scenarios, are robustness checks rather than
independent frequency samples.
