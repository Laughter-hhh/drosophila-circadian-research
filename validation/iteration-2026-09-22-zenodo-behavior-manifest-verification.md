# Iteration 2026-09-22: public behavior metadata manifest reaches verified stage

## Why this iteration

The Zenodo behavior-data metadata audit had already executed successfully and an isolated replay had passed, but its manifest omitted an explicit `manifest_stage`. Under the three-stage public-data contract, that left the record in compatibility-mode `executed` status. This iteration promotes only that already-audited metadata workflow to `verified`; it does not turn metadata into behavioral or circadian evidence.

## Input and scope

- Accession: `10.5281/zenodo.18214640`
- Source: `https://zenodo.org/records/18214640`
- Input: `validation/public-data/zenodo-18214640-20lux-main-dataset.csv`
- Input SHA-256: `1879cb556e1f84a225520b5a4d4689244b7109bfe850261d24dd3137c7fb1008`
- Audited rows: 190; condition counts: A=50, B=50, C=50, D=40
- Audit status: `verified_public_behavior_metadata_audit`
- Scientific boundary: genotype/strain, sex, age, temperature, LD/DD timing, validated individual-fly identity, and raw recording checksums remain missing; behavior/circadian analysis readiness remains blocked.

## Commands and gates

1. Added `manifest_stage: "verified"` to `validation/public-data/zenodo-18214640-metadata-provenance-manifest.json` after the prior executed validator and replay had passed.
2. Ran the verified-stage validator:

   ```powershell
   python scripts/validate_public_dataset_manifest.py validation/public-data/zenodo-18214640-metadata-provenance-manifest.json --root . --output validation/public-data/zenodo-18214640-metadata-provenance-validation-verified-20260922.json
   ```

   Result: exit code 0, `status=verified_public_dataset_manifest`, `manifest_stage=verified`, `issues=[]`.

3. Ran isolated replay:

   ```powershell
   python scripts/replay_public_dataset_manifest.py validation/public-data/zenodo-18214640-metadata-provenance-manifest.json --root . --timeout-seconds 120 --output validation/public-data/zenodo-18214640-metadata-replay-verified-20260922.json
   ```

   Result: exit code 0, `status=verified_public_dataset_replay`, one output hash verified, `issues=[]`.

## Reproducibility hashes

- Manifest: `d5d28585df0e2189a6f37ffcfa546e3c1da73336dff6626c2de23b9cbb83f691`
- Validator report: `4a98ddf550bb31c2fa56123b63df34892a8f2832599052abff4447e34ff9eca3`
- Replay report: `b14d7db71a254d22e12769d03c0548ddb655ace7af429968b9ecfdb91741260`

## Regression coverage

`tests/test_behavior_public_manifest.py` now asserts both the validator result and the nested replay provenance report retain `manifest_stage=verified`.

## Interpretation

**Verified workflow claim:** the current local input, script, manifest and declared output are linked and reproduce in an isolated mirror.

**Not established:** behavioral period/amplitude, circadian phase, genotype effect, neural activity, ion-channel mechanism, or causality. The metadata-only audit remains blocked for those scientific analyses until the missing research metadata and raw recording provenance are obtained.
