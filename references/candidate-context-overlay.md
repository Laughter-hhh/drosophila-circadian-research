# Candidate transcript-context overlay

Use this as a **sidecar** after the literature candidate table, checked source log, target-specific score files, and GSE157504 raw-detection/rhythm outputs have been validated. The overlay is not a ranking step: it never feeds transcript counts or author rhythm-list membership into the 0–3 score or the electrophysiology directness gate.

## Run

The bundled example uses 15 literature candidates and four target groups. Run from the repository root:

```powershell
python scripts/build_candidate_evidence_context.py `
  --candidate-table validation/public-data/candidate-evidence-real.csv `
  --search-log validation/public-data/candidate-evidence-search-log.csv `
  --feature-status validation/public-data/GSE157504_candidate_raw_feature_status.csv `
  --group-detection validation/public-data/GSE157504_candidate_raw_detection_by_group.csv `
  --rhythm-details validation/public-data/GSE157504_candidate_rhythm_details.csv `
  --rhythm-manifest validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json `
  --rhythm-validation validation/public-data/GSE157504-candidate-channel-rhythm-manifest-validation.json `
  --rhythm-replay validation/public-data/GSE157504-candidate-channel-rhythm-replay.json `
  --target-score s-LNv=validation/public-data/candidate-target-cell-score-slnv.csv `
  --target-score l-LNv=validation/public-data/candidate-target-cell-score-llnv.csv `
  --target-score LNd=validation/public-data/candidate-target-cell-score-lnd.csv `
  --target-score DN=validation/public-data/candidate-target-cell-score-dn.csv `
  --context-output validation/public-data/GSE157504_candidate_context_overlay.csv `
  --report-output validation/public-data/GSE157504_candidate_context_overlay_report.json `
  --manifest-output validation/public-data/GSE157504-candidate-context-overlay-manifest.json

python scripts/validate_public_dataset_manifest.py `
  validation/public-data/GSE157504-candidate-context-overlay-manifest.json `
  --root . `
  --output validation/public-data/GSE157504-candidate-context-overlay-manifest-validation.json

python scripts/replay_public_dataset_manifest.py `
  validation/public-data/GSE157504-candidate-context-overlay-manifest.json `
  --root . `
  --output validation/public-data/GSE157504-candidate-context-overlay-replay.json
```

The builder stops if the candidate table or search log fails validation, the upstream GSE manifest/isolated replay does not verify the exact feature/detection/rhythm input hashes, the target-score candidate sets differ, or a recomputed target score/gate disagrees with the existing target-specific score artifact.

## Read the sidecar conservatively

- There is one row per literature candidate × target group. `literature_class` and GSE `priority_class` are kept in separate columns because they are different classifications.
- `LD` is reported as `ZT`; `DD` is reported as `CT`. Raw UMI counts/fractions are descriptive cell-level measurements, not independent-fly inference.
- If a target group/condition has zero annotated cells, its count is zero but the detection fraction and per-cell mean are undefined and reported `NA`; this is not a biological non-detection. The builder rejects internally inconsistent zero-cell rows and prevents outputs from overwriting any supplied input or executable helper.
- Zero detected cells are labelled dropout-sensitive, not biologically absent. A gene without an exact feature record (or a candidate not included in the upstream candidate audit) receives `NA` detection fields and an explicit not-evaluable status.
- An absent author high-confidence (HC) call means “not listed under author criteria,” not proven arrhythmic. When the literature candidate was not in the upstream candidate audit, its rhythm status is also not evaluable.
- `LN_ITP` calls stay in their own ambiguous field and are never assigned to pure s-LNv or LNd. DN calls retain exact author cluster names (for example, DN1p); a DN-subcluster call is not evidence for all DN.
- `static_rationale_review_flag=review` asks a human to reconcile wording where transcript context may conflict with a static “missing target/circadian evidence” rationale. It does not rewrite the source evidence, promote expression to electrophysiology, change scores, or remove the ephys gate.
- The report records differences between the literature shortlist and GSE audit candidate sets. Do not silently add/drop genes to force them to match.

## Provenance boundary

The context manifest hashes candidate and source-log inputs, four target-score files, GSE-derived inputs, the upstream raw/rhythm manifest/validation/replay, the context CSV/report, and the builder script. The validator checks file integrity and declared provenance; isolated replay checks deterministic reproducibility and output hashes. Neither establishes biological validity, normalization suitability, independent biological replication, channel function, or causality.
