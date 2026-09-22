# Iteration 2026-09-23: promote the whole-cell ephys trace pipeline to verified

## Scope

The checked-in synthetic ephys manifest covers a Drosophila s-LNv whole-cell trace workflow: experiment metadata, raw-QC/provenance, normalized trace derivation, pre-analysis bundle validation, and exploratory cosinor. Before this iteration the validator and isolated replay already passed, but the manifest did not explicitly declare its stage.

## Verification

Added `manifest_stage: "verified"` to `validation/synthetic-ephys-trace-replay-manifest.json`, then reran the current ephys-specific validator and isolated replay:

```powershell
python scripts/validate_ephys_trace_replay_manifest.py validation/synthetic-ephys-trace-replay-manifest.json --root . --output validation/synthetic-ephys-trace-replay-manifest-validation-verified-20260923.json
python scripts/replay_ephys_trace_manifest.py validation/synthetic-ephys-trace-replay-manifest.json --root . --timeout-seconds 120 --output validation/synthetic-ephys-trace-replay-isolated-replay-verified-20260923.json
```

Results:

- `verified_ephys_trace_replay_manifest`, zero issues;
- `verified_ephys_trace_replay`, 5 runs and 6 output hashes verified, zero issues;
- all raw binary files, normalized traces, metadata, QC, derived measurements, bundle report and exploratory cosinor were linked by relative paths and SHA-256.

## Reproducibility hashes

- Manifest: `466e78e75f456bfe654d03a483f43300728a5e86c1bff1fba22532448b898e58`
- Validator: `2a9efc34b8fe7a36013c67a45029a3e6d1f6c9fca8b478c4dfe4e3426f5e5853`
- Replay: `ea4675c2215253ee77ffe9443a5a67be9c40f50b376bfd398a773edfb8f0897e`

`tests/test_ephys_trace_replay.py` now asserts that the checked-in manifest explicitly remains `verified` before replay.

## Scientific boundary

This proves deterministic QC, trace derivation and exploratory analysis from the registered synthetic inputs. It does not prove cell identity, channel selectivity, membrane-potential rhythm, biological-unit statistical adequacy or causality. The ephys cosinor remains exploratory and formal inference still requires biological-unit-aware mixed-effects analysis and independent experiments.
