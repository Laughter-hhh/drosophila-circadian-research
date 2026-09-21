# Iteration report: public-data manifest workflow order

Date: 2026-09-22

## Failure observed

The manifest validator and schema already supported a safe `planning` preflight, but the main skill router said to replay an executed analysis before running GEO parsing/extraction. The public behavior metadata guide likewise placed analysis before creation of the manifest. This made the advertised workflow impossible to follow literally: a planning manifest has no outputs to replay, while actual outputs and their hashes do not exist until after execution.

The underlying stages are supported: `planning` validates inputs, script identity, safe argv, and new planned output paths; `executed` validates real output records and can be replayed; after those checks pass, `verified` requires all run records to carry verified status.

## Changes

- Reordered the main skill's research gate and GEO/behavior routing to express `planning preflight → execute declared commands → executed validation and isolated replay → verified validation and replay`.
- Kept completed parent datasets distinct from new planned downstream work: an existing executed/verified parent may be validated and replayed before it is consumed; new outputs are not replayed before they exist.
- Updated the public behavior metadata workflow to create the planning record before running the metadata audit and to preserve the distinction between metadata QC and behavioral evidence.
- Added a CLI-level regression test that writes a real temporary planning manifest, runs `validate_public_dataset_manifest.py` through its command entry point, checks the generated `planning_public_dataset_manifest` report, and confirms the planned output remains absent.

## Validation

- Manifest/schema tests: **12 passed**.
- Isolated replay tests: **7 passed**.
- Full repository suite: **334 passed**.
- `git diff --check`: passed.
- Global skill deployment: copied current `SKILL.md`, `scripts`, `references`, `assets`, and `agents` into `C:\Users\laugh\.agents\skills\drosophila-circadian-research` without deleting installation-only files. SHA-256 comparison found **107/107 runtime files identical**, no missing files, no mismatches; the installed manifest-validator CLI accepted the current GSE77451 verified manifest. An installation-only historical validation artifact remained present.
- The optional `skill-creator` `quick_validate.py` remains unavailable in the bundled Python because PyYAML is not installed; no package was installed. The changed frontmatter was not modified, and the repository tests plus runtime CLI smoke test passed.

## Scope limits

Planning preflight validates declared file/script identity and command safety; it does not run commands, certify scientific design, or check that a future analysis is statistically appropriate. Replay establishes deterministic local reproduction of declared outputs only, not biological validity or causal evidence.
