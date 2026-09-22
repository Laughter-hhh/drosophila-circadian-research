# Iteration 2026-09-23: verify the GSE157504 parent rhythm-evidence manifest

## Scope

This parent workflow extracts author-reported clock-neuron channel-gene rhythm calls and audits raw UMI feature detection from GSE157504. It feeds the candidate-evidence bridge, but it is transcript-level provenance only.

## Verification

The fresh validator and isolated replay both passed before promotion. The manifest now declares `manifest_stage: "verified"`, and both run records are marked `verified`.

- `verified_public_dataset_manifest`, 11 files, 2 runs, zero issues;
- `verified_public_dataset_replay`, 2 runs, 7 output hashes verified, zero issues;
- the checked-in regression test verifies the stage, run count, output count, and every replay hash.

## Reproducibility hashes

- Manifest: `f5fa2be244eb9d32cf84b35e57ef098125042cb798e97daeebed570e24d01ff2`
- Validator: `7ada5eb9b85fb4abb7225269ddc6f018f9b3847c66a84172cf26a18302e33795`
- Replay: `bf36ca66bf7e79476eed997a3df54d205ded651631ecc6e58a140de0caf3e38e`

## Scientific boundary

Raw UMI detection is descriptive and subject to dropout; author rhythm-list membership is transcribed rather than refit. The manifest does not support claims about channel protein abundance, native current, membrane-potential rhythm, behavior, fly-level replication, or causality. Candidates absent from the raw feature table are not biologically absent, and ambiguous neuron labels remain unresolved pending targeted evidence.
