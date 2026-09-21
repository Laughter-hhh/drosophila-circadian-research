# Candidate scorer source-log fail-closed iteration — 2026-09-21

## Trigger

A prior blind evaluation appeared to classify `Irk1` as conditional direct for native s-LNv current. Audit showed that report had scored a candidate table whose SHA-256 (`DDDC50…`) did not match the current authoritative table (`5908ea101e20e6975d8a20fb229f66959f6de62efa42bbe66176a1020ae13f0c`). Re-running the current candidate table with its current source log already kept `Irk1` at `needs_direct_evidence`; the stale report was not valid evidence of a current scorer regression.

The audit did expose a forward-safety gap: the CLI allowed scoreable/native-current candidate tables to be ranked without a source log, and a supplied source log was validated separately rather than jointly against candidate summary claims at the scoring boundary. That left room for an old or mismatched summary to reach a ranking if a caller skipped the documented pre-validation step.

## Change

`scripts/score_candidates.py` now fails closed when a table contains numeric score dimensions or declares `membrane_potential_or_current` but lacks the paired `--search-log` and `--readout-match`. With a log, it validates the candidate table against that same log before ranking. A validation failure stops before output creation. The no-log diagnostic exception remains narrowly limited to all-`NA`, non-current context tables, which cannot produce a Top.

The scorer documentation now clarifies the CSV output format and distinguishes the complete ranked longlist from gate-qualified Top results: raw scores do not make an ineligible candidate a Top.

## Verification

- Added five synthetic regression cases for omitted logs, scored non-current tables without logs, current all-NA input without logs, candidate/log mismatch before output, and preserving the all-NA transcript diagnostic.
- Full suite: 296 tests passed.
- Current real table/log: 15 candidates, 19 source-log records, zero validation issues.
- Target-gated result: s-LNv Shaw/Shal tie; l-LNv `na` is unique Top with Shaw and Shal also passing; LNd and broad DN have no direct Top. `Irk1` remains `needs_direct_evidence` for s-/l-LNv native current.
- GSE157504 all-NA diagnostic: `insufficient_scored_evidence`, empty rankings, no Top.
- New public-data manifest: 21 files / 6 runs, verified with zero issues; isolated replay reproduced 11 output hashes.
- GSE157504 context overlay, GSE157504 evidence bridge, and combined transcript-context parent chains were revalidated and replayed after the scorer change.
- Independent blind forward test, using the current skill and raw evidence inputs without consulting previous reports, reproduced the four target outcomes and confirmed that DN1p-only evidence cannot be generalized to all DN.

## Interpretation and limits

These outputs validate a reproducible evidence-triage workflow, not channel causality or biological function. In particular, the checked `Irk1` S2-R+ patch clamp is cultured heterologous-cell evidence; ClopHensor measures intracellular chloride rather than current; behavioral and expression records are separate readouts. No fresh full-text audit was performed in this iteration, and a formal electrophysiology design still depends on user-provided preparation, animal, temperature, time-system, reagent, power, and QC details.
