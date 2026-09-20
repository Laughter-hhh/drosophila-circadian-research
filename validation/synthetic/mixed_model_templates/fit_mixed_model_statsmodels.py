#!/usr/bin/env python3
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
