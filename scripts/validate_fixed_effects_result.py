#!/usr/bin/env python3
"""Validate technical QC and provenance fields from fixed-effects cosinor output."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _valid_metadata(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    digest = value.get("sha256")
    size = value.get("size_bytes")
    return isinstance(digest, str) and len(digest) == 64 and all(character in "0123456789abcdefABCDEF" for character in digest) and isinstance(size, int) and size >= 0


def validate(result: dict[str, object]) -> dict[str, object]:
    reasons: list[str] = []
    if result.get("status") != "executed_fixed_effects":
        reasons.append("result_status_is_not_executed_fixed_effects")
    if result.get("random_effect") is not None:
        reasons.append("random_effect_present_in_independent_unit_branch")
    provenance = result.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("hash_match") is not True:
        reasons.append("provenance_hash_match_missing_or_false")
    else:
        table_meta = provenance.get("table_file_metadata")
        manifest_meta = provenance.get("manifest_output_table_metadata")
        if not _valid_metadata(table_meta) or not _valid_metadata(manifest_meta):
            reasons.append("provenance_file_metadata_incomplete")
        elif table_meta["sha256"] != manifest_meta["sha256"] or table_meta["size_bytes"] != manifest_meta["size_bytes"]:
            reasons.append("provenance_table_manifest_metadata_mismatch")
    for key, minimum in [("n_rows", 1), ("n_biological_replicates", 4), ("n_unique_time_points", 3)]:
        value = result.get(key)
        if not isinstance(value, int) or value < minimum:
            reasons.append(f"{key}_below_minimum")
    if not isinstance(result.get("rank"), int) or not isinstance(result.get("df_resid"), int) or result["df_resid"] <= 0:
        reasons.append("invalid_design_rank_or_residual_df")
    technical = result.get("technical_qc")
    if not isinstance(technical, dict) or technical.get("full_rank") is not True or technical.get("positive_residual_df") is not True or technical.get("all_residuals_finite") is not True:
        reasons.append("technical_qc_failed")
    cosinor = result.get("cosinor")
    if not isinstance(cosinor, dict):
        reasons.append("cosinor_diagnostics_missing")
    else:
        for key in ["beta_cos24", "beta_sin24", "amplitude", "cov_cos24_sin24_hc3"]:
            if not finite(cosinor.get(key)):
                reasons.append(f"cosinor_{key}_missing_or_nonfinite")
        amplitude = cosinor.get("amplitude")
        phase = cosinor.get("acrophase_hours")
        # A zero-amplitude signal has no identifiable phase; null is the correct value.
        if not (phase is None and finite(amplitude) and float(amplitude) <= 1e-10) and not finite(phase):
            reasons.append("cosinor_acrophase_missing_or_nonfinite")
        ci = cosinor.get("amplitude_normal_approx_95_ci")
        if ci is not None and (not isinstance(ci, list) or len(ci) != 2 or not all(finite(value) for value in ci) or float(ci[0]) > float(ci[1])):
            reasons.append("amplitude_interval_invalid")
    residuals = result.get("residual_diagnostics")
    if not isinstance(residuals, dict):
        reasons.append("residual_diagnostics_missing")
    else:
        if residuals.get("n") != residuals.get("n_finite"):
            reasons.append("nonfinite_residuals_present")
        for key in ["mean", "sd", "max_abs"]:
            if not finite(residuals.get(key)):
                reasons.append(f"residual_{key}_missing_or_nonfinite")
    versions = result.get("runtime_versions")
    if not isinstance(versions, dict) or not all(versions.get(key) for key in ["python", "numpy", "pandas"]):
        reasons.append("runtime_versions_incomplete")
    return {
        "status": "verified_fixed_effects_result" if not reasons else "blocked_fixed_effects_result",
        "blocking_reasons": reasons,
        "interpretation": "Technical QC and file-identity checks only; HC3 and normal-approximation uncertainty do not replace estimand review, independent replication or biological interpretation.",
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
    return 0 if verdict["status"] == "verified_fixed_effects_result" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
