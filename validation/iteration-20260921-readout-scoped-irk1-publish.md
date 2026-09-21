# 2026-09-21 — Readout-scoped Irk1 evidence and GitHub release

## Trigger

An independent forward-use audit of the candidate evidence workflow found that Irk1's s-LNv ClopHensor, LNv behavioral genetics, and S2-R+ whole-cell patch-clamp observations were compressed into one near-direct electrical record. That record could incorrectly satisfy native s-LNv and l-LNv electrophysiology gates.

## Source check

The primary paper separates these experiments: ex-vivo ClopHensor measures intracellular chloride in s-LNv; whole-cell patch clamp tests transfected Irk1 in S2-R+ cultured cells; and LNv-targeted Irk1 replacement is assessed through locomotor period. The paper does not report native s-LNv or l-LNv Irk1 current recordings.

Source: Schellinger et al., “Chloride oscillation in pacemaker neurons regulates circadian rhythms through a chloride-sensing WNK kinase signaling cascade,” Cell Reports (2022), https://pmc.ncbi.nlm.nih.gov/articles/PMC8972083/.

## Changes

- Split the paper into distinct intracellular-ion-concentration, cultured-cell-current, and LNv behavior/period search-log records.
- Reclassified the Irk1 current summary as indirect/unverified for clock-neuron electrophysiology; retained it as a pilot candidate without representing it as native current.
- Strengthened joint candidate/log validation: direct, near-direct, and indirect summaries must link to a checked record with the same source, readout, and target scope; named cell groups must be covered by those matching records.
- Added a real-data regression proving Irk1 does not pass the s-LNv or l-LNv membrane-potential/current gate, and a CLI smoke test for the documented source-log scoring command.
- Corrected source-scoped match reporting so an unverified target cell is reported as missing evidence rather than a cell-type mismatch.
- Refreshed subtype-specific ephys rankings and the GSE157504 bridge replay hashes.

## Verification

- Full suite: 266 tests passed.
- Candidate table: 15 rows; evidence log: 19 rows; both schema and joint-source validation passed.
- Four subtype-specific membrane-potential/current rankings were regenerated. Irk1 is needs_direct_evidence for s-LNv, l-LNv, LNd, and DN. Direct-pass shortlist candidates remain Shaw/Shal for s-LNv, and na/Shaw/Shal for l-LNv; LNd and DN have no direct-pass shortlist candidate in this evidence set.
- GSE157504 evidence bridge: 15 candidates and 30 source-log records; seven numeric ranking dimensions remain unrated for all candidates. Manifest validation passed (11 files, four runs, zero issues); isolated replay passed (seven output hashes, zero mismatches).
- GSE157504 rhythm extraction replay passed (two runs, seven output hashes, zero issues).
- skill-creator quick validator could not run because the available Python environment lacks PyYAML. The SKILL.md frontmatter itself was not changed in this release; no dependency was installed.

## Interpretation limit

These changes repair evidence provenance and ranking scope. They do not establish that Irk1 generates a native clock-neuron current rhythm or causes membrane-potential rhythms. The chloride and locomotor-period results remain separate evidence types from cultured-cell channel current.
