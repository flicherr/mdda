# Scenario catalog

The current research revision defines a version-controlled core corpus of 28
deliberately constructed scenarios. It is fixed for comparisons made within
that revision, but it is not inherently immutable: future corpus revisions may
add scenarios and must be versioned and reported explicitly.

The table describes mechanisms and observations. It does not store expected
scientific classifications; those are derived from clean reference
observations.

| ID | Family | Mutation | Observation |
|---|---|---|---|
| `controls.comment_only` | direct/control | comment text | selected declaration |
| `controls.unused_noninline_body` | direct/control | unused private body | selected declaration |
| `controls.add_different_name` | direct/control | unrelated exported name | selected declaration |
| `direct.change_used_signature` | direct/control | used parameter type | selected declaration |
| `direct.remove_used_declaration` | direct/control | remove used function | compile status |
| `overload.add_better_candidate` | lookup/overload | exact-match overload | selected declaration |
| `overload.add_ambiguous_candidate` | lookup/overload | equal-rank overload | compile status |
| `overload.add_non_template_candidate` | lookup/overload | non-template competitor | selected declaration |
| `overload.add_constrained_candidate` | lookup/overload | constrained competitor | selected declaration |
| `lookup.export_using_changes_overload_set` | lookup/overload | target before exported using | selected declaration |
| `adl.add_associated_namespace_function` | ADL/conversion | associated-namespace function | selected declaration |
| `adl.add_hidden_friend` | ADL/conversion | hidden friend | selected declaration |
| `adl.add_nonmember_operator` | ADL/conversion | non-member operator | expression type |
| `conversion.add_better_conversion_function` | ADL/conversion | conversion function | selected declaration |
| `adl.new_candidate_beats_ordinary_lookup` | ADL/conversion | better ADL reference binding | selected declaration |
| `templates.sfinae_candidate_becomes_viable` | templates/constraints | nested type enables substitution | selected declaration |
| `constraints.add_requires_expression_candidate` | templates/constraints | requires-expression overload | selected declaration |
| `constraints.add_subsuming_candidate` | templates/constraints | subsuming named constraint | selected declaration |
| `constraints.change_concept_satisfaction` | templates/constraints | concept predicate threshold | constraint result |
| `templates.remove_instantiation_requirement` | templates/constraints | remove required nested type | compile status |
| `specialization.add_partial_specialization` | specialization/CTAD | pointer partial specialization | expression type |
| `specialization.add_explicit_specialization` | specialization/CTAD | explicit specialization | expression type |
| `deduction.add_exact_guide` | specialization/CTAD | exact deduction guide | deduced type |
| `deduction.add_constrained_guide` | specialization/CTAD | constrained deduction guide | deduced type |
| `reexport.add_export_import_overload` | re-export | private import becomes exported | selected declaration |
| `reexport.remove_export_import` | re-export | exported import becomes private | reachability |
| `reexport.break_intermediate_chain` | re-export | intermediate edge becomes private | reachability |
| `reexport.new_reachable_candidate` | re-export | re-exported non-template competitor | selected declaration |

## Corpus invariants

- every `before` consumer compiles;
- `before/consumer.cpp` and `after/consumer.cpp` are byte-identical;
- at least one provider module source differs;
- module lists and order are identical between states;
- each state uses a fresh BMI directory and module cache;
- each scenario has one primary observation;
- language-rule references are recorded in the manifest;
- no manifest field pre-commits the reference result.

Five scenarios intentionally make the after-consumer ill-formed. The pipeline
treats those failures as semantic observations rather than harness failures.

`reexport.remove_export_import` and `reexport.break_intermediate_chain` are a
paired depth check of one reachability rule. The first changes the module
imported directly by the consumer. The second leaves that top-level module
textually unchanged and breaks a lower re-export edge. The extra level tests
whether recursive reachability is handled transitively; it is not a separate
language mechanism or an independent frequency sample.
