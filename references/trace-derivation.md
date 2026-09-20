# Standardized trace-to-measurement derivation

Use `scripts/derive_trace_measurements.py` after exporting vendor files (for example ABF/CED/TIFF) into an auditable normalized UTF-8 CSV. The script deliberately does not guess vendor-specific binary decoding. It requires a raw-QC manifest and experiment metadata, validates both, and converts only `qc_status=pass` records.

Input columns:

- all assays: `record_id,time_seconds,value`;
- imaging additionally: `roi_id`.

For ephys it emits one mean measurement per passing record by default; for imaging it emits one mean measurement per passing ROI. Circadian `time_hours` is parsed from metadata `ZT_or_CT` in the default `metadata` mode, never inferred from trace acquisition time. Each output row includes `metric_name`, `value_unit`, `subunit_id`, trace sample count, duration, `time_basis` and the input file hashes are recorded in the report.

Long traces must not be silently collapsed when the scientific question is about within-record temporal structure. Use:

- `--time-mode metadata` (default): one whole-trace summary anchored to metadata ZT/CT;
- `--time-mode metadata_plus_elapsed --time-bin-seconds 3600`: one row per explicit elapsed-time bin, added to the metadata ZT/CT anchor. This requires a documented trace start time and emits an anchoring warning;
- `--time-mode elapsed`: one row per bin in within-record elapsed time, but it is not comparable across records until an external ZT/CT anchor is supplied, so the script emits a warning.

`--check-files` is on by default. A passing QC record with `file_status` other than `present` is blocked under the default; `--no-check-files` is an explicit provisional override and is recorded in the report. Missing pass-record traces, nonfinite samples, too-short bins, imaging ROI-count mismatches, missing/invalid ZT/CT and malformed columns block the run. Non-pass records in the trace export are ignored with an explicit warning.

The resulting CSV can be passed to `validate_preanalysis_bundle.py`, `analyze_preanalysis_cosinor.py` or `analyze_preanalysis_nested_cosinor.py`. For ΔF/F, spike detection, event detection or voltage-clamp current extraction, define and validate the normalization/windowing rule before using this generic mean-value adapter.

Example:

```powershell
python scripts/derive_trace_measurements.py `
  --traces normalized-ephys.csv `
  --metadata metadata.csv --raw-qc raw-qc.csv `
  --assay ephys --stage exploratory --check-files `
  --time-mode metadata_plus_elapsed --time-bin-seconds 3600 `
  --metric-name resting_membrane_potential --value-unit mV `
  --output derived.csv --report derivation.json
```

This is a deterministic extraction/QC step, not a claim that the derived signal is rhythmic or channel-specific.
