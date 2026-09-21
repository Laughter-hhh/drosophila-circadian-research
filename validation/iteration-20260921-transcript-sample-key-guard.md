# Iteration — block duplicate transcript/probe rows in expression rhythm inputs

Date: 2026-09-21
Status: verified for the synthetic duplicate-key invariant, GSE77451 structural audit, GSE22308 unchanged-output regression, manifest validation, and isolated replay. This is not evidence of candidate rhythmicity or channel function.

## Trigger

The expression rhythm helper accepted multiple rows with the same sample ID inside a gene/cell/background group. That lets multiple probes or transcript isoforms enter a gene-level cosinor as if they were repeated observations, changing the fit weights and inflating observation counts. It also accepted a repeated sample key if one duplicated feature row had an empty expression value, because empty rows were filtered before analysis.

The official GSE77451 processed LNv, LNd and DN1 matrices are transcript-level ESAT quantifications, with a separate transcript ID and gene Symbol field and 12 library columns in each file. The structural audit used exact symbol matching after case folding, without synonym expansion. The three target-group files showed:

| Source group | Sample columns | Candidate symbols found | Candidates with multiple transcript rows | Candidate × sample keys with repeated feature rows | Exact symbols not found |
| --- | ---: | ---: | ---: | ---: | --- |
| LNv | 12 | 13/15 | 13 | 156 | Irk1, Ork1 |
| LNd | 12 | 14/15 | 14 | 168 | Irk1 |
| DN1 | 12 | 14/15 | 14 | 168 | Irk1 |

Examples include para (57 transcript rows), Sh (14), cac (15) and slo (19) per source matrix. These counts describe feature structure only. Missing exact-symbol rows do not establish non-expression; no values were normalized, aggregated, compared by time or rhythm-tested.

## Changes

- The descriptive expression-rhythm helper now requires nonblank, unique sample IDs within each gene-symbol × cell-type × background group, checking all rows before dropping missing expression values. It fails with an instruction to aggregate probes/transcripts using an explicit rule or analyze transcripts separately. It does not guess a sum/mean/median.
- Added audit_esat_candidate_sample_keys.py for ESAT transcript-level GEO files. It records matrix/sample structure, candidate transcript multiplicity and repeated gene-sample keys, while explicitly avoiding expression or rhythm conclusions.
- Routed the audit from SKILL.md and GEO workflow documentation; added it to the constrained manifest replay allowlist.
- Kept GSE22308 as a no-duplicate public regression: after the guard, its rhythm JSON was byte-identical to the existing output (SHA-256 96e9bff734d3fadd7c269acf2270a17c7d78b31fb5c961f6fc51b1b8fe8836a5). Its provenance manifest now binds the current script hash and records the isolated rerun.

## Verification

- Synthetic: expression-rhythm tests, 5 passed; ESAT-key audit tests, 3 passed.
- Real public data: official NCBI GEO GSE77451 processed LNv/LNd/DN1 matrices downloaded and SHA-256 recorded in GSE77451-candidate-transcript-key-manifest.json. All matrices passed gzip/TSV shape checks.
- GSE22308 manifest: verified, 12 files / 5 runs / zero issues. Isolated replay: verified, 5 runs / 7 output hashes / zero issues.
- GSE77451 manifest: verified, 5 files / 1 run / zero issues. Isolated replay: verified, 1 run / 1 output hash / zero issues.
- Full unittest suite: 277 passed.

Two staged regressions exposed stale assumptions after the script changed: first the GSE22308 manifest still named the previous rhythm-script SHA-256; after updating the provenance, its test still expected 11 files / 4 runs instead of the new 12 / 5. Both were updated, then the full suite and replay passed.

## Interpretation boundary

GSE77451 reports mixed LNv pools (s-LNv and l-LNv), LNd pools that include the fifth PDF-negative s-LNv, and only a DN1 subset. The paper describes two independent six-timepoint LD collections and approximately 50–100 manually isolated neurons per sample; this audit does not map sample labels to timepoints or infer individual-fly replication. Therefore it is a data-ingestion/key audit, not channel-expression or channel-rhythm evidence.

## Sources

Abruzzi, K. C. et al. RNA-seq analysis of Drosophila clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides. *PLoS Genet.* **13**, e1006613 (2017). https://doi.org/10.1371/journal.pgen.1006613.

NCBI Gene Expression Omnibus. GSE77451, RNA-seq analysis of Drosophila clock and non-clock neurons. https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE77451.

NCBI Gene Expression Omnibus. GSM2052232, LNv sample KA_SEQ_37, ZT2; processed expression is reported by transcript ID. https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM2052232.
