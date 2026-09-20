# Published single-cell clock-neuron channel evidence audit

Use this workflow when screening candidate ion-channel transcripts in the Drosophila clock-neuron single-cell dataset GSE157504. It has two deliberately separate evidence layers:

1. **Raw-count detection:** whether an exact candidate gene symbol has a nonzero raw UMI count in annotated cells. This is descriptive and subject to single-cell dropout.
2. **Published rhythm calls:** whether the authors listed the candidate among their high-confidence rhythmic transcripts in a cluster and LD/DD condition. This transcribes their result; it does not refit their model.

Neither layer establishes protein abundance, channel current, membrane-potential rhythm, or causal control of behavior. Feed these as evidence rows into the normal candidate-ranking workflow, not as an automatic final rank. For a schema-validated, non-scoring handoff to candidate ranking, also read [gse157504-evidence-handoff.md](gse157504-evidence-handoff.md).

## Reproducible workflow

Keep the accession, source URLs, input hashes, scripts, outputs, readable commands, structured `command_argv`, and analysis context in `validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json`. Validate and isolate-replay it with:

```powershell
python scripts/validate_public_dataset_manifest.py validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json --root .
python scripts/replay_public_dataset_manifest.py validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json --root . --timeout-seconds 120 --output validation/public-data/GSE157504-candidate-channel-rhythm-replay.json
```

Raw-count join and detection:

```powershell
python scripts/audit_gse157504_candidate_detection.py `
  validation/public-data/GSE157504_RAW.tar `
  validation/public-data/GSE157504_clock_neurons_annotation.csv `
  validation/public-data/GSE22308_candidate_genes.csv `
  --provenance-root . `
  --expected-raw-sha256 <manifest hash> `
  --expected-annotation-sha256 <manifest hash> `
  --expected-candidate-sha256 <manifest hash> `
  --sample-output validation/public-data/GSE157504_candidate_raw_detection_by_sample.csv `
  --group-output validation/public-data/GSE157504_candidate_raw_detection_by_group.csv `
  --feature-output validation/public-data/GSE157504_candidate_raw_feature_status.csv `
  --report-output validation/public-data/GSE157504_candidate_raw_detection_audit.json
```

Published author rhythm calls:

```powershell
python scripts/extract_published_sc_clock_channel_rhythms.py `
  validation/public-data/GSE22308_candidate_genes.csv `
  validation/public-data/GSE157504_published_rhythmic_genes_supp1.xlsx `
  --source-url https://elifesciences.org/articles/63056 `
  --provenance-root . `
  --expected-candidate-sha256 <manifest hash> `
  --expected-supplement-sha256 <manifest hash> `
  --summary-output validation/public-data/GSE157504_candidate_rhythm_summary.csv `
  --detail-output validation/public-data/GSE157504_candidate_rhythm_details.csv `
  --report-output validation/public-data/GSE157504_candidate_rhythm_extraction.json
```

The expected hashes are the lowercase SHA-256 values in the manifest. Do not remove hash checks in a formal rerun. `openpyxl` is needed for the supplementary workbook; the raw tar join uses the Python standard library.

## Barcode, condition, and cell-type rules

- The provided annotation contains 2,615 cell IDs assigned to 17 high-confidence clusters. The raw archive has 84 compressed matrices and 8,060 cell columns; columns outside this annotation are not silently assigned to one of the 17 clusters.
- The join strips a single R-generated leading `X` and compares IDs case-insensitively. For DD only, it normalizes annotation ID tokens `_ztNN_` to the raw matrix `_CTNN_` form. This is a documented, condition-aware alias, not a claim that DD samples are in ZT.
- Report LD time as ZT and DD time as CT. The author annotation's `time` and ID strings may carry a `ztNN` token for DD; that token must not overwrite the experimental condition.
- Cluster labels `s_LNv`, `l_LNv`, `LNd...`, and `DN...` are grouped as s-LNv, l-LNv, LNd, and DN. Keep cluster IDs and labels in the detailed output.
- `LN_ITP` is intentionally classified as `LN_ITP_ambiguous`, not forced into s-LNv or LNd: the paper states this cluster combines the fifth PDF-negative s-LNv with an ITP-positive LNd. Do not attribute this cluster's channel call to a pure cell class.
- A candidate omitted from the exact raw feature-symbol table is `not_evaluable_in_this_matrix`, not biologically absent. In this dataset's current symbol list, `para` is not represented exactly; check aliases/annotation and an orthogonal assay before excluding it.

## Interpreting outputs

- `candidate_raw_detection_by_sample.csv` preserves candidate × cluster × condition × replicate × phase. Each detection fraction is `n raw counts > 0 / n uniquely matched annotated cells` for that row.
- `candidate_raw_detection_by_group.csv` pools annotated cells across time points and collection replicates for descriptive summaries. It is not a replicate-level effect estimate or LD-vs-DD test.
- `candidate_raw_feature_status.csv` reports exact feature presence and pooled raw detection across the annotated cells. Zero UMI counts can reflect dropout; nonzero counts do not prove functional protein or a current.
- The published supplement contains author-reported high-confidence cyclers, not a complete table of every tested gene. Its stated cutoffs include JTK adjusted q < 0.05, F24 > 0.5, at least 1.5-fold amplitude (with a specified zero-minimum exception), and maximum expression at least 0.8 TP10K. The extraction preserves reported cluster, condition, phase, scores and p/q values.
- An absent row in the published high-confidence table means only “not listed under the authors' criteria.” It is not evidence of absent expression or proven arrhythmicity.
- The article reports two experiments per condition and describes cell-level JTK replicates plus a random cell split for Fourier analysis. Treat the published calls as author-reported evidence and explicitly flag the cell-level pseudoreplication concern; do not claim this extraction independently establishes uncertainty at the biological-experiment level.
- A positive result here can motivate an information-gain pilot (for example, adult-restricted RNAi plus whole-cell current-clamp readouts), but it does not justify a formal causal experiment by itself. Check adult expression, reagent specificity, stock identity, controls, and electrophysiology QC through the dedicated gates.

## Verified example from the bundled GSE157504 audit

The join matched all 2,615 annotated IDs exactly once; 5,445 additional raw columns remained unannotated by this 17-cluster annotation. `Shab` raw detection in s-LNv was 160/181 LD cells and 97/142 DD cells; these are cell-detection fractions, not animal-level n or differential-expression tests. The published high-confidence table reported `Shab` cycling in s-LNv in both LD and DD. Together, these are a prioritization clue, not evidence that Shab protein or current drives a membrane-potential rhythm.

## Primary sources

- Ma, D. et al. A transcriptomic taxonomy of Drosophila circadian neurons around the clock. *eLife* **10**, e63056 (2021). [https://doi.org/10.7554/eLife.63056](https://doi.org/10.7554/eLife.63056).
- GEO Series GSE157504. [NCBI GEO record](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504).
- Official eLife supplementary workbook: [elife-63056-supp1-v2.xlsx](https://cdn.elifesciences.org/articles/63056/elife-63056-supp1-v2.xlsx).
- Authors' analysis repository: [rosbashlab/scRNA_seq_clock_neurons](https://github.com/rosbashlab/scRNA_seq_clock_neurons).
