# Formal mixed-effects handoff

## Purpose and boundary

`scripts/prepare_mixed_model_input.py` is a strict preprocessing and model-specification gate. It does not fit a model and cannot create publication-level results by itself. It aggregates subunits within one `gene_symbol × cell_type × background × biological_replicate_id × time_hours` analysis stratum, verifies metadata, and writes a table plus a manifest that is either `ready_for_mixed_model` or `blocked_mixed_model_input`.

Use `scripts/emit_mixed_model_templates.py` only after a ready manifest. It emits equivalent starting templates for Python `statsmodels`, R `lme4` and MATLAB `fitlme`. The API/formula sources are collected in `references/mixed-model-runtime-sources.md`; templates must still be reviewed against the actual design, software versions and estimand before execution.

## Split multiple analysis strata first

If one source table contains multiple `gene_symbol × cell_type × background` combinations, split it before formal modeling:

```powershell
python scripts/split_mixed_model_input.py input.csv --output-dir validation/mixed/strata --output-manifest validation/mixed/strata-manifest.json
```

The splitter preserves the input columns and rows, writes deterministic per-stratum CSV files, records SHA-256 hashes and verifies row conservation. It does not infer metadata, aggregate observations or fit a model. Run `prepare_mixed_model_input.py` separately on every `output_file`; do not combine the resulting strata in one cosinor model unless the estimand explicitly requires a hierarchical multi-stratum model and its design is reviewed.

## Formal gate

The manifest blocks when any of the following is true:

- `experimental_unit` is missing, mixed or a technical-replicate label;
- more than one `gene_symbol × cell_type × background` stratum is supplied; split the input and run one model per stratum before inference;
- metadata differs within a biological-unit × time cell;
- `batch_id`, `sex`, `age_days`, `genotype`, `temperature_C` or `lighting` is missing/unknown;
- `age_days` or `temperature_C` is non-numeric/non-finite; descriptive labels such as `adult` do not satisfy the formal numeric covariate requirement;
- fewer than four biological replicates or three unique time points are present.

If each biological replicate contributes repeated aggregated observations within the single analysis stratum, the proposed random effect is `(1 | biological_replicate_id)`. If each unit contributes only one time point, no random intercept is proposed because its variance is not separately estimable from residual error; treat the biological replicate as the independent unit and use the fixed-effects branch below. The mixed-model emitter refuses to generate a random-intercept template when that random effect is absent.

## Repeated-unit mixed-effects handoff

```powershell
python scripts/prepare_mixed_model_input.py input.csv --output-table validation/mixed/aggregated.csv --output-json validation/mixed/manifest.json
python scripts/emit_mixed_model_templates.py validation/mixed/manifest.json --output-dir validation/mixed/templates
python validation/mixed/templates/fit_mixed_model_statsmodels.py validation/mixed/aggregated.csv validation/mixed/manifest.json validation/mixed/result.json
python scripts/validate_mixed_model_result.py validation/mixed/result.json --output validation/mixed/result-verdict.json
```

Record the exact model formula, random-effects structure, contrast/estimand, missing-data rule, optimizer/convergence diagnostics, residual QC, software versions and output hash. Run `scripts/check_mixed_model_runtime.py` first. If Python `statsmodels`, R `lme4`/`jsonlite` or MATLAB Statistics Toolbox is unavailable, the skill must report `blocked` and retain the prepared table/templates; it must not silently fall back to row-level or cell-level inference.

The Python template records convergence, fixed effects, cosinor amplitude/acrophase, a clearly labeled delta-method normal-approximation interval using the full cosine/sine covariance, residual summary and runtime versions. `scripts/validate_mixed_model_result.py` can mark the output `verified_mixed_model_result` only when these technical fields pass; that status is not biological causal verification.

## Independent-unit fixed-effects branch

When the manifest has `random_effects: []` because every biological replicate contributes one time point, run:

```powershell
python scripts/fit_fixed_effects_cosinor.py validation/mixed/aggregated.csv validation/mixed/manifest.json --output validation/mixed/fixed-effects-result.json
python scripts/validate_fixed_effects_result.py validation/mixed/fixed-effects-result.json --output validation/mixed/fixed-effects-verdict.json
```

This branch requires independent biological units, aggregates no lower-level rows, uses an explicit full-rank design, HC3-robust covariance and asymptotic-normal intervals, and records invariant covariates rather than silently treating them as estimable effects. It blocks if any biological replicate has repeated time points or if the design rank/residual degrees of freedom are invalid. Its `verified_fixed_effects_result` status is technical QC only and is not evidence that an ion channel causes a rhythm.

## Interpretation

The cosinor coefficients describe a conditional model for the specified biological unit and covariates. A significant fixed effect is not automatically evidence that an ion channel causes membrane-potential or behavioral rhythms; retain the causal-chain evidence labels and require independent perturbation, rescue and readout validation.
