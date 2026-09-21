# Iteration record — GSE157504 candidate context overlay

## Change

Added `scripts/build_candidate_evidence_context.py` and `references/candidate-context-overlay.md`. The sidecar joins the verified GSE157504 raw UMI detection and author-reported HC rhythm calls to the current literature candidate table at the `candidate × s-LNv/l-LNv/LNd/DN` level. It records score and ephys-gate parity against all four existing target-score files; it cannot use transcript data to change them.

The first real-data run exposed an upstream set mismatch: literature-scored candidates contain `na`, while the GSE candidate audit contains `eag` instead. The overlay now keeps the candidate universes separate: `na` receives explicit not-evaluable detection/rhythm statuses; `eag` is disclosed as GSE-only and is not silently inserted into the literature list. `para` remains not evaluable because its exact feature symbol is absent. `LN_ITP` rhythm calls stay ambiguous, DN calls preserve their named cluster/subcluster, zero UMI is dropout-sensitive, and author HC-list omission is not called arrhythmic.

A follow-up boundary review against the source data dictionary found that a target group can legitimately have zero annotated cells, in which case the upstream extractor leaves `detection_fraction` and `mean_raw_counts_per_cell` blank because they are undefined. The overlay now preserves those fields as `NA`, not zero, and rejects any nonzero counts in a zero-cell row. An output-path collision guard also prevents a custom output argument from overwriting candidate/input or executable helper files.

Static rationale wording for `Shab` and `cac` is flagged for human reconciliation where the transcript context may conflict with a static “missing target/circadian evidence” statement. The overlay does not automatically edit the rationale or promote transcript data to electrophysiology.

## Verification

- Full suite after follow-up fixes: 271 tests passed.
- Focused context tests: 5 passed (synthetic, real-data integration, zero-cell boundary, and path-collision safety); the two replay-allowlist tests also pass in the full suite.
- Follow-up synthetic boundary tests: zero annotated cells preserve undefined fraction/mean; output collisions fail before writing and input bytes are unchanged.
- Real output: 60 rows; 15 literature candidates × four target groups.
- Shab: s-LNv LD 160/181 detected (ZT), DD 97/142 (CT); matching author HC calls are retained with their original cluster/statistics.
- Candidate score, coverage, readout, directness score/gate, and shortlist gate match all four existing target-score CSVs.
- New public-data manifest: 19 hash-checked files, one run, zero issues.
- Isolated replay: one run, two output hashes verified, zero issues.

## Interpretation boundary

This is a reproducible data-integration check, not a new biological experiment or a reanalysis of the rhythm model. Cell counts are nested and descriptive; the report establishes neither protein abundance nor native current, membrane potential, causality, or behavior.
