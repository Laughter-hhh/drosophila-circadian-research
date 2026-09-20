#!/usr/bin/env python3
"""Validate the technical QC fields emitted by the Python mixed-model template.

This is a result-quality gate, not a substitute for biological interpretation,
independent replication or review of the estimand and model formula.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def validate(result: dict[str, object]) -> dict[str, object]:
    reasons: list[str] = []
    if result.get("status") != "executed_mixed_model":
        reasons.append("result_status_is_not_executed_mixed_model")
    if not result.get("formula"):
        reasons.append("model_formula_missing")
    if result.get("random_effect") != "1 | biological_replicate_id":
        reasons.append("random_effect_not_recorded_as_expected")
    if not isinstance(result.get("n_rows"), int) or result["n_rows"] <= 0:
        reasons.append("n_rows_missing_or_nonpositive")
    if not isinstance(result.get("n_biological_replicates"), int) or result["n_biological_replicates"] < 4:
        reasons.append("fewer_than_four_biological_replicates")
    if result.get("converged") is not True:
        reasons.append("model_not_converged")

    cosinor = result.get("cosinor")
    if not isinstance(cosinor, dict):
        reasons.append("cosinor_diagnostics_missing")
    else:
        for key in ["beta_cos24", "beta_sin24", "amplitude", "acrophase_hours"]:
            if not _finite(cosinor.get(key)):
                reasons.append(f"cosinor_{key}_missing_or_nonfinite")
        ci = cosinor.get("amplitude_normal_approx_95_ci")
        if not isinstance(ci, list) or len(ci) != 2 or not all(_finite(value) for value in ci) or float(ci[0]) > float(ci[1]):
            reasons.append("amplitude_interval_missing_or_invalid")

    residuals = result.get("residual_diagnostics")
    if not isinstance(residuals, dict):
        reasons.append("residual_diagnostics_missing")
    else:
        if residuals.get("n") != residuals.get("n_finite"):
            reasons.append("nonfinite_residuals_present")
        for key in ["mean", "sd", "max_abs"]:
            if not _finite(residuals.get(key)):
                reasons.append(f"residual_{key}_missing_or_nonfinite")

    technical_qc = result.get("technical_qc")
    if not isinstance(technical_qc, dict) or technical_qc.get("all_residuals_finite") is not True:
        reasons.append("technical_qc_failed")
    versions = result.get("runtime_versions")
    if not isinstance(versions, dict) or not all(versions.get(key) for key in ["python", "numpy", "pandas", "statsmodels"]):
        reasons.append("runtime_versions_incomplete")

    return {
        "status": "verified_mixed_model_result" if not reasons else "blocked_mixed_model_result",
        "blocking_reasons": reasons,
        "interpretation": "Technical QC only; inspect model formula, estimand, residual structure and independent replication before biological claims.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = json.loads(args.result.read_text(encoding="utf-8"))
        verdict = validate(result)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(verdict, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if verdict["status"] == "verified_mixed_model_result" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
