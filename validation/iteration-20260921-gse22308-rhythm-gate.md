# GSE22308 circadian expression gate replay — 2026-09-21

Status: verified for manifest integrity and deterministic pipeline replay; exploratory_not_verified for biological inference. This report tests whether the workflow distinguishes pooled-cell sample replicates from individual flies and blocks rhythm claims when a group has too few time points.

## Task contract

~~~yaml
task_id: gse22308-clock-neuron-candidate-rhythm-gate-20260921
status: verified
scientific_status: exploratory_not_verified
research_question: Does the GEO expression workflow block two-timepoint groups and keep four-timepoint pooled-cell results exploratory rather than animal-level or causal?
species: Drosophila melanogaster
preparation: adult purified PDF-positive clock-neuron pools; processed Affymetrix/GCRMA series matrix
target_groups: large_PDF_circadian_neurons; small_PDF_circadian_neurons; ELAV neuron control
experimental_unit: pooled_cell_sample
primary_readout: candidate transcript abundance from GCRMA log2 processed values
time_system: ZT under LD 12:12
input_files:
  - validation/public-data/GSE22308_series_matrix.txt.gz
  - validation/public-data/GPL1322.annot.gz
  - validation/public-data/GSE22308_sample_metadata.csv
required_metadata:
  - sample accession and matrix alignment
  - cell group, genotype/background and ZT
  - replicate label and experimental-unit class
  - temperature and batch (retain unknown when absent)
analysis_plan: Validate the GEO manifest, replay its five declared processing/analysis runs, and assert cell-type-specific timepoint gates on the 19-candidate real-data table.
decision_gate: Two unique time points must not yield a rhythm inference; four-point results remain exploratory for pooled samples, with formal inference blocked when experimental design/batch support is insufficient.
acceptance_tests:
  - manifest status verified_public_dataset_manifest
  - replay status verified_public_dataset_replay with output hashes matched
  - Sh in small PDF clock neurons remains insufficient_or_invalid_time_series
  - Sh in large PDF clock neurons is exploratory_inferential_cosinor, not formal or causal evidence
~~~

## Public source and design facts

- Official GEO record: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE22308
- Primary paper: Kula-Eversole, E. et al. Surprising gene expression patterns within and between PDF-containing circadian neurons in Drosophila. Proc. Natl. Acad. Sci. U.S.A. 107, 13497–13502 (2010). https://doi.org/10.1073/pnas.1002081107
- GEO identifies D. melanogaster, Affymetrix Drosophila Genome 2.0, adult purified clock-neuron expression profiling under LD. Its design lists four time points for large PDF neurons and two for small PDF neurons.
- Repository metadata classifies each sample as pooled_cell_sample. Sample-level replicate labels do not identify individual flies. temperature_C and batch_id are unknown in the metadata used here.

## Execution and outcomes

Manifest validation found 12 registered files and 5 declared runs with zero blocking issues. Isolated replay reran all 5 commands and matched all 7 declared output hashes. Machine-readable rerun reports:

- validation/public-data/GSE22308-provenance-validation-rerun-20260921.json
- validation/public-data/GSE22308-replay-rerun-20260921.json

The 19-candidate cosinor report contains 76 candidate × cell-group × background groups:

- 19 groups with four unique time points in large PDF circadian neurons, yw passed only the exploratory sample-level cosinor branch.
- 57 groups with two unique time points—including all small PDF circadian neuron, yw groups, ELAV controls and per01 large-PDF groups—were returned as insufficient_or_invalid_time_series.
- For Sh, the large-PDF group comprises 10 pooled samples across four ZT points and remains exploratory; the small-PDF group comprises four pooled samples at two ZT points and receives no rhythm estimate.
- The top-level result remains scientific_status=exploratory_not_verified and formal_status=blocked_requires_mixed_model; metadata warnings retain unknown batch and temperature. No expression value here establishes channel current, membrane potential, or causal behavior effects.

## Reproduction

~~~powershell
python scripts/validate_public_dataset_manifest.py validation/public-data/GSE22308-provenance-manifest.json --root . --output validation/public-data/GSE22308-provenance-validation-rerun-20260921.json
python scripts/replay_public_dataset_manifest.py validation/public-data/GSE22308-provenance-manifest.json --root . --timeout-seconds 120 --output validation/public-data/GSE22308-replay-rerun-20260921.json
python -m unittest discover -s tests -p test_cosinor_inference.py
~~~

The real-data integration test asserts the Sh large-PDF/four-timepoint exploratory branch, the small-PDF/two-timepoint block, pooled-sample units, unknown batch/temperature warnings, and formal-status boundary. This is a reproducibility/gating validation—not an independent biological reanalysis or proof of channel rhythm.
