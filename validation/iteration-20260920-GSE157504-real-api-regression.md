# Iteration record: GSE157504 public-data API regression

Date: 2026-09-20

## Scope and observed gap

The GSE157504 route already exercised both scripts through their command-line entry points and tested the raw-count `run()` API on a synthetic tar fixture. That left one specific regression gap: an import-only failure in the reusable API could pass its small synthetic test while the real public matrices had only been checked through the CLI. This iteration adds an independently executable real-data regression test for that API without changing the biological interpretation of the dataset.

## Change

- Added `tests/test_gse157504_detection_api_public.py`.
- The test reads the three expected input hashes from the checked provenance manifest and calls `scripts.audit_gse157504_candidate_detection.run()` directly, without going through `main()` or writing derived output files.
- It checks complete barcode matching, raw-matrix coverage, completeness of the time grid, exact-symbol feature coverage, the `Shab` s-LNv LD/DD cell counts, and the LD=`ZT` / DD=`CT` distinction.
- The test skips only if the bundled public dataset inputs or manifest are absent. If they are present but their hashes differ, the test fails through the API's expected-hash checks.

## Verification

1. Focused GSE157504 tests: 13 tests passed.
2. New real-data API integration test: 1 test passed in 7.394 s.
3. Full suite: `python scripts/run_tests.py` — 236 tests passed in 17.686 s.
4. Task contract: `OK: research task contract is valid`.
5. Dataset manifest: `verified_public_dataset_manifest`, 11 file hashes checked, 2 analysis runs linked, no issues or warnings.
6. Isolated replay: `verified_public_dataset_replay`, 2 runs returned 0, all 7 declared output hashes matched.
7. Direct read-only API execution over the real inputs, with manifest hashes supplied: 2,615/2,615 annotated barcodes matched exactly once across 84 matrices; six expected phases were present for each replicate; 14 of 15 candidate symbols were represented exactly. `Shab` detection in s-LNv was 160/181 LD cells and 97/142 DD cells. The missing exact feature `para` remains unevaluable in this matrix, not biologically absent.
8. `git diff --check` found no whitespace errors. The skill frontmatter was manually checked: opening/closing delimiters, matching directory name, lowercase-hyphen name syntax, allowed keys, description length (197 characters), and no unfinished TODO scaffold markers all passed.

The skill-creator `quick_validate.py` could not run because the bundled Python environment does not include `PyYAML` (`ModuleNotFoundError: No module named 'yaml'`). No dependency was installed. The manual frontmatter check is narrower and is not represented as an equivalent YAML parser validation.

## Interpretation boundary

The raw-count detection results describe nonzero UMI detection in annotated cells; cells are not independent fly-level replicates, and zeros can reflect dropout. The supplement extraction transcribes author-reported high-confidence rhythm rows rather than refitting the rhythm model. Neither readout establishes channel protein abundance, current, membrane-potential rhythm, or causal behavioral control. Keep the mixed `LN_ITP` group separate from pure s-LNv/LNd claims. These boundaries follow the task contract and `references/published-sc-clock-rhythm-audit.md`.

## Reproduction commands

From the skill repository root, using Python 3.12 with `openpyxl` available for workbook extraction:

```powershell
python -m unittest tests.test_gse157504_candidate_detection tests.test_gse157504_detection_api tests.test_gse157504_detection_api_public tests.test_gse157504_public_manifest tests.test_published_sc_clock_channel_rhythms -v
python scripts/validate_research_task.py validation/GSE157504-candidate-channel-rhythm-task.json
python scripts/validate_public_dataset_manifest.py validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json --root . --output validation/public-data/GSE157504-candidate-channel-rhythm-manifest-validation.json
python scripts/replay_public_dataset_manifest.py validation/public-data/GSE157504-candidate-channel-rhythm-provenance-manifest.json --root . --timeout-seconds 120 --output validation/public-data/GSE157504-candidate-channel-rhythm-replay.json
python scripts/run_tests.py
```

## Sources

- Ma, D. et al. A transcriptomic taxonomy of Drosophila circadian neurons around the clock. *eLife* **10**, e63056 (2021). https://doi.org/10.7554/eLife.63056.
- NCBI GEO Series GSE157504: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504.
- Author analysis repository: https://github.com/rosbashlab/scRNA_seq_clock_neurons.
- Official eLife supplementary workbook: https://cdn.elifesciences.org/articles/63056/elife-63056-supp1-v2.xlsx.
