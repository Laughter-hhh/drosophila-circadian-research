# Iteration record — target-cell-specific evidence and ranking gate

Date: 2026-09-20  
Status: verified for evidence-scope matching, score triage, and deterministic GSE157504 handoff. This does not establish channel causality or publication-grade biological conclusions.

## Failure modes reproduced

- Records that named only a broad neuron group could pass a directness gate for a more specific requested subtype (for example, generic `LNv` used as evidence for `s-LNv`). A DN1p observation could similarly be read as evidence for all `DN`.
- When all candidate score fields were `NA`, the sensitivity output still selected a first candidate based on input order and described it as a stable Top.
- After correcting the all-`NA` case, a second public-evidence replay showed that scored-but-mismatched candidates could still be presented as the “Top” for a target cell with no matching evidence. Partial-coverage candidates could also become a Top for broad `DN`.
- The GSE157504 bridge report counted zero candidates with all ranking dimensions unscored, although the generated rows correctly contained `NA` in all seven dimensions. The counter sliced the evidence schema at the wrong indices and accidentally included `evidence_label`.

## Changes made

- Added `evidence_target_cells` to candidate and search-log schemas. Direct candidate claims must be supported by checked log records with matching target scope, readout, and named cell groups.
- Added a target-cell taxonomy and matching gate to `scripts/score_candidates.py`. Broad-parent, partial-subset, ambiguous mixed cluster, exact, and mismatch cases remain distinct. The user must explicitly pass one or more `--target-cell` values for target-specific shortlist status.
- Preserved full scored rankings as a long-list aid, but restricted the sensitivity `top_candidates` field to target-scoped `pass` or `conditional_directness` rows. Mismatched, partial, and unscored candidates cannot become Top; ties are reported as a full set, and no target-scoped candidate yields an empty Top with an explicit status.
- Corrected the GSE157504 bridge's unscored-dimension count to iterate over an explicit seven-field tuple and added an assertion that all 15 real handoff rows remain unscored.
- Updated the static literature table and checked-source log with subtype-specific evidence: Shaw/Shal are recorded as separate s-LNv and l-LNv recordings; *na* (Narrow abdomen) is recorded for DN1p and the l-LNv supplemental result, not all DN or all LNv. The cell mapping is supported by the primary papers: [Smith et al., PMID 31612994](https://pubmed.ncbi.nlm.nih.gov/31612994/) and [Flourakis et al., PMID 26276633](https://pubmed.ncbi.nlm.nih.gov/26276633/) (including [Supplementary Figure S4](https://web.njit.edu/~diekman/papers/FlourakisEtAl_Cell_2015_ArticlePlusSupplemental.pdf)).

## Real-data outcome

The GSE157504 handoff produced 15 candidate rows and 30 source-log rows. Fourteen had nonzero raw UMI detection in at least one eligible target group; nine had an author-reported high-confidence rhythm row in a target group. All 15 rows have all seven numeric candidate-ranking dimensions marked `NA`. The scorer therefore reports `insufficient_scored_evidence`, empty rankings, and no Top candidate. These are transcript-level observations only; they do not establish protein abundance, channel current, membrane-potential rhythm, fly-level prevalence, or causal behavior.

The independently curated candidate table was scored with one target-cell query at a time. Resulting target-scoped shortlists were:

| Target query | Target-specific direct-gate pass | Conditional directness | Top interpretation |
|---|---|---|---|
| `s-LNv` | Shaw, Shal | Irk1 | Shaw and Shal tie; no arbitrary single winner |
| `l-LNv` | *na*, Shaw, Shal | Irk1 | *na* is the score Top, with Shaw/Shal also passing the direct gate |
| `LNd` | none | none | No target-scoped Top; high-scoring mismatches remain only in the long list |
| `DN` | none | none | *na* has DN1p subset evidence only; it is partial coverage and cannot become a Top for all DN |

These rankings reflect the input evidence ratings and transparent scoring rule, not a final biological conclusion. The transcript-only GSE bridge itself contributes no numeric score.

## Verification

- Full suite: `python -m unittest discover -s tests -v` — 263 tests passed.
- Focused target-cell suite — 10 tests passed, including exact subtype match, broad-parent unresolved, DN1p partial coverage, mismatch, all-`NA` no-Top, ties, and rejection of mismatched/partial Top candidates.
- Focused real GSE157504 evidence-bridge tests — 4 passed, including the 15/15 unscored-dimension counter assertion and evidence/search-log schema checks.
- GSE157504 manifest gate: `verified_public_dataset_manifest`, 11 files, 4 runs, zero issues/warnings.
- Isolated manifest replay: `verified_public_dataset_replay`, 4 runs, 7 output-hash checks, zero mismatches.
- Research task contract: validated after recording the final run.
- Skill Creator `quick_validate.py` could not run because the bundled Python runtime lacks `PyYAML` (`ModuleNotFoundError`). No dependency was installed; the skill frontmatter was inspected manually. This remains a tooling limitation, not a pass of the official quick validator.

## Reproduction commands

From the skill repository root:

```powershell
python -m unittest discover -s tests -v
python scripts/validate_public_dataset_manifest.py validation/public-data/GSE157504-candidate-evidence-bridge-manifest.json --output validation/public-data/GSE157504-candidate-evidence-bridge-manifest-validation.json
python scripts/replay_public_dataset_manifest.py validation/public-data/GSE157504-candidate-evidence-bridge-manifest.json --root . --output validation/public-data/GSE157504-candidate-evidence-bridge-replay.json
python scripts/score_candidates.py validation/public-data/candidate-evidence-real.csv --target-cell s-LNv --output validation/public-data/candidate-target-cell-score-slnv.csv --sensitivity-output validation/public-data/candidate-target-cell-sensitivity-slnv.json
```

Repeat the last command with `l-LNv`, `LNd`, or `DN` and the corresponding output suffix to reproduce the other target-specific results.

