# Bundle-to-cosinor exploratory analysis

Use `scripts/analyze_preanalysis_cosinor.py` only after the metadata, raw-QC and derived-measurement bundle passes. The script joins every measurement to its raw record and metadata, averages repeated technical measurements within each `(biological_replicate_id, time_hours)` cell, then fits a fixed 24-hour (or user-specified) cosinor separately for the requested metadata strata.

Safety gates:

- `--time-system ZT` or `--time-system CT` is required before a fit. A numeric phase without a declared ZT/CT reference is not interpretable.
- Raw-file existence and SHA-256 checks are on by default. `--no-check-files` is an explicit provisional override and is recorded in `warnings`; a `qc_status=pass` record whose `file_status` is not `present` is blocked under the default.
- If `metric_name` or `value_unit` labels are present, they must be complete and unambiguous. Multiple readouts or physical units cannot be pooled silently; use `--metric-name` or separate bundles.
- Any non-empty condition field such as `treatment`, `blocker`, `concentration`, `vehicle`, `RNAi`, `effector` or `temperature_shift` must be included in `--group-by`; otherwise the run is blocked rather than pooling controls and perturbations.

The output distinguishes:

- `exploratory_descriptive_fit`: a descriptive mesor, amplitude, peak phase and R² were calculable;
- `insufficient_time_coverage`: the group lacks the configured number of observations or unique time points;
- `blocked_preanalysis_cosinor`: a provenance, join, field, label, condition or finite-number gate failed;
- `blocked_formal_cosinor_requires_mixed_model`: the bundle passed, but this script cannot make formal biological-unit-aware inference.

The top-level fields `input_gate`, `analysis_status`, `scientific_status` and `formal_status` keep input verification separate from scientific validation. For cross-sectional sampling (each fly contributes only one time point), the output labels the design and warns that it is not within-animal rhythm evidence. The result includes nested bundle reports and input SHA-256 values for reproducibility.

Example:

```powershell
python scripts/analyze_preanalysis_cosinor.py `
  --metadata validation/synthetic-ephys-cosinor-metadata.csv `
  --raw-qc validation/synthetic-ephys-cosinor-raw-qc.csv `
  --measurements validation/synthetic-ephys-cosinor-derived.csv `
  --assay ephys --stage exploratory --check-files `
  --time-system ZT --group-by cell_type,genotype `
  --metric-name resting_membrane_potential `
  --output validation/synthetic-ephys-bundle-cosinor.json
```

This is a QC-aware descriptive handoff, not evidence that an ion channel is rhythmic or causal. Formal claims require an auditable biological-unit-aware mixed-effects/permutation analysis, residual and convergence diagnostics, and independent validation.
