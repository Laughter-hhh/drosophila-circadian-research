# Iteration report: GSE22308 forward test and design confounding audit

Date: 2026-09-22

## Forward-test request and source

An independent evaluator received only an isolated copy of the GSE22308 series matrix, sample metadata, candidate list, the current skill, and the current workflow scripts. The evaluator verified the authoritative NCBI GEO record for [GSE22308](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE22308), which identifies adult *Drosophila melanogaster* purified clock-neuron array profiling under LD and reports four ZT points for large PDF neurons versus two points for the other listed groups.

This was an isolated-input forward test, not a fully blind test: while locating allowed scripts, the evaluator saw filenames of prior validation artifacts but did not open or use their contents. The exact limitation is retained in `validation/gse22308-forwardtest-20260922-summary.json`.

## Observed analysis behavior

- The series matrix parsed with **24/24** sample-column alignment, **18,952** feature rows, no duplicate feature IDs, and no nonnumeric values.
- All **15** candidate genes mapped to numeric GPL1322 probe data.
- The descriptive rhythm output kept **15** groups with enough phase coverage for the fixed 24-hour waveform and **45** groups as `insufficient_or_invalid_time_series`.
- Only adult `yw` large-PDF samples had four ZT points (ZT0/6/12/18; 3/2/3/2 samples). `yw` ELAV, `yw` small-PDF, and `per01` large-PDF groups had only ZT0/12 and were not fitted as 24-hour rhythms.
- No inferential cosinor was run. The evaluator described `Ca-alpha1T`, `Irk1`, and `sei` as exploratory leads by amplitude/fit quality, not as statistically established rhythms or functional channel candidates.

## New failure found and fixes

To prevent a common scientific overreach—interpreting a background comparison as an independent sex effect—I added `scripts/audit_design_confounding.py`. It reports factor levels, cross-tabs, blank values, and one-to-one observed mappings as `perfectly_confounded` warnings. The real GSE22308 sample table flags `sex × genotype_background` as perfectly confounded: `yw` is annotated `male_and_female`, while `per01` is annotated `male`. The audit therefore does not permit an independent sex effect claim.

The new script exposed two reproducibility/security integration issues during its own end-to-end test:

1. Isolated replay correctly rejected the new script because it was not in the explicit reviewed-script allowlist. I added the allowlist entry and a safe-argv regression test.
2. Replay then detected an output hash mismatch because the script embedded an absolute input path in JSON. I changed the report to use a repository-relative path when possible and a basename outside the working root, then regenerated the output.

After both fixes, the GSE22308 manifest reached `verified` with **10 files, 4 runs, and zero validator issues**; isolated replay passed **6/6 output hashes with zero issues**. The compact commands, hashes, metrics, and limitations are recorded in `validation/gse22308-forwardtest-20260922-summary.json`. The independent temporary manifest and full reports were retained under `E:\skill\.tmp-independent-gse22308-20260922` during validation.

The repository regression suite after these changes was **342 tests, all passing**; the focused design-confounding, replay-allowlist, and routing tests also passed.

## Interpretation boundary

This verifies a reproducible public-data parsing, candidate mapping, exploratory waveform, and design-confounding workflow. It does not show that any candidate controls ion-channel current, membrane potential, clock-neuron activity, or behavior. The dataset is LD, pooled, and missing age, temperature, batch, and fly-level pooling details; follow-up requires an independent, cell-resolved, sex-stratified time course and then native current/membrane-potential measurements.
