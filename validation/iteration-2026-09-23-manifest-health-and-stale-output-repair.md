# Iteration 2026-09-23: repository-wide manifest health and stale-output repair

## Discovery

A read-only validator sweep over the current `validation/public-data/*manifest.json` files found three invalid manifests:

1. `GSE22308-blind-forward-context-stratified-manifest.json`: current `analyze_expression_rhythm.py` and `analyze_cosinor_inference.py` hashes were not recorded.
2. `GSE22308-blind-forward-sex-aware-manifest.json`: the same two script hashes were stale.
3. `GSE77451-candidate-transcript-key-manifest.json`: the current `audit_esat_candidate_sample_keys.py` hash was not recorded.

The validator correctly failed closed. After updating only the script hashes, isolated replay exposed four stale derived-output hashes: the context-stratified cosinor result, the sex-aware rhythm and cosinor results, and the ESAT transcript-key audit. Every declared command returned exit code 0; the failure was provenance drift, not a silent biological result.

## Repair and gates

- Re-ran the affected commands from each manifest using the current scripts and fixed seeds/parameters.
- Updated the three manifests with the observed output hashes and explicit `manifest_stage: "verified"`.
- Ran each manifest validator and isolated replay again.

Final gate results:

| Manifest | Validator | Replay | Runs | Output checks | Issues |
|---|---|---|---:|---:|---:|
| GSE22308 context-stratified | `verified_public_dataset_manifest` | `verified_public_dataset_replay` | 4 | 6 | 0 |
| GSE22308 sex-aware | `verified_public_dataset_manifest` | `verified_public_dataset_replay` | 4 | 6 | 0 |
| GSE77451 transcript-key | `verified_public_dataset_manifest` | `verified_public_dataset_replay` | 1 | 1 | 0 |

## Reproducibility hashes

### GSE22308 context-stratified

- Manifest: `da84687de1852bd1f9050081aee288f505a1c3e81385ce393a8230f21789d5ba`
- Validator: `0770fe5df557ef59b4ed8e01aa19c680a1c49f706bb059a94e488060f70d3d86`
- Replay: `6fa0c70eaff791e192d08fcae2c312016cb4a972c6d0e73f53c6bd1a5569e2ee`

### GSE22308 sex-aware

- Manifest: `d08e6d6d29dc4f7c980a9d3548138da0bb2d91f82c2c2bdfdeeea0e58cbea116`
- Validator: `19bf35b17f8c0300b9dcd1853816dbbad8840cc9697254a0ac3263d85cf97b4b`
- Replay: `e23a100c60ecd646f5284f750bac192c265ac68c5f0abf7991a2a3eceaf27930`

### GSE77451 transcript-key audit

- Manifest: `cdb09701a3af92afe86e78bceadd6ee9daac6086b6ae237b98da071122b36c85`
- Validator: `ab2b9f5377e7bed0230dbce57936c358ccccc3bb5c7837392b0800a7aafc5600`
- Replay: `d328c55c8fe972643418a362ec114c2bc1bfee9abd96f63be11ff548b40418f7`

## Scientific boundary

These gates establish current-file integrity and deterministic replay only. GSE22308 remains exploratory pooled-sample expression/cosinor evidence with its metadata confounding limitations; GSE77451 remains transcript sample-key provenance. None establishes ion-channel function, native clock-neuron membrane current, membrane-potential rhythm, behavior, or causality.
