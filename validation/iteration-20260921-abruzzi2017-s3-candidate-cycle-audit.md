# Iteration — exact-symbol audit of published clock-neuron cycler calls

Date: 2026-09-21
Status: verified for parsing, source mapping, manifest integrity and isolated replay. The manuscript-versus-supplement LNv count mismatch remains unresolved and is not treated as a biological result.

## Purpose

The existing candidate evidence table prioritized electrophysiological and genetic evidence but did not systematically cross-check the candidates against the authors' published transcript-cycling lists for specific clock-neuron groups. This iteration adds that check as a separate evidence layer. It does not alter the candidate score or promote transcript cycling to channel-current evidence.

## Implementation

- Added `scripts/audit_published_cycle_candidates.py`. It parses the official S3 XLSX with Python's standard-library ZIP/XML tools, resolves each sheet's column indices from its own headers, performs case-sensitive exact full-symbol matching, and preserves duplicate rows and source row numbers.
- Added synthetic tests for the actual per-sheet F24/JTK header-order variation, exact separation of `Sh`, `Shal` and `Shaw`, duplicate source rows, `not listed` semantics and ambiguous-header rejection.
- Added a constrained public-data replay allowlist entry, provenance manifest, audit CSV/JSON, and routing instructions in `SKILL.md` plus `references/geo-data-workflow.md`.
- Added `references/published-cycle-table-workflow.md` to document cell-group scope, author thresholds, interpretation boundaries, source count comparison and reusable commands.

## Real-data result

The audit covered 15 candidate genes across three target groups and emitted 45 candidate-group rows. Six group-level entries were listed across five unique candidates:

| Candidate | Published group entry | Source call | Interpretation boundary |
|---|---|---|---|
| `Shab` | LNv | HC | Mixed PDF-positive s-/l-LNv transcript evidence; no protein/current inference. |
| `Shab` | DN1 subset | LC | One of two author methods only. |
| `Sh` | LNd group | LC | LNd group also includes the fifth PDF-negative s-LNv; this is distinct from `Shal` and `Shaw`. |
| `para` | LNv | LC | Mixed LNv group and transcript-only evidence. |
| `cac` | LNd group | LC | Mixed LNd group and transcript-only evidence. |
| `sei` | LNv | LC | Mixed LNv group and transcript-only evidence. |

`Shaw`, `Shal`, `Irk1`, `na`, `Ca-alpha1D`, `Ca-alpha1T`, `slo`, `Irk2`, `Ork1` and `trpl` had no exact-symbol entry in the three selected S3 cycler worksheets. This means only “not listed in these tables.” It does not mean unexpressed or arrhythmic, and it does not contradict independent current-rhythm evidence for Shaw/Shal.

## Source discrepancy and scope

The article narrative reports 249 LNv HC cyclers; direct S3 parsing counts 252 unique HC symbols. LNd is 303 versus 303 and DN1 is 185 versus 185. The three target sheets show no disagreement between their HC/LC labels and F24/JTK flags. LNd contains two LC rows for `CG40498`; DN1 contains three LC rows for `Nopp140`. The LNv three-symbol difference is not explained by duplicate symbols or flag disagreement. Both 249 and 252 are retained without silently “correcting” either source.

The publication's LNv library combines PDF-positive small and large LNvs, its LNd group includes the fifth PDF-negative s-LNv, and its DN1s are a subset. The samples are pooled neuron libraries collected in two independent six-timepoint LD courses. The audit did not recompute the authors' normalization or rhythm statistics and does not establish protein levels, channel current, membrane potential or causal behavior.

## Verification

- Synthetic parser tests: 2 passed.
- Real source: 15 candidates, 3 target groups, 45 rows, 6 listed entries across 5 genes.
- Source QC: F24/JTK flags agree with HC/LC labels; manuscript-versus-S3 LNv count mismatch preserved.
- Provenance: manifest verified, 4 files / 1 run / zero issues.
- Isolated replay: verified, 1 run / 2 output hashes / zero issues.
- Full unit suite: 284 tests passed.
- Research task contract: `validation/Abruzzi2017-S3-channel-candidate-audit-task.json` records assumptions, acceptance criteria, evidence scope and limitations.

## Citation

Abruzzi, K. C. et al. RNA-seq analysis of Drosophila clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides. *PLoS Genet.* **13**, e1006613 (2017). https://doi.org/10.1371/journal.pgen.1006613.
