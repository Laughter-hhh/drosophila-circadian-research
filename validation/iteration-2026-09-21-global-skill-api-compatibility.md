# Iteration 2026-09-21: cross-project install and validator API compatibility

## Task and status

This iteration tested whether the separately installed user-level skill can resolve its routed resources and whether its GEO evidence workflow remains runnable after safe synchronization. Tooling compatibility and public-data replay are verified; the full global-install regression suite remains non-green because its bundled tests and fixtures are stale relative to the current repository schema.

## Drift found and bounded synchronization

The active skill is loaded from `C:/Users/laugh/.agents/skills/drosophila-circadian-research`, not from this Git repository. A hash audit of the tracked `SKILL.md`, `references/`, `scripts/`, and `assets/` runtime files found 76 identical files, 12 files matching known repository history, 14 missing support files, and 4 locally divergent files. The 12 known older files were refreshed and the 14 absent references/scripts were added. The four divergent files were preserved: `SKILL.md`, `references/candidate-ranking.md`, `scripts/replay_public_dataset_manifest.py`, and `scripts/score_candidates.py`.

After synchronization, 68 paths referenced by the installed `SKILL.md` resolve; zero are missing. The installed GSE22308 manifest now verifies 11 files and 4 runs, and isolated replay verifies all 6 declared output hashes.

## Failure and code change

The installed copy had a locally divergent `score_candidates.py` that did not export `UNVERIFIED_CELL` or `parse_cell_tokens`, while the newer evidence-log and candidate-table validators imported those internals from the scorer. This made the validators depend on a specific scorer version even though they own the evidence schema.

The repository validators now define the `unverified` token and canonical cell-group parser alongside the evidence-log schema. Candidate-table validation obtains the evidence enums and parser from that schema validator; scoring dimensions and ratings remain supplied by the scorer. The parser preserves canonical ordering, accepts documented case-insensitive aliases, rejects unknown cell labels, and rejects mixing `unverified` with named cells. Regression cases cover aliases, invalid labels, and mixed unknown/named tokens.

## Verification

- Focused schema/evidence tests: 8 search-log tests, 6 candidate-table tests, and 10 source-log-gate tests passed.
- Previously failing GSE157504/Abruzzi integration test: 6 tests passed after the parent manifests were refreshed.
- Full repository suite: **316 tests passed**.
- Four affected manifests/replays are verified with zero issues: evidence bridge (4 runs/7 output checks), candidate scoring (6/11), GSE context overlay (1/2), and combined transcript context (1/2). Total: 12 isolated runs and 22 matching output hashes.
- `git diff --check`: passed.
- Global installed GSE22308 manifest/replay: `verified_public_dataset_manifest` (11 files, 4 runs) and `verified_public_dataset_replay` (4 runs, 6 output hashes).
- Global installed reference scan: 68 references, zero missing.
- Global installed aggregate suite: 222 tests; 15 failed because legacy test fixtures expect the older candidate/search-log columns and module behavior. The active public-data manifest tests pass after refreshing the GSE fixture. The repository suite is the current authoritative regression suite; these 15 failures are retained as a deployment drift warning, not reported as a successful global test run.

## Interpretation limits and next step

No new biological observation or candidate ranking was produced in this iteration. GSE22308 replay establishes the declared scripts and current outputs reproduce; it does not establish normalization suitability, endogenous rhythmicity, target-cell identity, channel current, membrane-potential effects, or causality.

The next cross-project hardening step is to review and reconcile the four preserved local divergences and either refresh or remove the stale installed test fixtures without overwriting user-specific work. Until then, the repo version is fully tested, the global skill routes all referenced resources, and the global GSE workflow replays, but the global aggregate test suite must remain labeled partial.
