# Iteration 2026-09-20: Native electrophysiology evidence and pharmacology source audit

## Scope and status

Status: `verified` for the source-attribution and machine-validation changes below. This audit verifies the cited paper-to-record mapping and the repository's structural/evidence-scope gates; it does not establish any new channel mechanism or local pharmacological selectivity.

The release audit began with the real candidate evidence table, its structured search log, the primary channel source table, and the Smith et al. pharmacology plan/source-log bundle. Primary article records and figure legends were checked against PubMed/PMC or journal-hosted full text on 2026-09-20.

## Problems found and corrections

1. The PMID `23010658` record was assigned to the wrong paper in an earlier snapshot. It is Ruben, Drapeau, Mizrak & Blau (2012), “A mechanism for circadian control of pacemaker neuron excitability,” *J. Biol. Rhythms* **27**, 353–364, DOI `10.1177/0748730412455918`. The article studies rhythmic `Ir` expression (mapped by FlyBase to `Irk1`) and LNv-targeted genetic/behavioral and PER outcomes; it does not record a native `Irk1` current. Its behavior-only log record is now `indirect` relative to the candidate table's current/membrane-potential directness gate, while the transcript/localization record remains a molecular-readout record. This label is specific to the ranking question; it does not deny that the paper directly manipulated LN(v)s and measured behavior.
2. The `na` record is now linked to Flourakis et al. (2015), *Cell* **162**, 836–848, DOI `10.1016/j.cell.2015.07.036`. The described whole-cell current-clamp/voltage-clamp and sodium-substitution evidence is restricted to DN1p neurons, including `na` mutant and DN1p-targeted rescue evidence. The table explicitly prohibits transferring this evidence to s-LNv, l-LNv or LNd.
3. The Schellinger et al. (2022) record separates the in-vivo s-LNv ClopHensor/genetic/behavioral readouts from the `Irk1` whole-cell current measured in transfected S2-R+ cultured cells. The candidate remains `near_direct` for the native electrical-readout question.
4. Smith et al. (2019), *J. Physiol.* **597**, 5707–5722, DOI `10.1113/JP278826`, is recorded with the l-LNv genetic validation of the native blocker-sensitive components and the paper's starting concentrations: DTX 100 nM, GxTX 20 nM, BDS 300 nM and PaTX 100 nM. The plan remains `conditional_pilot`: local dose-response is `not_assessed`, local washout is `needs_confirmation`, and the source-level `native_verified` label is not local validation or proof of absolute selectivity. An unquoted comma in the `off_target_risk` field was also fixed; the CSV regression test now rejects rows parsed with extra/missing fields.

## Verification

- Candidate evidence + search-log joint gate: `verified_candidate_evidence_table`; 15 candidate rows and 17 structured source records, no issues.
- Pharmacology source log: `verified_pharmacology_source_log`; four blocker-specific records with matched paper concentrations.
- Pharmacology bundle and plan: `verified_pharmacology_bundle` / `verified_pharmacology_plan`, while `formal_status=conditional_pilot_only`. This correctly preserves the local dose-response and washout gates.
- When the additional candidate-evidence linkage gate is enabled, `Shaker`→`Sh` and `Shab` remain blocked because their candidate evidence labels are `unverified`. The checked synonym mapping only resolves nomenclature; it does not upgrade evidence. This is an expected stop, not a pharmacology source-log failure.
- Added five focused regression tests for citation/gene mapping, readout-specific directness, DN1p scope, native-versus-cultured patch readout, and blocker field/alignment checks.
- Full suite: `python scripts/run_tests.py` — 250 tests passed.
- `git diff --check` — passed.
- `skill-creator`'s `quick_validate.py` could not execute because the available Python runtime lacks PyYAML (`ModuleNotFoundError: yaml`); no dependency was installed. The frontmatter was visually checked, and repository tests passed.

The machine checks establish schema, provenance linkage, and stage-gate consistency. They do not replace local stock checks, dose-response/washout experiments, or causal experiments in each target neuron.

## Primary sources

- Ruben, M., Drapeau, M. D., Mizrak, D. & Blau, J. A mechanism for circadian control of pacemaker neuron excitability. *J. Biol. Rhythms* **27**, 353–364 (2012). https://doi.org/10.1177/0748730412455918
- Flourakis, M. et al. A conserved bicycle model for circadian clock control of membrane excitability. *Cell* **162**, 836–848 (2015). https://doi.org/10.1016/j.cell.2015.07.036
- Smith, P., Buhl, E., Tsaneva-Atanasova, K. & Hodge, J. J. L. Shaw and Shal voltage-gated potassium channels mediate circadian changes in Drosophila clock neuron excitability. *J. Physiol.* **597**, 5707–5722 (2019). https://doi.org/10.1113/JP278826
- Schellinger, J. N. et al. Chloride oscillation in pacemaker neurons regulates circadian rhythms through a chloride-sensing WNK kinase signaling cascade. *Curr. Biol.* **32**, 1429–1438.e6 (2022). https://doi.org/10.1016/j.cub.2022.03.017
