# Iteration 2026-09-22: repair stale combined transcript-context provenance

## Independent forward-test failure

The checked-in `validation/public-data/combined-transcript-candidate-context-manifest.json` was replayed from the current repository before editing. Both gates failed:

- validator: `invalid_public_dataset_manifest` (exit 1)
- isolated replay: `blocked_public_dataset_replay` (exit 1; no command executed)

The manifest contained five stale hashes: the current `replay_public_dataset_manifest.py`, the current `validate_public_dataset_manifest.py`, and three Abruzzi parent artifacts (`candidate-cycle-manifest.json`, its validation report, and its replay report). The GSE and Abruzzi parent workflows themselves passed fresh validator/replay checks. This was a provenance-refresh failure, not evidence that the underlying candidate-context join changed biologically.

## Repair

1. Freshly replayed all three parents (Abruzzi cycle audit, GSE157504 rhythm, and GSE157504 candidate overlay): all returned verified statuses with zero issues.
2. Re-ran the documented `build_published_cycle_candidate_context.py` command so the combined manifest recorded the current script and parent hashes.
3. Preserved the 60-row score-neutral join and then promoted the single run and manifest to `verified` only after the new validator and isolated replay passed.
4. Added a regression test that checks the checked-in combined manifest itself, rather than only a temporary manifest generated during a unit test.

## Final verified evidence

- Validator: exit 0, `verified_public_dataset_manifest`, `manifest_stage=verified`, 33 files, one run, zero issues.
- Isolated replay: exit 0, `verified_public_dataset_replay`, one run, two output hashes verified, zero issues.
- Combined context: 60 input rows → 60 output rows; 9 listed target rows (2 HC, 7 LC) and 51 `not_listed` rows.
- Invariants: all input context values copied verbatim; scores and electrophysiology gates not recomputed.

SHA-256:

- Combined manifest: `bf0624937656652b8393b294be42f4a23580c35b487de0f01dc31c4de2331746`
- Combined report: `60209a719365c1be6ff632d56249397b2e785d5b82c26fc3adc1e2f413bb03dc`
- Verified validator report: `3b62dd0301283733910921d7e8aede588f6cc4df89acfa266d140aa79939709b`
- Verified replay report: `5efe9baa7242363a407ab21e02d131fb1e02600e032f82750b2767a58d6f171d`

## Scientific boundary

This repair verifies file lineage and deterministic execution only. The joined transcript context remains a score-neutral sidecar: pooled LNv rows do not resolve s-/l-LNv, the LNd source includes a fifth PDF-negative s-LNv, DN coverage is a DN1 subset, and transcript calls do not establish channel protein, membrane current, membrane-potential rhythm, behavior, or causality.
