# Combined candidate transcript context

## Purpose and boundary

Use this workflow to display two already audited transcript evidence sources alongside the existing literature/electrophysiology candidate context:

1. GSE157504 candidate-level raw-UMI and author-rhythm context;
2. Abruzzi et al. (2017) Supplementary Table S3 author-reported HC/LC transcript-cycling calls.

This is a score-neutral sidecar. It copies every input context column verbatim; it does not rerank candidates, recalculate a score, revise an electrophysiology gate, refit rhythm statistics, or infer channel function. Read `candidate-context-overlay.md` and `published-cycle-table-workflow.md` first.

The PLOS candidate audit must preserve its source status, including the manuscript-versus-S3 LNv HC count discrepancy. `verified` parent manifests/replays mean file lineage and deterministic output hashes were reproduced, not that the transcript calls establish a physiological mechanism.

## Explicit source-group crosswalk

| Existing target row | PLOS S3 source group | Required interpretation |
|---|---|---|
| `s-LNv` | `LNv_PDF_positive_small_and_large_mixed` | Pooled PDF-positive s-/l-LNv context; the call cannot be assigned to one subtype. |
| `l-LNv` | `LNv_PDF_positive_small_and_large_mixed` | Same pooled source group; displaying the call on this row does not make it l-LNv-specific. |
| `LNd` | `LNd_plus_fifth_PDF_negative_s_LNv` | The source group includes the fifth PDF-negative s-LNv and is not LNd-only. |
| `DN` | `DN1_subset` | The source data cover a DN1 subset, not all DN or all DN1 subtypes. |

The crosswalk is for contextual comparison only. It does not assert that the author groups are equivalent to the target-specific groups in the GSE overlay.

## Status and output fields

- `published_cycle_author_class`: `HC`, `LC`, `not_listed`, `not_evaluable`, or `conflict`.
- `published_cycle_record_status` distinguishes an author-list omission from a candidate absent from the PLOS audit set, an unmapped target group, an incomplete source row, or conflicting duplicate source records.
- `published_cycle_source_rows_json` and `published_cycle_author_calls_json` retain source row IDs and author F24/JTK flags. Conflicting duplicate rows are preserved and surfaced rather than collapsed into one call.
- `published_cycle_audit_entry_count` counts matching audit CSV rows (including a `not_listed` placeholder); `published_cycle_source_row_count` counts actual matched S3 workbook rows.
- `published_cycle_source_scope_note` and `published_cycle_target_scope_relation` state how the source group relates to the requested target group.
- All original GSE detection/rhythm, literature-score, coverage, directness, shortlist, and readout fields remain unchanged.

`not_listed` means not listed under the author's reported criteria in that source table; it does not mean unexpressed or biologically arrhythmic. A transcript-cycling call does not establish channel protein abundance, membrane current, membrane-potential rhythm, or causal behavioral function.

## Reproducible command

Run from the repository root after confirming that both parent source manifests and their isolated replays still validate:

```powershell
python scripts/build_published_cycle_candidate_context.py `
  --gse-context validation/public-data/GSE157504_candidate_context_overlay.csv `
  --gse-report validation/public-data/GSE157504_candidate_context_overlay_report.json `
  --gse-manifest validation/public-data/GSE157504-candidate-context-overlay-manifest.json `
  --gse-validation validation/public-data/GSE157504-candidate-context-overlay-manifest-validation.json `
  --gse-replay validation/public-data/GSE157504-candidate-context-overlay-replay.json `
  --cycle-evidence validation/public-data/Abruzzi2017_channel-candidate-cycle-evidence.csv `
  --cycle-report validation/public-data/Abruzzi2017_channel-candidate-cycle-audit.json `
  --cycle-manifest validation/public-data/Abruzzi2017-candidate-cycle-manifest.json `
  --cycle-validation validation/public-data/Abruzzi2017-candidate-cycle-manifest-validation.json `
  --cycle-replay validation/public-data/Abruzzi2017-candidate-cycle-replay.json `
  --output-csv validation/public-data/combined-transcript-candidate-context.csv `
  --output-report validation/public-data/combined-transcript-candidate-context-report.json `
  --manifest-output validation/public-data/combined-transcript-candidate-context-manifest.json

python scripts/validate_public_dataset_manifest.py `
  validation/public-data/combined-transcript-candidate-context-manifest.json `
  --root . `
  --output validation/public-data/combined-transcript-candidate-context-manifest-validation.json

python scripts/replay_public_dataset_manifest.py `
  validation/public-data/combined-transcript-candidate-context-manifest.json `
  --root . `
  --timeout-seconds 180 `
  --output validation/public-data/combined-transcript-candidate-context-replay.json
```

The combined builder revalidates both parent manifests against current files, requires the parents' stored isolated replays to verify the exact CSV and report hashes, and cross-checks the S3 audit CSV against its report. Its own manifest includes both parent manifests' transitive file records plus the validation/replay records. The combined manifest validator and replay must pass before the research-task contract can be marked `verified`.

## Current real-data result

The current 15-candidate context emits 60 candidate-by-target rows. Six distinct candidate-by-source-group calls (six S3 source rows across five genes) map to nine target rows: `Shab` is HC in the pooled LNv group (shown on both s-LNv and l-LNv context rows without subtype resolution) and LC in the DN1 subset; `Sh` and `cac` are LC in the mixed LNd group; `para` and `sei` are LC in the pooled LNv group. The remaining 51 mapped target rows are `not_listed` in the selected PLOS cycler sheets. The nine expanded target rows are not nine independent source calls. These transcript calls are supplemental context, not membrane-current evidence.

The GSE overlay's separate candidate-set difference (`na` absent from the GSE candidate audit; `eag` present only in that audit) is preserved unchanged. The PLOS S3 audit itself still reports 252 unique LNv HC symbols versus 249 in the manuscript narrative; both values remain visible and unreconciled.

## Source

Abruzzi, K. C. et al. RNA-seq analysis of Drosophila clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides. *PLoS Genet.* **13**, e1006613 (2017). [Article](https://doi.org/10.1371/journal.pgen.1006613); [Supplementary Table S3](https://doi.org/10.1371/journal.pgen.1006613.s003).
