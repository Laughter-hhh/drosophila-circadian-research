# Iteration report: published-cycle candidate input column

Date: 2026-09-22

## Friction observed

An external forward-test workflow used a candidate CSV whose symbol header was `gene_symbol`, while `audit_published_cycle_candidates.py` accepted only `candidate`. The tester had to create a header-only adapter to run the published-cycle audit. The forward test is informative but was not fully blind: the evaluator had seen an earlier iteration report before independently rerunning the local data workflow. No new biological ranking is claimed from this interface finding.

## Change

- Added `--candidate-column` to the audit CLI, defaulting to `candidate` so existing commands retain their behavior.
- Kept exact, case-sensitive symbol matching and all existing duplicate/blank-symbol checks; selecting a column does not infer aliases or rewrite the source CSV.
- Documented `--candidate-column gene_symbol` in the published-cycle workflow guide.
- Added a synthetic regression test using the original `gene_symbol` header and verified that the source CSV remains unchanged.

## Validation

- Focused published-cycle audit tests: **3 passed**.
- Full repository suite: **335 passed**.
- Re-ran the real GSE77451/Abruzzi S3 audit using the unchanged default column. Output CSV and JSON SHA-256 values remained identical to the prior manifest values.
- Public-data manifest validation: `verified_public_dataset_manifest`, 4 files, 1 run, no issues or warnings.
- Isolated replay: `verified_public_dataset_replay`, 1 run and 2 output hashes verified.
- `git diff --check`: passed.

## Scope limits

The option resolves only the input header mismatch. Candidate symbols still require an explicit reviewed alias map when nomenclature differs; the audit remains a transcript-level match to author-reported supplement calls and cannot establish channel protein abundance, current, membrane-potential effects, or causal behavior effects.
