# Iteration record — readout-specific candidate directness

Date: 2026-09-20  
Status: `verified` for evidence-triage semantics and reproducible public-data output; not a channel-function or causal biology validation.

## Observed issue

The real GSE157504 candidate diagnostic showed transcript-only rows with `directness_score=3` and `directness_gate=pass`, because the rows have a named assay and a direct target-neuron expression readout. The same rows correctly had blank total score, zero evidence coverage, and `shortlist_gate=needs_evidence`; nevertheless, “directness” could be misread as direct evidence that the channel contributes current or membrane-potential rhythm.

## Changes

- `scripts/score_candidates.py` now emits `readout_domain` and makes `directness_basis` readout-specific. Direct molecular expression/localization is explicitly limited to that molecular observation and says it does not establish channel current, membrane-potential rhythm, or channel-specific causality. A current/membrane-potential observation is likewise distinguished from candidate-specific causality, which requires a documented perturbation and appropriate controls.
- The sensitivity report now states that directness is matched-readout-specific and that the shortlist gate is an evidence-triage rule, not a causal conclusion.
- `references/candidate-ranking.md` now explains these distinctions and retains the existing evidence-label vocabulary and compatibility behavior.
- Added `tests/test_candidate_scoring_readout_scope.py` for direct transcript evidence, direct electrophysiology observations, and sensitivity-report wording. Earlier scorer behavior is preserved in `validation/legacy-score_candidates-20260920-before-readout-scope.py`; the prior candidate-ranking text is preserved in `validation/legacy-candidate-ranking-20260920-before-readout-scope.md`.
- Regenerated the GSE157504 score diagnostic and sensitivity output and refreshed the bridge manifest with the new scorer/output hashes.

## Verification

- Focused candidate-scoring tests: 9 passed.
- GSE157504 synthetic/real bridge tests with `ResourceWarning` promoted to an error: 4 passed.
- Full repository suite after the scorer change: 245 passed.
- Bridge manifest: `verified_public_dataset_manifest`, 11 files, 4 runs, 0 issues and 0 warnings.
- Isolated replay: `verified_public_dataset_replay`, 4 runs, all 7 declared output hashes matched.
- Research task contract validates and is marked `verified`.

## Current real-data interpretation

All 15 GSE157504 candidates remain `needs_evidence`; all seven numeric ranking dimensions remain `NA`. Rows with a direct target-cell transcript readout now visibly report `readout_domain=molecular_expression_or_localization`; this is evidence of a molecular readout in annotated clock-neuron cells, not channel current or function. The author's rhythmic-gene table remains a published transcript-level call, not a rhythm model refit here. LD is kept as ZT, DD as CT, and mixed `LN_ITP` evidence is not relabeled as pure s-LNv/LNd evidence.

The source article describes clock-neuron single-cell RNA sequencing under LD and DD across six time points, with two replicates per condition/time point, and deposits the data under GSE157504. The official supplementary-file description identifies Supplementary file 1 as rhythmic genes by cluster and LD/DD condition. The present workflow transfers these reported observations; it does not establish channel protein, current, membrane-potential rhythm, or behavior causality.

## Remaining validation boundary

The official `skill-creator` `quick_validate.py` remains unavailable in the bundled Python runtime because PyYAML is not installed; it was not installed as part of this iteration. No SKILL frontmatter changed in this iteration. The next scientific evidence upgrade is to add source-checked candidate perturbation plus target-neuron current/membrane-potential evidence, rather than assigning stronger meaning to transcript directness.

## Sources

- Ma, D. et al. A transcriptomic taxonomy of *Drosophila* circadian neurons around the clock. *eLife* **10**, e63056 (2021). https://doi.org/10.7554/eLife.63056.
- eLife figures and data, including descriptions of Supplementary file 1. https://elifesciences.org/articles/63056/figures.
- NCBI GEO, GSE157504. https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504.
