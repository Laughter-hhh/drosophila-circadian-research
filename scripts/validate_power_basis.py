#!/usr/bin/env python3
"""Validate a transparent, biological-unit-aware power/sample-size basis report.

This is a planning/QC gate, not a substitute for a design-specific simulation.
The built-in calculation is a conservative normal approximation for two equal-size
groups and Cohen's d. Nested, cosinor and repeated-measures designs must provide
an externally reviewed or simulation-based basis instead of being silently reduced
to an independent two-group calculation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist
from typing import Any


REQUIRED_RECORD_FIELDS = {
    "plan_id", "design_type", "independent_biological_unit", "effect_size_metric",
    "effect_size", "alpha", "target_power", "comparison_count",
    "multiplicity_method", "cluster_structure", "basis_status", "basis_source",
    "calculation_method", "n_per_group", "minimum_n_total",
}
UNITS = {"fly", "brain", "cell", "culture", "library", "image", "animal"}
DESIGNS = {"two_group_mean_equal_n", "nested_or_cosinor_external", "other_external"}
METRICS = {"cohens_d", "phase_difference_hours", "amplitude_difference", "absolute_difference", "other"}
BASIS_STATUS = {"pilot_estimate", "literature_estimate", "simulation", "feasibility_only", "not_available"}
MULTIPLICITY = {"none", "bonferroni", "holm", "fdr", "other"}
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED", "NOT_AVAILABLE", "NONE"}


def _present(value: Any) -> bool:
    return str(value if value is not None else "").strip().upper() not in MISSING


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_int(value: Any) -> bool:
    try:
        return int(str(value).strip()) > 0 and float(str(value).strip()) == int(str(value).strip())
    except (TypeError, ValueError):
        return False


def _expected_n_per_group(effect_size: float, alpha: float, target_power: float, comparison_count: int, multiplicity: str) -> int:
    if multiplicity in {"bonferroni", "holm"}:
        alpha = alpha / comparison_count
    elif multiplicity == "none" and comparison_count != 1:
        raise ValueError("multiplicity_method=none requires comparison_count=1")
    if effect_size <= 0 or not (0 < alpha < 1) or not (0 < target_power < 1):
        raise ValueError("effect_size, alpha and target_power must be in valid ranges")
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(target_power)
    return int(math.ceil(2 * (z_alpha + z_power) ** 2 / effect_size**2))


def _record_result(record: dict[str, Any], line: int) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    plan_id = str(record.get("plan_id", "")).strip()
    if not plan_id:
        issues.append({"line": line, "type": "missing_plan_id"})
    missing = sorted(REQUIRED_RECORD_FIELDS - set(record))
    if missing:
        issues.append({"line": line, "plan_id": plan_id, "type": "missing_fields", "fields": missing})
        return {"plan_id": plan_id, "issues": issues, "warnings": warnings}

    design = str(record.get("design_type", "")).strip().lower()
    unit = str(record.get("independent_biological_unit", "")).strip().lower()
    metric = str(record.get("effect_size_metric", "")).strip().lower()
    basis = str(record.get("basis_status", "")).strip().lower()
    multiplicity = str(record.get("multiplicity_method", "")).strip().lower()
    method = str(record.get("calculation_method", "")).strip().lower()
    if design not in DESIGNS:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_design_type", "value": design})
    if unit not in UNITS:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_independent_biological_unit", "value": unit})
    if metric not in METRICS:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_effect_size_metric", "value": metric})
    if basis not in BASIS_STATUS:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_basis_status", "value": basis})
    if multiplicity not in MULTIPLICITY:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_multiplicity_method", "value": multiplicity})
    if not _present(record.get("cluster_structure")):
        issues.append({"line": line, "plan_id": plan_id, "type": "missing_cluster_structure"})
    if not _present(record.get("basis_source")):
        issues.append({"line": line, "plan_id": plan_id, "type": "missing_basis_source"})
    alpha = _number(record.get("alpha"))
    target_power = _number(record.get("target_power"))
    effect = _number(record.get("effect_size"))
    if alpha is None or not 0 < alpha < 1:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_alpha"})
    if target_power is None or not 0.5 <= target_power < 1:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_target_power"})
    if effect is None or effect <= 0:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_effect_size"})
    comparison_count = record.get("comparison_count")
    try:
        comparisons = int(str(comparison_count).strip())
    except (TypeError, ValueError):
        comparisons = 0
    if comparisons <= 0:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_comparison_count"})
    if multiplicity == "none" and comparisons != 1:
        issues.append({"line": line, "plan_id": plan_id, "type": "multiplicity_none_requires_one_comparison"})
    declared_n = record.get("n_per_group")
    total_n = record.get("minimum_n_total")
    if not _positive_int(declared_n):
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_n_per_group"})
    if not _positive_int(total_n):
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_minimum_n_total"})

    low = _number(record.get("effect_size_low")) if _present(record.get("effect_size_low")) else effect
    high = _number(record.get("effect_size_high")) if _present(record.get("effect_size_high")) else effect
    if low is None or high is None or low <= 0 or high <= 0 or low > high:
        issues.append({"line": line, "plan_id": plan_id, "type": "invalid_effect_size_sensitivity_range"})
    elif basis in {"pilot_estimate", "literature_estimate", "simulation"} and (low == high == effect):
        warnings.append({"line": line, "plan_id": plan_id, "type": "effect_size_sensitivity_range_is_degenerate"})
    elif basis in {"pilot_estimate", "literature_estimate", "simulation"} and low > effect:
        issues.append({"line": line, "plan_id": plan_id, "type": "effect_size_low_exceeds_point_estimate"})
    elif basis in {"pilot_estimate", "literature_estimate", "simulation"} and high < effect:
        issues.append({"line": line, "plan_id": plan_id, "type": "effect_size_high_below_point_estimate"})

    calculation: dict[str, Any] = {}
    if design == "two_group_mean_equal_n":
        if metric != "cohens_d":
            issues.append({"line": line, "plan_id": plan_id, "type": "two_group_normal_approx_requires_cohens_d"})
        if method != "normal_approximation_two_group_equal_n":
            issues.append({"line": line, "plan_id": plan_id, "type": "unsupported_two_group_calculation_method"})
        if not issues and alpha is not None and target_power is not None and effect is not None and low is not None and high is not None:
            try:
                expected_point = _expected_n_per_group(effect, alpha, target_power, comparisons, multiplicity)
                expected_low = _expected_n_per_group(low, alpha, target_power, comparisons, multiplicity)
                expected_high = _expected_n_per_group(high, alpha, target_power, comparisons, multiplicity)
                calculation = {
                    "method": "normal_approximation_two_group_equal_n",
                    "expected_n_per_group_at_point": expected_point,
                    "expected_n_per_group_at_low": expected_low,
                    "expected_n_per_group_at_high": expected_high,
                    "recommended_n_per_group_conservative": expected_low,
                }
                declared = int(str(declared_n).strip())
                declared_total = int(str(total_n).strip())
                if declared < expected_low:
                    issues.append({"line": line, "plan_id": plan_id, "type": "n_per_group_below_conservative_sensitivity", "declared": declared, "required": expected_low})
                if declared_total < 2 * declared:
                    issues.append({"line": line, "plan_id": plan_id, "type": "minimum_n_total_below_two_group_total", "declared": declared_total, "required": 2 * declared})
            except ValueError as exc:
                issues.append({"line": line, "plan_id": plan_id, "type": "power_calculation_error", "detail": str(exc)})
    elif design in {"nested_or_cosinor_external", "other_external"}:
        if method not in {"external_simulation", "externally_reviewed_power", "design_specific_simulation"}:
            issues.append({"line": line, "plan_id": plan_id, "type": "complex_design_requires_external_or_simulation_method"})
        warnings.append({"line": line, "plan_id": plan_id, "type": "complex_design_not_reduced_to_independent_two_group_formula"})
        calculation = {"method": method, "computed": False}

    if basis in {"feasibility_only", "not_available"}:
        warnings.append({"line": line, "plan_id": plan_id, "type": "basis_not_formal_power_evidence", "basis_status": basis})
    formal_eligible = not issues and basis not in {"feasibility_only", "not_available"}
    return {
        "plan_id": plan_id,
        "line": line,
        "independent_biological_unit": unit,
        "basis_status": basis,
        "declared_n_per_group": int(str(declared_n).strip()) if _positive_int(declared_n) else None,
        "declared_minimum_n_total": int(str(total_n).strip()) if _positive_int(total_n) else None,
        "formal_eligible": formal_eligible,
        "issues": issues,
        "warnings": warnings,
        "calculation": calculation,
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return {"status": "invalid_power_basis_report", "issues": [{"type": "top_level_must_be_object"}], "warnings": []}
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        return {"status": "invalid_power_basis_report", "issues": [{"type": "records_must_be_nonempty_list"}], "warnings": []}
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for line, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            result = {"line": line, "plan_id": "", "issues": [{"line": line, "type": "record_must_be_object"}], "warnings": []}
        else:
            result = _record_result(record, line)
        plan_id = str(result.get("plan_id", ""))
        if plan_id and plan_id in seen:
            result.setdefault("issues", []).append({"line": line, "plan_id": plan_id, "type": "duplicate_plan_id"})
        if plan_id:
            seen.add(plan_id)
        issues.extend(result.get("issues", []))
        warnings.extend(result.get("warnings", []))
        results.append(result)
    status = "verified_power_basis_report" if not issues else "invalid_power_basis_report"
    return {
        "status": status,
        "report_id": payload.get("report_id", ""),
        "n_records": len(records),
        "n_formal_eligible": sum(1 for result in results if result.get("formal_eligible")),
        "records": results,
        "issues": issues,
        "warnings": warnings,
        "inference_warning": "This report verifies declared planning assumptions and transparent calculations only; it does not establish biological effect, assay quality, causal validity or achieved power.",
    }


def validate_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return validate_payload(payload)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate_file(args.input)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_power_basis_report" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


