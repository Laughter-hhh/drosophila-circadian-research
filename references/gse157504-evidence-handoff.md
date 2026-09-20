# GSE157504 → candidate-evidence handoff

Use this handoff only after the GSE157504 raw-count and author-rhythm workflows have passed their own manifest checks. It creates candidate-evidence rows and structured source-log records; it does **not** assign candidate scores.

## What the handoff means

- A `direct` label means the source directly measured a transcript-level readout in an annotated clock-neuron group. It does not mean direct evidence that the channel carries current, controls membrane potential, or causes a behavior.
- Candidate scoring dimensions stay `NA`. There is no validated rule mapping a cell-level raw-UMI detection fraction or membership in an author high-confidence rhythm list to the existing 0–3 score scale.
- Zero raw UMI can reflect dropout. A missing exact feature symbol is not evaluable. A candidate absent from the authors' high-confidence table is merely “not listed under their criteria,” not proven arrhythmic.
- Do not classify an `LN_ITP`-only call as pure s-LNv or LNd evidence. Keep LD as ZT and DD as CT.
- The evidence log records the source and the analysis result separately; schema validation proves traceability, not that an interpretation is biologically sufficient.

## Run and validate

From the repository root, first copy the four lowercase SHA-256 values for the candidate list, feature-status table, group-detection table, and rhythm-detail table from their provenance manifest. The example below uses the currently bundled GSE157504 files; replace each hash when inputs change.

```powershell
python scripts/build_gse157504_candidate_evidence.py `
  validation/public-data/GSE22308_candidate_genes.csv `
  validation/public-data/GSE157504_candidate_raw_feature_status.csv `
  validation/public-data/GSE157504_candidate_raw_detection_by_group.csv `
  validation/public-data/GSE157504_candidate_rhythm_details.csv `
  --provenance-root . `
  --expected-candidate-sha256 <manifest hash> `
  --expected-feature-sha256 <manifest hash> `
  --expected-group-sha256 <manifest hash> `
  --expected-rhythm-sha256 <manifest hash> `
  --search-date YYYY-MM-DD `
  --evidence-output validation/public-data/GSE157504_candidate_evidence_handoff.csv `
  --search-log-output validation/public-data/GSE157504_candidate_evidence_search_log.csv `
  --report-output validation/public-data/GSE157504_candidate_evidence_handoff_report.json

python scripts/validate_evidence_search_log.py `
  validation/public-data/GSE157504_candidate_evidence_search_log.csv `
  --output validation/public-data/GSE157504_candidate_evidence_search_log_validation.json

python scripts/validate_candidate_evidence.py `
  validation/public-data/GSE157504_candidate_evidence_handoff.csv `
  --search-log validation/public-data/GSE157504_candidate_evidence_search_log.csv `
  --output validation/public-data/GSE157504_candidate_evidence_handoff_validation.json

python scripts/score_candidates.py `
  validation/public-data/GSE157504_candidate_evidence_handoff.csv `
  --output validation/public-data/GSE157504_candidate_evidence_score_diagnostic.csv `
  --sensitivity-output validation/public-data/GSE157504_candidate_evidence_score_sensitivity.json
```

All four scripts above are in the isolated public-manifest replay allowlist. Use `validation/public-data/GSE157504-candidate-evidence-bridge-manifest.json` to verify the input/output chain and replay it in an isolated mirror.

## Expected behavior on the currently bundled inputs

The verified example contains 15 candidates and 30 source-log rows (one raw-detection record plus one rhythm-table record per candidate). Fourteen candidates have at least one nonzero raw UMI in the specified target groups; nine have an author-reported high-confidence rhythm row in a pure target group. All seven numeric scoring dimensions remain `NA`, so the score diagnostic should mark all candidates `needs_evidence`, even when transcript-level `directness_gate` passes. This is a readiness/coverage result, not an evidence ranking.

After adding separately reviewed evidence (e.g. electrophysiology, adult-specific reagents and source-checked genetic tools), rerun the candidate validator and scorer on a merged table. Do not overwrite this handoff to imply that transcript-only rows support electrophysiological or causal claims.

## Primary sources

- Ma, D. et al. A transcriptomic taxonomy of Drosophila circadian neurons around the clock. *eLife* **10**, e63056 (2021). https://doi.org/10.7554/eLife.63056.
- NCBI GEO Series GSE157504: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504.
- Official eLife Supplementary file 1: https://cdn.elifesciences.org/articles/63056/elife-63056-supp1-v2.xlsx.
