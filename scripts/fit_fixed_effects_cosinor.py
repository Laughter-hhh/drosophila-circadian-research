#!/usr/bin/env python3
"""Fit a fixed-effects cosinor for independent biological units.

This branch is intentionally limited to designs in which each biological
replicate contributes one time point. It uses NumPy/Pandas only and reports
HC3-robust, asymptotic-normal uncertainty; it is not a substitute for a
repeated-measures mixed-effects model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from statistics import NormalDist
from pathlib import Path


REQUIRED = ["biological_replicate_id", "time_hours", "value"]
CATEGORICAL = ["batch_id", "sex", "genotype", "lighting"]
NUMERIC = ["age_days", "temperature_C"]


def _json_number(value: float | None) -> float | None:
    return float(value) if value is not None and math.isfinite(float(value)) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_metadata(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size_bytes": int(stat.st_size), "sha256": _sha256(path)}


def _normal_p(z: float) -> float | None:
    if not math.isfinite(z):
        return None
    return float(2.0 * (1.0 - NormalDist().cdf(abs(z))))


def _design(data):
    import numpy as np
    import pandas as pd

    columns = ["Intercept", "cos24", "sin24"]
    vectors = [
        np.ones(len(data), dtype=float),
        np.cos(2.0 * np.pi * data["time_hours"].to_numpy(dtype=float) / 24.0),
        np.sin(2.0 * np.pi * data["time_hours"].to_numpy(dtype=float) / 24.0),
    ]
    metadata = {"invariant_covariates": [], "numeric_centers": {}, "categorical_reference_levels": {}}
    for name in CATEGORICAL:
        if name not in data.columns:
            continue
        values = data[name].fillna("").astype(str)
        levels = sorted(values.unique().tolist())
        if len(levels) <= 1:
            metadata["invariant_covariates"].append(name)
            continue
        metadata["categorical_reference_levels"][name] = levels[0]
        for level in levels[1:]:
            columns.append(f"C({name})[T.{level}]")
            vectors.append((values == level).astype(float).to_numpy())
    for name in NUMERIC:
        if name not in data.columns:
            continue
        values = pd.to_numeric(data[name], errors="coerce")
        if values.isna().any():
            raise ValueError(f"numeric covariate contains missing/non-numeric values: {name}")
        if values.nunique() <= 1:
            metadata["invariant_covariates"].append(name)
            continue
        center = float(values.mean())
        metadata["numeric_centers"][name] = center
        columns.append(name)
        vectors.append((values - center).to_numpy(dtype=float))
    return np.column_stack(vectors), columns, metadata


def fit(table_path: Path, manifest_path: Path, result_path: Path | None = None) -> dict[str, object]:
    import numpy as np
    import pandas as pd

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "ready_for_mixed_model":
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": manifest.get("blocking_reasons", [])}
    random_effects = manifest.get("model_specification", {}).get("random_effects", [])
    if random_effects:
        return {"status": "blocked_fixed_effects_wrong_design", "blocking_reasons": ["manifest_has_estimable_random_effect; use mixed-model workflow"]}
    try:
        table_metadata = _file_metadata(table_path)
    except OSError as exc:
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": [f"table_metadata_unavailable:{exc}"]}
    expected_metadata = manifest.get("output_table_metadata")
    if not isinstance(expected_metadata, dict) or not expected_metadata.get("sha256"):
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": ["manifest_missing_output_table_metadata"], "table_file_metadata": table_metadata}
    if expected_metadata.get("sha256") != table_metadata["sha256"] or expected_metadata.get("size_bytes") != table_metadata["size_bytes"]:
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": ["manifest_output_table_hash_mismatch"], "table_file_metadata": table_metadata, "manifest_output_table_metadata": expected_metadata}
    data = pd.read_csv(table_path)
    missing = [column for column in REQUIRED if column not in data.columns]
    if missing:
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": [f"missing_required_columns:{','.join(missing)}"]}
    if data[REQUIRED].isna().any().any():
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": ["required_values_missing"]}
    counts = data.groupby("biological_replicate_id")["time_hours"].nunique()
    if int((counts > 1).sum()) != 0:
        return {"status": "blocked_fixed_effects_wrong_design", "blocking_reasons": ["biological_replicates_have_repeated_time_points; use mixed-model workflow"]}
    keys = data[["biological_replicate_id", "time_hours"]]
    if keys.duplicated().any():
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": ["duplicate_biological_unit_time_rows"]}
    try:
        y = pd.to_numeric(data["value"], errors="raise").to_numpy(dtype=float)
        X, columns, design_metadata = _design(data)
    except (TypeError, ValueError) as exc:
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": [str(exc)]}
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        return {"status": "blocked_fixed_effects_input", "blocking_reasons": ["nonfinite_design_or_outcome"]}
    n_rows, n_columns = X.shape
    rank = int(np.linalg.matrix_rank(X))
    df_resid = n_rows - rank
    if df_resid <= 0:
        return {"status": "blocked_fixed_effects_design_rank", "blocking_reasons": ["nonpositive_residual_degrees_of_freedom"], "n_rows": n_rows, "rank": rank}
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    residuals = y - X @ beta
    leverage = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    denominator = np.maximum(1.0 - leverage, np.finfo(float).eps)
    meat = X.T @ ((residuals * residuals / (denominator * denominator))[:, None] * X)
    covariance = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    coefficients = {}
    for index, name in enumerate(columns):
        z = float(beta[index] / se[index]) if se[index] > 0 else float("nan")
        coefficients[name] = {
            "estimate": _json_number(beta[index]),
            "se_hc3": _json_number(se[index]),
            "normal_approx_95_ci": [_json_number(beta[index] - 1.96 * se[index]), _json_number(beta[index] + 1.96 * se[index])],
            "z": _json_number(z),
            "p_normal_approx": _normal_p(z),
        }
    cos_index, sin_index = columns.index("cos24"), columns.index("sin24")
    beta_cos, beta_sin = float(beta[cos_index]), float(beta[sin_index])
    amplitude = float(np.hypot(beta_cos, beta_sin))
    amplitude_epsilon = 1e-12 * max(1.0, float(np.max(np.abs(y))))
    acrophase = None if amplitude <= amplitude_epsilon else float((np.arctan2(-beta_sin, beta_cos) % (2.0 * np.pi)) * 24.0 / (2.0 * np.pi))
    var_cos = float(covariance[cos_index, cos_index])
    var_sin = float(covariance[sin_index, sin_index])
    cov_cos_sin = float(covariance[cos_index, sin_index])
    amplitude_var = (beta_cos * beta_cos * var_cos + beta_sin * beta_sin * var_sin + 2.0 * beta_cos * beta_sin * cov_cos_sin) / max(amplitude * amplitude, np.finfo(float).eps)
    amplitude_ci = None
    if np.isfinite(amplitude_var) and amplitude_var >= 0:
        amplitude_se = float(np.sqrt(amplitude_var))
        amplitude_ci = [max(0.0, amplitude - 1.96 * amplitude_se), amplitude + 1.96 * amplitude_se]
    result = {
        "status": "executed_fixed_effects",
        "model": "fixed-effects cosinor with HC3-robust covariance",
        "formula": "value ~ cos24 + sin24 + measured formal covariates with non-invariant levels",
        "random_effect": None,
        "manifest": str(manifest_path),
        "provenance": {"table_file_metadata": table_metadata, "manifest_output_table_metadata": expected_metadata, "hash_match": True},
        "n_rows": int(n_rows),
        "n_biological_replicates": int(data["biological_replicate_id"].nunique()),
        "n_unique_time_points": int(data["time_hours"].nunique()),
        "n_repeated_biological_replicates": 0,
        "rank": rank,
        "df_resid": int(df_resid),
        "design_metadata": design_metadata,
        "coefficients": coefficients,
        "cosinor": {"beta_cos24": _json_number(beta_cos), "beta_sin24": _json_number(beta_sin), "amplitude": _json_number(amplitude), "acrophase_hours": _json_number(acrophase), "amplitude_normal_approx_95_ci": [_json_number(value) for value in amplitude_ci] if amplitude_ci else None, "cov_cos24_sin24_hc3": _json_number(cov_cos_sin)},
        "residual_diagnostics": {"n": int(n_rows), "n_finite": int(np.isfinite(residuals).sum()), "mean": _json_number(float(np.mean(residuals))), "sd": _json_number(float(np.std(residuals, ddof=1))), "max_abs": _json_number(float(np.max(np.abs(residuals))))},
        "technical_qc": {"full_rank": bool(rank == n_columns), "positive_residual_df": bool(df_resid > 0), "all_residuals_finite": bool(np.isfinite(residuals).all()), "max_leverage": _json_number(float(np.max(leverage)))},
        "runtime_versions": {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
        "uncertainty_note": "HC3 covariance and normal-approximation intervals; review estimand and small-sample limitations before formal claims.",
    }
    if result_path is not None:
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = fit(args.table, args.manifest, args.output)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["status"] == "executed_fixed_effects" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
