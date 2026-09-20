# Provenance-aware nested cosinor inference

Use `scripts/analyze_preanalysis_nested_cosinor.py` when a verified ephys or imaging bundle contains multiple subunits, ROIs, cells or technical measurements per biological replicate. The wrapper first runs the metadata/raw-QC/derived-measurement bundle gate, then requires a declared `--time-system ZT` or `--time-system CT`, selects one `metric_name`, rejects mixed `value_unit` values, aggregates subunits within each `biological_replicate_id × time_hours` cell, and delegates to the dependency-light nested cosinor implementation.

The exploratory output uses within-biological-unit time-label permutation when each replicate has repeated time points and biological-unit cluster bootstrap for confidence intervals. It reports `experimental_unit`, number of biological replicates, subunits and aggregated observations. The result is not a formal mixed-effects model: no publication-grade causal or significance claim should be made from it. `--stage formal` is blocked even when all input gates pass.

Safety gates:

- Raw-file existence and SHA-256 checks are on by default. `--no-check-files` is an explicit provisional override and is recorded in `warnings`; a `qc_status=pass` record whose `file_status` is not `present` is blocked under the default.
- Use an explicit `--metric-name` whenever the measurement table contains more than one readout. Do not pool membrane voltage, firing rate, calcium fluorescence or other quantities. Rows with a missing `metric_name` are blocked whenever any named metric is present, rather than silently dropped. Add `value_unit` to the derived table; missing units are warned, and incompatible units block the run.
- Any non-empty condition field such as `treatment`, `blocker`, `concentration`, `vehicle`, `RNAi`, `effector` or `temperature_shift` must be included in `--group-by`; otherwise controls and perturbations are not pooled silently.
- Duplicate metadata join keys and duplicate raw `record_id` values are blocked.

Top-level status semantics are intentionally separate: `input_gate=verified_preanalysis_bundle` means only that files and joins passed; `analysis_status=executed_exploratory` means a calculation ran; `scientific_status=exploratory_not_verified` and `formal_status=blocked_requires_mixed_model` prevent either from being misread as biological confirmation.

Example:

```powershell
python scripts/analyze_preanalysis_nested_cosinor.py `
  --metadata validation/synthetic-ephys-nested-metadata.csv `
  --raw-qc validation/synthetic-ephys-nested-raw-qc.csv `
  --measurements validation/synthetic-ephys-nested-derived.csv `
  --assay ephys --stage exploratory --check-files `
  --time-system ZT --metric-name resting_membrane_potential `
  --n-permutations 1000 --n-bootstrap 1000 --seed 20260906 `
  --output validation/synthetic-ephys-nested-cosinor.json
```

For a formal paper analysis, retain the bundle and this exploratory result as an audit trail, then use the ready mixed-effects handoff, convergence/residual checks and pre-specified contrasts once a supported backend is available.
