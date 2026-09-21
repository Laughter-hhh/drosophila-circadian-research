# Real-task forward-test refinements — 2026-09-21

Status: `executed`; candidate-scoring route independently verified, literature-reading post-edit rerun pending.

## Trigger and scope

Two blind forward uses exercised workflows that were already part of the skill:

1. Beginner-level bilingual, figure-by-figure reading of Smith et al. (2019), including all main-text figure panels, assay principles, conclusions, and public author-team context.
2. Target-specific screening of a 15-candidate evidence table against its 19-record structured evidence-search log for native membrane-potential/current evidence in s-LNv and l-LNv.

The evaluators were given raw article access points or the candidate table/log, not the expected scientific conclusions. Their outputs were isolated outside the repository. The initial reading and QA are at `E:\skill\.forward-test-lit-20260921-3a012d8546624ae0a8cdddd811ce2a2`; the initial candidate ranking run is at `E:\skill\.forward-test-current-1b05a69716784b46b646f31dc28bec2f`.

## Observed behavior

- The literature workflow explained the paper bilingually for a novice and inventoried 23 caption-labeled panels across Figures 1–7. It correctly did **not** claim visual verification: the Bristol author-manuscript PDF was not readable in the available web reader (403), the Wiley page resolved to the abstract, and artwork/supplement details remained inaccessible. The report marked this as a partial, caption-based reading.
- The QA found that access state and provenance were not sufficiently visible **per panel**, and that `n`/trial counts could not be mapped to the independent experimental unit from captions alone. These must remain `unknown` until the methods or supplement resolve them.
- The candidate workflow reproduced target-specific evidence triage. The evaluator also tried a `.json` suffix for the CSV `--output` and had to rerun with `.csv`; the scored longlist included candidates that did not pass the Top gate. The scorer already documents these semantics, but the main workflow did not directly route users to `candidate-scoring.md` whenever they invoked the scorer.

## Skill changes

- `SKILL.md` now routes `score_candidates.py` use to `references/candidate-scoring.md` as well as `candidate-ranking.md`; this exposes the output-format and gate-qualified Top interpretation at the point of use.
- `references/deep-literature-reading.md` now specifies a bounded source fallback sequence and a stop condition; requires an overall coverage/access label plus per-panel image/caption status and source provenance; prohibits inventing artwork-only labels; and preserves `unknown` for `n`, trials, and experimental units until methods or supplements define them.

No scorer implementation or serialization change was made. CSV raw longlists and JSON sensitivity reports are already documented choices; this iteration fixes the workflow routing so that guidance is loaded before invoking the scorer. A serialization change would require a separate compatibility migration because several public-data manifests hash the current scorer and its outputs.

## Verification

- Synthetic regression suite: `python -m unittest discover -s tests` — 296 tests passed after the instruction edits.
- Public-data manifest: `candidate-scoring-source-log-guard-manifest.json` — `verified_public_dataset_manifest`, 21 files and 6 runs, zero blocking issues; formal status remains `conditional_online_source_access`.
- Isolated replay: `verified_public_dataset_replay`, 6 runs and 11 output-hash checks passed. Reports were written outside the repository at `E:\skill\.verify-dd28ff0f7b9d45448a8c108ba625a134\`.
- `skill-creator/scripts/quick_validate.py` could not start because the available Python runtime lacks `PyYAML` (`ModuleNotFoundError: yaml`). The skill frontmatter was unchanged; its required `name` and `description`, reference paths, and diff whitespace were manually checked.
- Fresh candidate-scoring route rerun read the references selected by the revised skill routing. Candidate-table and source-log validators passed (15 candidates; 19 log records); both requested targets produced 15-row CSV longlists and parseable JSON sensitivity reports in `E:\skill\candidate-ranking-eval-2b61b6e660be44278f5f26bf40e1b9d8\`. The s-LNv output reports a Shaw/Shal tie (91.67; coverage 0.970) across all three weight scenarios; l-LNv reports `na` as the unique Top (92.93; coverage 1.00), with Shaw/Shal tied next. The evaluator used copies of the three scripts that were byte-identical to the repository versions. These are evidence-triage outputs, not causal conclusions.

  From that isolated directory, the evaluator ran (using the bundled Python 3.12.14 executable in this Windows environment):

  ```powershell
  python scripts/validate_evidence_search_log.py data/candidate-evidence-search-log.csv --output evidence-search-log-validation.json
  python scripts/validate_candidate_evidence.py data/candidate-evidence-real.csv --search-log data/candidate-evidence-search-log.csv --output candidate-evidence-validation.json
  python scripts/score_candidates.py data/candidate-evidence-real.csv --search-log data/candidate-evidence-search-log.csv --readout-match membrane_potential_or_current --target-cell s-LNv --output ranking-s-LNv.csv --sensitivity-output sensitivity-s-LNv.json
  python scripts/score_candidates.py data/candidate-evidence-real.csv --search-log data/candidate-evidence-search-log.csv --readout-match membrane_potential_or_current --target-cell l-LNv --output ranking-l-LNv.csv --sensitivity-output sensitivity-l-LNv.json
  ```
- The fresh literature-reading rerun is still in progress. Do not promote the figure-reading changes to fully behavior-verified until that output is reviewed; the prior test remains partial because the source artwork was inaccessible.

## Evidence limits

This validates instruction routing, provenance reporting, and reproducible evidence triage—not a biological claim about channel causality. For the 2019 paper, the inaccessible figure artwork, axes/units, representative traces, and supplementary materials remain unverified. The output files from the independent evaluators are separate test artifacts and are not being presented as figure-image verification.

Source: Smith, P., Buhl, E., Tsaneva-Atanasova, K. & Hodge, J. J. L. Shaw and Shal voltage-gated potassium channels mediate circadian changes in Drosophila clock neuron excitability. *J. Physiol.* **597**, 5707–5722 (2019). https://doi.org/10.1113/JP278826.
