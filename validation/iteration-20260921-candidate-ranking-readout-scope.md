# Iteration record — source/readout-scoped channel ranking and tie stability

Date: 2026-09-21
Status: verified for current-output semantics, target/readout-scoped scoring, synthetic ranking invariants, and deterministic GSE157504 replay. This does not re-audit every cited paper or establish native channel causality.

## Trigger and reproduced weakness

An independent forward-use test identified two interpretation hazards: the output called top_candidate_stable=false when the same two candidates tied in every weight scenario, and a user following the SKILL.md candidate-scoring route could omit the source log/readout flags and mistake a candidate-row summary for a source-scoped native-current ranking.

The current public table and source log were re-run before editing. With the canonical current candidate row (Irk1 is indirect, target cells unverified) the scorer already blocks Irk1 as native s-/l-LNv current; with the checked source log and membrane_potential_or_current readout, Irk1 has no matching direct/near-direct target-cell record. Its checked s-LNv ClopHensor record is a separate intracellular_ion_concentration readout, while the patch-clamp assay is in cultured S2-R+ cells. This supersedes the older target-ranking iteration's conditional Irk1 wording for native current.

The all-NA GSE157504 transcript handoff was also re-run: all three weight scenarios report insufficient_scored_evidence, empty rankings and Top sets, and null stability. No alphabetical or input-order winner is emitted.

## Changes made

- Added top_candidate_set_stable to sensitivity output. It is true only when every weight scenario has the same non-empty Top/tie set. Existing top_candidate_stable remains the stricter “same unique winner in every scenario” field.
- Added tests distinguishing a stable Shaw/Shal tie from a changing winner set and from an all-NA/no-Top case.
- Clarified the SKILL.md workflow and candidate-ranking/scoring references: real candidate rankings must pass the validated source log, an explicit --readout-match, and one --target-cell per requested subtype. Candidate-row-only scoring is exploratory and cannot be described as source-scoped directness.
- Generated new readout-scoped target outputs under validation/public-data/candidate-native-current-*; refreshed the GSE157504 bridge sensitivity output and updated both affected manifests.

## Current public-evidence outcome

candidate-evidence-real.csv and its 19-record checked source log validate with 15 candidate rows and zero issues. Separate source-log scores for membrane_potential_or_current produce:

| Target | Direct-gate/Top interpretation | Conditional directness |
|---|---|---|
| s-LNv | Shaw and Shal tie in all three weight scenarios; top_candidate_set_stable=true, top_candidate_stable=false | none |
| l-LNv | na is the unique Top in all three scenarios; Shaw and Shal also pass the direct gate | none |
| LNd | no target-scoped Top | none |
| DN | no target-scoped Top | none |

These are outputs of the curated evidence ratings and matching rules, not independently re-evaluated biological conclusions. In particular, needs_direct_evidence for Irk1 means the current evidence log has no matching native-current record for s-LNv or l-LNv; it does not show that Irk1 current is absent.

## Verification

- Full suite in the data-bearing repository clone: python -m unittest discover -s tests — 271 passed.
- Focused tests: target-cell/tie semantics 10 passed; candidate scoring 6 passed; source-log gate 5 passed.
- Candidate-table validator: verified_candidate_evidence_table; 15 candidates, 19 search-log records, zero issues.
- GSE157504 transcript-only score diagnostic: insufficient_scored_evidence, empty ranks/Top, null stability.
- GSE157504 evidence bridge manifest: verified_public_dataset_manifest, 11 files/4 runs/zero issues; isolated replay verified_public_dataset_replay, 4 runs/7 output hash checks/zero issues.
- GSE157504 candidate-context manifest: verified_public_dataset_manifest, 19 files/1 run/zero issues; isolated replay verified_public_dataset_replay, 1 run/2 output hash checks/zero issues.
- Skill Creator quick_validate.py attempted but could not import yaml (ModuleNotFoundError: No module named 'yaml'). No environment dependency was installed; frontmatter was manually inspected and not changed.

## Environment note

A first full-suite run in a newly created Git worktree produced hash failures because core.autocrlf=true converted tracked text files and because ignored/local raw-data inputs were not carried into the new worktree. The candidate source file hash in that worktree differed from the provenance hash. Re-running in the original data-bearing clone, whose input bytes match the manifests, passed all 271 tests. The failed worktree run is not counted as a code validation pass.

## Reproduction

From the repository root, use the following pattern for each target subtype:

    python scripts/validate_candidate_evidence.py validation/public-data/candidate-evidence-real.csv --search-log validation/public-data/candidate-evidence-search-log.csv --output validation/public-data/candidate-evidence-real-readout-scoped-validation.json
    python scripts/score_candidates.py validation/public-data/candidate-evidence-real.csv --search-log validation/public-data/candidate-evidence-search-log.csv --readout-match membrane_potential_or_current --target-cell s-LNv --output validation/public-data/candidate-native-current-score-slnv.csv --sensitivity-output validation/public-data/candidate-native-current-sensitivity-slnv.json

Repeat the second command with l-LNv, LNd, or DN and the matching output suffix. The exact input, code, and output hashes are recorded in validation/candidate-native-current-readout-scope-task.json. For the GSE157504 transcript-only negative control, use its candidate-evidence bridge manifest and isolated replay.
