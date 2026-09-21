# Iteration report: GSE77451 ESAT adapter and staged provenance

Status: verified for file integrity and isolated replay; biological interpretation remains exploratory.

## What changed

- Added `scripts/prepare_esat_candidate_expression.py` to join explicitly audited matrix sample columns to GEO metadata, preserve candidate transcript rows, and emit separate `sum`, `median`, and `max` gene-by-sample sensitivity tables. No normalization or expression unit is inferred.
- Added an explicit source-checked matrix alias `Ir` → `Irk1` in `validation/public-data/GSE77451-symbol-aliases.csv`, citing [FlyBase FBgn0265042](https://flybase.org/reports/FBgn0265042). Alias use is counted separately from exact/case-folded symbol matches.
- Updated `scripts/analyze_expression_rhythm.py` to keep declared `timecourse_id` groups separate. When an older input lacks this field, its output schema and values remain unchanged.
- Added `planning` manifest preflight: safe, not-yet-existing outputs and structured commands can be checked before execution; planning manifests cannot be replayed. Documented the planning → executed → verified transition.
- Added the adapter to the isolated replay allowlist and synthetic tests for sample-order independence, duplicate transcript IDs, alias handling, missing candidate rows, and aggregation behavior.

## Real-data run

Input: GSE77451 processed ESAT matrices for broad `LNv`, `LNd`, and `DN1` groups, plus the existing audited GEO sample map, a 15-gene candidate list, and the alias record.

- Parsed 28,067 LNv, 28,066 LNd, and 28,066 DN1 matrix rows; each matrix contained 12 mapped samples.
- Matched 457 candidate transcript rows across the three matrices and preserved 5,484 transcript × sample values.
- Emitted 540 candidate × sample rows for each aggregation method (15 candidates × 12 samples × 3 broad groups).
- Ran descriptive fits separately across six mapped course labels. Each aggregation produced 90 gene/group/course records; 88 were computable and two `Ork1` LNv course records had no numeric expression. This is an execution/coverage result, not evidence that 88 groups are statistically rhythmic.
- `Irk1` matched through the documented `Ir` alias (four transcript rows in each broad group). No alias was silently inferred.

The grouped data do not resolve s-LNv versus l-LNv or DN subtypes. GSM/library records and transcript rows are not individual-fly replicates. Processed value scale/normalization, individual fly identity, sex, age, genotype, and temperature are not established by this adapter. The descriptive cosinor output has no inferential p/q values and does not establish membrane-current, membrane-potential, or causal channel evidence.

## Verification

- Synthetic adapter tests: 3 passed.
- Rhythm tests: 9 passed, including two same-phase-grid courses that remain two independent fit groups.
- Manifest tests: 11 passed, including safe planning outputs and rejection of false execution claims.
- Isolated replay tests: 7 passed after the adapter was added to the allowlist.
- Full repository suite: 328 tests passed.
- GSE77451 manifest: 15 file hashes and 5 runs validated; isolated replay passed all 5 runs and matched all 9 declared output hashes. The manifest was then promoted to `verified` and validated/replayed again.
- Backward compatibility: regenerated GSE22308 descriptive outputs remained byte-identical to their recorded hashes; its canonical manifest was refreshed with the current rhythm-script hash and the existing isolated replay passed.

Primary artifacts:

- `validation/public-data/GSE77451-esat-candidate-expression-provenance-manifest.json`
- `validation/public-data/GSE77451-esat-candidate-expression-manifest-validation.json`
- `validation/public-data/GSE77451-esat-candidate-expression-replay.json`
- `validation/public-data/GSE77451-esat-candidate-expression-20260922-audit.json`
- `validation/public-data/GSE77451-esat-candidate-expression-20260922-transcripts.csv`
- `validation/public-data/GSE77451-esat-candidate-rhythm-sum-20260922.json` (and `median` / `max` counterparts)

The manifest and replay establish provenance linkage and deterministic output reproduction only. They do not validate normalization suitability, subtype identity, biological representativeness, statistical inference, or a biological mechanism.
