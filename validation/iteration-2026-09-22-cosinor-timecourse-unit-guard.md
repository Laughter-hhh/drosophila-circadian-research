# Iteration report: course-aware exploratory cosinor and pooled-unit guard

Date: 2026-09-22

## Finding reproduced on public data

Before this change, `scripts/analyze_cosinor_inference.py` grouped expression rows by gene, cell type, background, developmental stage and sex, but not by `timecourse_id`. On GSE77451, the two separately mapped LNv six-point courses were therefore merged into one 12-observation inference group. Candidate groups whose expression values were all blank were dropped before grouping, so Ork1/LNv had no output record. For `pooled_neuron_library`, GSM/library identifiers were also reported as biological-replicate counts, although they are not individual-fly replicates.

## Changes

- Added `timecourse_id` to inference grouping and metadata reconciliation. If course labels exist for some samples but cannot be resolved for others, inference now stops rather than mixing a partially identified course with known courses.
- Retained blank-expression rows in their mapped groups. A group with no numeric expression is emitted as `no_numeric_expression`, with missing-row counts and an explicit warning that matrix nonrepresentation does not demonstrate biological absence.
- Distinguished library/sample-unit counts from biological n. For pooled or library material, rows are keyed/resampled by sample/library ID, `n_sample_units` counts those IDs, while `n_subjects` and `n_biological_replicates` are `null`; exploratory results carry a pooled-unit warning.
- Updated the main skill and the GEO/cosinor workflow documents to make these analysis gates explicit.
- Added a dedicated GSE77451 provenance manifest for all three transcript-to-gene aggregation scenarios and refreshed the existing GSE22308 manifest hashes/outputs for the modified inference script.

## Validation

- Focused cosinor-inference tests: **20 passed**. New checks cover separate course strata, course-label conflicts/partial mapping, pooled-unit counts, retained all-missing groups, and the public GSE77451 case.
- Full repository suite: **333 passed**.
- GSE77451 (`sum`, `median`, `max`): each run retained **90** candidate × cell-group × course strata; each had **88** numeric groups and **2** `no_numeric_expression` groups. Shaw/LNv was split into its two six-point courses; Ork1/LNv remained explicitly represented as missing in both courses. All pooled/library groups report no animal-level replicate n.
- GSE77451 provenance: manifest validation passed and isolated replay verified **3 runs / 3 output hashes**.
- GSE22308: the prior 1000-permutation/1000-bootstrap commands were regenerated with the current script and the updated manifest validation/replay completed successfully.
- The `skill-creator` `quick_validate.py` could not start because the available bundled Python lacks the `PyYAML` dependency (`ModuleNotFoundError: yaml`). No package was installed. Repository tests and manifest/replay checks were run independently.

## Interpretation limits

These checks establish implementation behavior, local file integrity and deterministic replay only. GSE77451 course labels are curator mappings, not verified experimental batch or individual-fly identifiers. The samples are pooled neuron libraries, transcript scale/normalization remains unresolved, and the broad LNv/LNd/DN1 labels do not resolve the requested clock-neuron subtypes. The cosinor p-values and bootstrap intervals remain exploratory; they do not establish biological rhythmicity in an individual neuron, a channel-to-membrane-potential mechanism, or causality.

## Files

- Implementation: `scripts/analyze_cosinor_inference.py`
- Regression tests: `tests/test_cosinor_inference.py`
- Method references: `references/cosinor-inference.md`, `references/geo-data-workflow.md`
- GSE77451 inference outputs: `validation/public-data/GSE77451-esat-candidate-inference-{sum,median,max}-20260922.json`
- GSE77451 provenance and replay: `validation/public-data/GSE77451-esat-candidate-inference-provenance-manifest.json`, `validation/public-data/GSE77451-esat-candidate-inference-replay.json`
