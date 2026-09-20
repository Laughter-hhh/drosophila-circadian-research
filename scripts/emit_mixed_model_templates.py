#!/usr/bin/env python3
"""Emit reproducible R, Python and MATLAB mixed-model templates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PY_TEMPLATE = r'''#!/usr/bin/env python3
"""Fit a pre-specified random-intercept cosinor and emit QC diagnostics."""
import importlib.util
import json
import platform
import sys
from pathlib import Path

table_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path("nested_aggregated.csv")
manifest_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else table_path.with_name("nested_manifest.json")
result_path = Path(sys.argv[3]) if len(sys.argv) >= 4 else None
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("status") != "ready_for_mixed_model":
    print(json.dumps({"status": "blocked_mixed_model_input", "blocking_reasons": manifest.get("blocking_reasons", [])}, indent=2))
    raise SystemExit(2)
if importlib.util.find_spec("statsmodels") is None:
    print(json.dumps({"status": "blocked_mixed_model_runtime_unavailable", "required": "statsmodels"}, indent=2))
    raise SystemExit(2)

import numpy as np
import pandas as pd
import statsmodels
import statsmodels.formula.api as smf


def emit_result(payload, exit_code=0):
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    if result_path is not None:
        result_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(exit_code)


dat = pd.read_csv(table_path)
dat["cos24"] = np.cos(2 * np.pi * dat["time_hours"] / 24.0)
dat["sin24"] = np.sin(2 * np.pi * dat["time_hours"] / 24.0)
formula = "value ~ cos24 + sin24 + C(batch_id) + C(sex) + age_days + C(genotype) + temperature_C + C(lighting)"
try:
    fit = smf.mixedlm(formula, dat, groups=dat["biological_replicate_id"], re_formula="1").fit(reml=True)
except Exception as exc:
    emit_result({"status": "mixed_model_fit_failed", "error_type": type(exc).__name__, "error": str(exc), "formula": formula, "random_effect": "1 | biological_replicate_id"}, 3)

print(fit.summary())
fixed_effects = {str(key): float(value) for key, value in fit.fe_params.items()}
beta_cos = fixed_effects.get("cos24")
beta_sin = fixed_effects.get("sin24")
if beta_cos is not None and beta_sin is not None:
    amplitude = float(np.hypot(beta_cos, beta_sin))
    acrophase_hours = float((np.arctan2(-beta_sin, beta_cos) % (2 * np.pi)) * 24.0 / (2 * np.pi))
else:
    amplitude = None
    acrophase_hours = None

# Use the full fixed-effect covariance, including cos24/sin24 covariance.
amplitude_ci = None
if amplitude is not None:
    try:
        covariance = fit.cov_params()
        var_cos = float(covariance.loc["cos24", "cos24"])
        var_sin = float(covariance.loc["sin24", "sin24"])
        cov_cos_sin = float(covariance.loc["cos24", "sin24"])
        amplitude_var = (beta_cos * beta_cos * var_cos + beta_sin * beta_sin * var_sin + 2.0 * beta_cos * beta_sin * cov_cos_sin) / max(amplitude * amplitude, np.finfo(float).eps)
        if np.isfinite(amplitude_var) and amplitude_var >= 0:
            amplitude_se = float(np.sqrt(amplitude_var))
            amplitude_ci = [float(max(0.0, amplitude - 1.96 * amplitude_se)), float(amplitude + 1.96 * amplitude_se)]
    except (KeyError, TypeError, ValueError):
        amplitude_ci = None
residuals = np.asarray(fit.resid, dtype=float)
finite_residuals = residuals[np.isfinite(residuals)]
residual_diagnostics = {
    "n": int(residuals.size),
    "n_finite": int(finite_residuals.size),
    "mean": float(np.mean(finite_residuals)) if finite_residuals.size else None,
    "sd": float(np.std(finite_residuals, ddof=1)) if finite_residuals.size > 1 else None,
    "max_abs": float(np.max(np.abs(finite_residuals))) if finite_residuals.size else None,
}
converged = bool(getattr(fit, "converged", False))
n_biological_replicates = int(dat["biological_replicate_id"].nunique())
payload = {
    "status": "executed_mixed_model",
    "formula": formula,
    "random_effect": "1 | biological_replicate_id",
    "manifest": str(manifest_path),
    "n_rows": int(len(dat)),
    "n_biological_replicates": n_biological_replicates,
    "converged": converged,
    "fixed_effects": fixed_effects,
    "cosinor": {"beta_cos24": beta_cos, "beta_sin24": beta_sin, "amplitude": amplitude, "acrophase_hours": acrophase_hours, "amplitude_normal_approx_95_ci": amplitude_ci},
    "residual_diagnostics": residual_diagnostics,
    "technical_qc": {"converged": converged, "all_residuals_finite": bool(residuals.size == finite_residuals.size), "at_least_four_biological_replicates": bool(n_biological_replicates >= 4)},
    "runtime_versions": {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__, "statsmodels": statsmodels.__version__},
}
emit_result(payload)
'''


R_TEMPLATE = r'''#!/usr/bin/env Rscript
args <- commandArgs(trailingOnly = TRUE)
table_path <- if (length(args) >= 1) args[[1]] else "nested_aggregated.csv"
manifest_path <- if (length(args) >= 2) args[[2]] else "nested_manifest.json"
if (!requireNamespace("jsonlite", quietly=TRUE) || !requireNamespace("lme4", quietly=TRUE)) stop("BLOCKED: require jsonlite and lme4")
manifest <- jsonlite::fromJSON(manifest_path)
if (!identical(manifest$status, "ready_for_mixed_model")) stop("BLOCKED: mixed-model manifest is not ready")
dat <- read.csv(table_path, check.names = FALSE)
dat$cos24 <- cos(2*pi*dat$time_hours/24)
dat$sin24 <- sin(2*pi*dat$time_hours/24)
fit <- lme4::lmer(value ~ cos24 + sin24 + factor(batch_id) + factor(sex) + age_days + factor(genotype) + temperature_C + factor(lighting) + (1|biological_replicate_id), data=dat, REML=TRUE)
print(summary(fit))
print(lme4::isSingular(fit, tol=1e-4))
'''


MATLAB_TEMPLATE = r'''% Fit the pre-specified random-intercept cosinor with MATLAB Statistics Toolbox.
% Usage: fit_mixed_model('nested_aggregated.csv','nested_manifest.json')
function fit = fit_mixed_model(table_path, manifest_path)
if nargin < 1, table_path = 'nested_aggregated.csv'; end
if nargin < 2, manifest_path = 'nested_manifest.json'; end
manifest = jsondecode(fileread(manifest_path));
if ~strcmp(manifest.status,'ready_for_mixed_model')
    error('BLOCKED: mixed-model manifest is not ready');
end
if exist('fitlme','file') ~= 2
    error('BLOCKED: MATLAB Statistics and Machine Learning Toolbox fitlme is unavailable');
end
dat = readtable(table_path);
dat.cos24 = cos(2*pi*dat.time_hours/24);
dat.sin24 = sin(2*pi*dat.time_hours/24);
dat.batch_id = categorical(dat.batch_id);
dat.sex = categorical(dat.sex);
dat.genotype = categorical(dat.genotype);
dat.lighting = categorical(dat.lighting);
formula = 'value ~ 1 + cos24 + sin24 + batch_id + sex + age_days + genotype + temperature_C + lighting + (1|biological_replicate_id)';
fit = fitlme(dat, formula, 'FitMethod', 'REML');
disp(fit);
end
'''


def emit(manifest_path: Path, output_dir: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "ready_for_mixed_model":
        raise ValueError(f"manifest is not ready_for_mixed_model: {manifest.get('blocking_reasons')}")
    random_effects = manifest.get("model_specification", {}).get("random_effects", [])
    if random_effects != ["1 | biological_replicate_id"]:
        raise ValueError(
            "manifest does not contain an estimable biological_replicate_id random intercept; "
            "do not emit a mixed-model template for one-time-point biological units"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {"fit_mixed_model_statsmodels.py": PY_TEMPLATE, "fit_mixed_model.R": R_TEMPLATE, "fit_mixed_model.m": MATLAB_TEMPLATE}
    for name, content in files.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="\n")
    emitted = {
        "status": "templates_emitted",
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "files": [str(output_dir / name) for name in files],
        "runtime_requirement": "statsmodels (Python), lme4+jsonlite (R), or Statistics Toolbox (MATLAB); fit results are not generated by this emitter.",
        "python_result_argument": "Pass an optional third argument to write the Python fit JSON and validate it with validate_mixed_model_result.py.",
    }
    (output_dir / "template_manifest.json").write_text(json.dumps(emitted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return emitted


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        print(json.dumps(emit(args.manifest, args.output_dir), ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
