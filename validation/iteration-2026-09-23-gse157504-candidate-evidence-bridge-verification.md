# Iteration 2026-09-23: verify the GSE157504 candidate-evidence bridge

## Scope

This workflow joins GSE157504 clock-neuron raw-UMI detection and author-reported rhythm context to the 15-channel candidate list, validates the evidence search log and evidence table, and emits a score-readiness diagnostic. It is a bridge to candidate ranking, not a ranking claim itself.

## Verification

The current manifest already had passing local validation and replay, but all four runs were recorded as `executed` and the manifest had no explicit stage. After confirming a fresh validator/replay baseline, the manifest was upgraded to `manifest_stage: "verified"` and all four run records were promoted to `verified`. The final gates returned:

- `verified_public_dataset_manifest`, 11 files, 4 runs, zero issues;
- `verified_public_dataset_replay`, 4 runs, 7 output hashes verified, zero issues.

The bridge report remains conservative: 15 candidates, 30 search-log records, 14 candidates with direct target-group raw-UMI detection, 9 with author high-confidence rhythm rows, and all 15 candidates with every ranking dimension unrated. The score diagnostic contains only `shortlist_gate=needs_evidence`; no Top candidate is emitted from transcript-only evidence.

## Reproducibility hashes

- Manifest: `0864894730df8796cf6f1f79d73916c6d72a32302eb99dfe0141f3b66064b352`
- Validator: `e3f0f9884a2fc530c79bfb9760e97a490137e500be015c7bac32cbaa23df578e`
- Replay: `ff2b50d2beecbfb32fbdf26a6055404e2b8fe35c051300416fb58665d6252e5c`

`tests/test_gse157504_candidate_evidence_bridge.py` now checks the checked-in manifest/replay and the score-neutral `needs_evidence` invariant.

## Scientific boundary

Raw UMI detection and author rhythm-list membership remain transcript evidence. They do not establish channel protein, native membrane current, membrane-potential rhythm, behavior, animal-level inference or causality; the bridge intentionally leaves all ranking dimensions unrated until separately sourced target-specific evidence is available.
