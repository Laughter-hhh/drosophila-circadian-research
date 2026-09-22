# Iteration 2026-09-23: repair the GSE157504 downstream provenance chain

## Trigger

Promoting the GSE157504 parent rhythm manifest to `verified` changed its SHA-256. The repository-wide forward-manifest test correctly found that the overlay and combined-context manifests still referenced the previous parent hash.

## Repair

The parent validation/replay reports were regenerated, the candidate-context overlay was rebuilt from its recorded command, and the combined transcript context was rebuilt from its recorded command. Both downstream manifests were then validated and replayed in isolation; the combined manifest was promoted to `manifest_stage: "verified"` with its run marked `verified`.

- Parent: `verified_public_dataset_manifest`, 11 files, 2 runs; replay: 7 output checks.
- Candidate overlay: `verified_public_dataset_manifest`, 15 files, 1 run; replay: 1 output check.
- Combined context: `verified_public_dataset_manifest`, 33 files, 1 run; replay: 2 output checks.
- All three layers returned zero issues, and the repository-wide forward-manifest test now checks the updated hashes.

## Reproducibility hashes

| Layer | Manifest | Validation | Replay |
|---|---|---|---|
| Parent rhythm evidence | `f5fa2be244eb9d32cf84b35e57ef098125042cb798e97daeebed570e24d01ff2` | `7ada5eb9b85fb4abb7225269ddc6f018f9b3847c66a84172cf26a18302e33795` | `bf36ca66bf7e79476eed997a3df54d205ded651631ecc6e58a140de0caf3e38e` |
| Candidate context overlay | `bf638203a16555a11656acc2bc270109c81e12f6b4d27f70f7e87ecbe6d14c24` | `0e12803e7cb9d80bd870f7b94913a5cdb9f1c39ed2d28a99f957fc730a82fa9f` | `1ec1b45859a2bd42fb4e95331a79e28874792b4ba2689e5747e0a2e20192cfff` |
| Combined transcript context | `abca33de8844871ae719a2cb569fc5fcd1a12a740c9d79a063c1b537634c9d11` | `e0e7a697b0cdbbae2499501a41b431ba86f36637504f790c230de19d3e1bb453` | `23ef8a06c1ebc7d82ca6db75ee7a19cbe690fb865a3c32ab25fecd55dad0c0d8` |

## Scientific boundary

This repair changes provenance integrity, not biological interpretation. The linked datasets remain transcript-level context; they do not establish channel protein, native current, membrane-potential rhythm, behavior, fly-level replication, or causality.
