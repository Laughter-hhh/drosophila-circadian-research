# Iteration record — GSE157504 evidence handoff

Date: 2026-09-20  
Status: `verified` for deterministic transcript-evidence handoff; not verified for channel function, membrane-potential rhythm, or behavior causality.

## Research workflow gap

The existing GSE157504 workflow could audit exact feature representation, raw UMI detection by annotated group, and the authors' reported rhythmic-gene table, but it did not have a schema-safe handoff into the candidate-evidence and evidence-search-log validators. Simply scoring this transcript evidence would overstate what the assay measures. A second provenance defect was found during this iteration: the bridge manifest contained a space inside one output SHA-256, which caused the manifest gate to reject an otherwise complete chain.

## Changes made

- Added `scripts/build_gse157504_candidate_evidence.py`. It hash-checks the candidate list, feature-status table, group-detection table, and author-rhythm detail table before writing outputs. It emits one evidence row and two traceable source-log records per candidate. It treats raw UMI detection and published rhythm-list membership as transcript-level observations only, preserves LD as ZT and DD as CT, does not transfer `LN_ITP`-only rows to pure s-LNv/LNd evidence, and leaves the seven numeric ranking dimensions `NA`.
- Added synthetic and real-data coverage in `tests/test_gse157504_candidate_evidence_bridge.py`: positive target-group detection, missing exact feature, zero counts/dropout, mixed `LN_ITP`, hash mismatch, condition/time-system mismatch, schema validation, and a bundled-data integration check.
- Added the four bridge/validator/scorer scripts to the reviewed allowlist in `scripts/replay_public_dataset_manifest.py`; added tests that confirm these exact scripts can replay and an unreviewed script remains blocked.
- Added `references/gse157504-evidence-handoff.md`, linked from `references/published-sc-clock-rhythm-audit.md`, plus a machine-readable verified task contract.
- Corrected the malformed manifest digest for `GSE157504_candidate_evidence_handoff_validation.json` to `ea63d330e49330fc7a1f9f3e2c5a39bc390daba82d7bb1dd9a7b2e3edfdd9f7b`. The pre-fix manifest is preserved at `validation/legacy-GSE157504-candidate-evidence-bridge-manifest-20260920-before-hash-fix.json` so the failure remains auditable.

## Real-data result

The handoff used the bundled, hash-identified GSE157504-derived inputs. It produced 15 candidate rows and 30 source-log rows. Fourteen candidates had at least one nonzero raw UMI observation in the defined target groups; nine had an author-reported high-confidence rhythmic row in a target group. These are transcript-level summaries of cells nested within collection replicates, not fly-level prevalence estimates. The candidate evidence and search log passed their schema validators. All seven numeric candidate evidence dimensions remain `NA`, and the diagnostic marks all 15 candidates `needs_evidence`; this is not a ranked list.

The source paper reports single-cell RNA sequencing of Drosophila clock neurons across six time points under LD and DD, with two replicates per condition/time point; it deposits the data as GSE157504. Its Supplementary file 1 lists author-identified rhythmic genes by cluster and LD/DD condition. This iteration reuses the existing extracted tables; it does not rerun the authors' rhythm model or normalize the raw matrices.

## Verification evidence

- Manifest gate: `verified_public_dataset_manifest`, 11 files, 4 runs, 0 issues, 0 warnings.
- Isolated replay: `verified_public_dataset_replay`, 4 runs, 7 output SHA-256 checks, 0 mismatches.
- Focused bridge/replay tests with `-W error::ResourceWarning`: 6 passed.
- Complete automated suite via `scripts/run_tests.py`: 242 passed.
- `scripts/validate_research_task.py validation/GSE157504-candidate-evidence-bridge-task.json`: passed.
- `scripts/quick_validate.py` could not start because the configured Python runtime lacks `PyYAML` (`ModuleNotFoundError: No module named 'yaml'`). No dependency was installed. The `SKILL.md` frontmatter was inspected manually (required `name` and `description`, allowed keys, hyphen-case name, no unfinished TODO placeholder); this manual review is not represented as a successful run of the official quick validator.

## Remaining limits and next experiment

The data cannot distinguish transcript detection from translated channel protein, membrane localization, conductance, or contribution to rhythmic membrane potential. Zero counts can reflect dropout; absence from the author table means only “not listed under those criteria.” The next evidence upgrade should add independently source-checked target-neuron electrophysiology or validated genetic/pharmacological perturbation records to the candidate evidence log, then test one candidate with an adult-restricted pilot that measures a defined current or resting membrane potential at matched circadian times before proposing a multi-edge causal experiment.

## Sources checked

- Ma, D. et al. A transcriptomic taxonomy of *Drosophila* circadian neurons around the clock. *eLife* **10**, e63056 (2021). https://doi.org/10.7554/eLife.63056.
- NCBI Gene Expression Omnibus, GSE157504. https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504.
- eLife figures/data and supplementary-file descriptions. https://elifesciences.org/articles/63056/figures.
