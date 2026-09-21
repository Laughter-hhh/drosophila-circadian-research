# Iteration — score-neutral joint transcript-context sidecar

Date: 2026-09-21
Status: verified for source lineage, group crosswalk, score invariance, manifest integrity and isolated replay. The PLOS manuscript-versus-S3 LNv HC-count difference remains unresolved and is not promoted to a biological finding.

## Gap addressed

The repository already had two useful but separate products: a GSE157504 candidate context overlay and an exact-symbol parser for Abruzzi et al. (2017) S3 transcript-cycler tables. A researcher still had to compare them manually, creating a risk that a pooled LNv, mixed LNd or partial DN1 call would be treated as target-subtype evidence or that published transcript calls would be allowed to influence the existing current/electrophysiology score.

## Implementation

- Added `scripts/build_published_cycle_candidate_context.py` as a separate downstream sidecar builder; the existing GSE context builder and its outputs were not modified.
- The builder revalidates both parent manifests against current files, requires the stored isolated replays to attest to the exact CSV and report hashes, and cross-checks the PLOS audit CSV against `candidate_summary`, source row numbers, HC/LC flags and source classes.
- Added an explicit target crosswalk: pooled PDF-positive LNv to both s-LNv and l-LNv rows (not subtype-resolved); LNd-plus-fifth-PDF-negative-s-LNv to LNd (not LNd-only); DN1 subset to DN (not all dorsal neurons).
- Preserves every base context field verbatim. HC/LC, not-listed, absent-from-audit, unmapped target and conflicting-row cases remain distinct. Exact workbook row references and author F24/JTK flags are retained. Duplicate class conflicts are surfaced, never collapsed.
- Added the new script to the isolated replay allowlist with regression coverage; added a focused reference and a router entry in `SKILL.md`.

## Real-data result

The source inputs contain 15 literature candidates. The base GSE context and PLOS audit each cover those same 15 symbols; the pre-existing GSE-only `eag` and literature-only `na` difference is retained in the GSE context report and unchanged in the joined rows.

The join emits 60 candidate-by-target rows. The PLOS tables contain six distinct candidate-by-source-group calls across five candidate genes; because the pooled LNv group is cross-referenced on both s-LNv and l-LNv rows, these appear as nine target-row annotations, not nine independent source calls:

| Candidate | PLOS S3 source group | Author call | Context mapping limit |
|---|---|---|---|
| `Shab` | pooled PDF-positive LNv | HC | Displayed on s-LNv and l-LNv rows; source cannot resolve subtype. |
| `Shab` | DN1 subset | LC | Context for a DN1 subset, not all DN. |
| `Sh` | LNd plus fifth PDF-negative s-LNv | LC | Not LNd-only. |
| `para` | pooled PDF-positive LNv | LC | Displayed on s-LNv and l-LNv rows; source cannot resolve subtype. |
| `cac` | LNd plus fifth PDF-negative s-LNv | LC | Not LNd-only. |
| `sei` | pooled PDF-positive LNv | LC | Displayed on s-LNv and l-LNv rows; source cannot resolve subtype. |

The 60-row sidecar contains 2 HC target rows, 7 LC target rows and 51 rows marked “not listed in the selected published cycler sheets.” The latter does not mean not expressed or arrhythmic. All 32 base GSE-context columns—including detection/rhythm context, literature score, coverage, ephys directness, shortlist gate and readout—are byte-value equivalent at the CSV-cell level; no score or gate is recomputed.

The output carries the source discrepancy forward: the manuscript narrative reports 249 LNv HC cyclers, while S3 parsing finds 252 unique HC symbols. LNd (303) and DN1 (185) agree with the manuscript totals. The combined sidecar does not reconcile the LNv discrepancy. PLOS groups and study scope were checked against the primary article, which states that the LNvs combine PDF-positive small and large neurons, the LNd group includes the fifth PDF-negative s-LNv, and the profiled DN1s are a subset [Abruzzi *et al.*, *PLoS Genet.* **13**, e1006613 (2017)](https://doi.org/10.1371/journal.pgen.1006613).

## Verification

- Synthetic crosswalk, missingness, source-conflict and duplicate-context-key tests: 6 passed.
- Replay-gate tests: 5 passed; explicitly checks the new builder's safe Python argv allowlist.
- Real parent chains: both source manifests revalidated against current file hashes; both stored parent replays attest to the exact CSV and report outputs.
- Real data: 15 candidates x 4 target groups = 60 rows; six source-group calls across five genes; scores/gates preserved; LNv source discrepancy retained.
- Composite provenance: `verified_public_dataset_manifest`, 33 files, one run, zero issues.
- Isolated replay: `verified_public_dataset_replay`, one run, two output hashes verified, zero issues.
- Full repository suite: 291 tests passed.
- Research task contract: `validation/combined-published-cycle-candidate-context-task.json` passes `scripts/validate_research_task.py` and is marked `verified` for this descriptive join only.
- The skill-creator `quick_validate.py` could not start because the configured Python runtime lacks PyYAML (`ModuleNotFoundError: yaml`). No package was installed; frontmatter, skill name, new route and referenced files were checked directly.

## Interpretation boundary and next use

This is planning context for prioritizing follow-up assays, not a new ranking and not evidence that any channel's current causes a membrane-potential rhythm. The next information-gaining step is to combine these transcript annotations with candidate-specific target-cell electrophysiology and genetic-tool evidence, retaining the existing directness gate; any formal perturbation still needs cell-specific causal evidence, adult-onset/developmental controls, and an experiment-unit-aware design.

## Reproducible artifacts

- Table: `validation/public-data/combined-transcript-candidate-context.csv`
- Report: `validation/public-data/combined-transcript-candidate-context-report.json`
- Manifest/validation/replay: `validation/public-data/combined-transcript-candidate-context-manifest.json`, `validation/public-data/combined-transcript-candidate-context-manifest-validation.json`, and `validation/public-data/combined-transcript-candidate-context-replay.json`
- Workflow instructions: `references/combined-transcript-candidate-context.md`
- Code and tests: `scripts/build_published_cycle_candidate_context.py`, `tests/test_published_cycle_candidate_context.py`, and `tests/test_public_dataset_replay.py`

Abruzzi, K. C. *et al.* RNA-seq analysis of *Drosophila* clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides. *PLoS Genet.* **13**, e1006613 (2017). https://doi.org/10.1371/journal.pgen.1006613.
