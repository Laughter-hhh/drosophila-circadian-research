#!/usr/bin/env python3
"""Validate staged experiment plans for channel, rhythm and external-input studies."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    from scripts.validate_power_basis import validate_file as validate_power_file
except ModuleNotFoundError:  # direct execution as ``python scripts/validate_experiment_plan.py``
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.validate_power_basis import validate_file as validate_power_file


REQUIRED = {
    "plan_id", "candidate", "module", "hypothesis", "causal_link", "target_neuron", "species",
    "stage", "perturbation", "time_basis", "lighting_condition", "sex_age_temperature",
    "experimental_unit", "biological_unit_definition", "minimum_n", "sample_size_basis",
    "primary_readout", "secondary_readouts", "controls", "qc_metrics", "analysis_plan",
    "expected_result_matrix", "alternative_explanations", "go_no_go_rule",
    "developmental_boundary", "reagent_identity_status", "stock_identity_status", "source_status",
}
STAGES = {"information_gain_pilot", "conditional_pilot", "formal_experiment"}
MODULES = {"channel_screen", "channel_rhythm", "external_input", "behavior_link", "other"}
PERTURBATIONS = {
    "observation_only", "pharmacology", "RNAi", "optogenetics",
    "temperature_activation", "voltage_clamp", "current_clamp", "other",
}
IDENTITY = {"verified", "pending_audit", "not_applicable", "unknown"}
SOURCE_STATUS = {"planning", "executed", "verified", "blocked"}
DEVELOPMENT = {"adult_restricted", "developmental_aware", "not_applicable", "unknown"}
UNITS = {"fly", "brain", "cell", "culture", "library", "image", "animal"}
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED", "NOT_AVAILABLE", "NONE"}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _tokens(value: str | None) -> set[str]:
    return {
        token.strip().lower()
        for token in re.split(r"[;,|]", value or "")
        if token.strip()
    }


def _contains_any(tokens: set[str], *choices: str) -> bool:
    return any(choice.lower() in tokens for choice in choices)


def _positive_int(value: str | None) -> bool:
    try:
        return int((value or "").strip()) > 0
    except (TypeError, ValueError):
        return False


def _add_formal_or_warning(
    issues: list[dict[str, object]],
    warnings: list[dict[str, object]],
    stage: str,
    record: dict[str, object],
) -> None:
    (issues if stage == "formal_experiment" else warnings).append(record)


def validate(path: Path, power_report_path: Path | None = None) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {
                "status": "invalid_experiment_plan",
                "formal_status": "blocked_by_validation_issues",
                "n_rows": 0,
                "issues": [{"type": "missing_columns", "columns": missing}],
                "warnings": [],
            }
        rows = list(reader)
    formal_plan_ids = {
        (row.get("plan_id") or "").strip()
        for row in rows
        if (row.get("stage") or "").strip().lower() == "formal_experiment"
    }
    power_validation: dict[str, object] | None = None
    power_by_plan: dict[str, dict[str, object]] = {}
    if formal_plan_ids:
        if power_report_path is None:
            power_validation = {"status": "missing_power_basis_report", "issues": [{"type": "formal_requires_power_basis_report"}]}
        else:
            try:
                power_validation = validate_power_file(power_report_path)
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                power_validation = {"status": "invalid_power_basis_report", "issues": [{"type": "power_report_read_error", "detail": str(exc)}]}
            for power_record in power_validation.get("records", []) if isinstance(power_validation, dict) else []:
                if isinstance(power_record, dict) and power_record.get("plan_id"):
                    power_by_plan[str(power_record["plan_id"])] = power_record
    seen: set[str] = set()
    formal_rows = 0
    formal_passes = 0
    for line_number, row in enumerate(rows, start=2):
        row_issue_count = len(issues)
        plan_id = (row.get("plan_id") or "").strip()
        if not plan_id:
            issues.append({"line": line_number, "type": "missing_plan_id"})
            continue
        if plan_id in seen:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "duplicate_plan_id"})
        seen.add(plan_id)
        for field in (
            "candidate", "hypothesis", "causal_link", "target_neuron", "species",
            "time_basis", "lighting_condition", "sex_age_temperature",
            "experimental_unit", "biological_unit_definition", "sample_size_basis",
            "primary_readout", "controls", "qc_metrics", "analysis_plan",
            "expected_result_matrix", "alternative_explanations", "go_no_go_rule",
        ):
            if not _present(row.get(field)):
                issues.append({"line": line_number, "plan_id": plan_id, "type": f"missing_{field}"})
        stage = (row.get("stage") or "").strip().lower()
        module = (row.get("module") or "").strip().lower()
        perturbation = (row.get("perturbation") or "").strip()
        if stage not in STAGES:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_stage", "value": row.get("stage", "")})
        if module not in MODULES:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_module", "value": row.get("module", "")})
        if perturbation not in PERTURBATIONS:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_perturbation", "value": row.get("perturbation", "")})
        time_basis = (row.get("time_basis") or "").upper()
        if not re.search(r"\b(?:ZT|CT)(?:\s*[+-]?\d+(?:\.\d+)?)?\b", time_basis):
            issues.append({"line": line_number, "plan_id": plan_id, "type": "time_basis_must_declare_ZT_or_CT"})
        if not re.search(r"\b(?:LD|DD)\b", (row.get("lighting_condition") or "").upper()):
            issues.append({"line": line_number, "plan_id": plan_id, "type": "lighting_condition_must_declare_LD_or_DD"})
        experimental_unit = (row.get("experimental_unit") or "").strip().lower()
        if experimental_unit not in UNITS:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_experimental_unit", "value": row.get("experimental_unit", "")})
        if not _positive_int(row.get("minimum_n")):
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_minimum_n"})
        reagent_status = (row.get("reagent_identity_status") or "").strip().lower()
        stock_status = (row.get("stock_identity_status") or "").strip().lower()
        if reagent_status not in IDENTITY:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_reagent_identity_status", "value": row.get("reagent_identity_status", "")})
        if stock_status not in IDENTITY:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_stock_identity_status", "value": row.get("stock_identity_status", "")})
        developmental = (row.get("developmental_boundary") or "").strip().lower()
        if developmental not in DEVELOPMENT:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_developmental_boundary", "value": row.get("developmental_boundary", "")})
        source_status = (row.get("source_status") or "").strip().lower()
        if source_status not in SOURCE_STATUS:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_source_status", "value": row.get("source_status", "")})
        controls = _tokens(row.get("controls"))
        qc = _tokens(row.get("qc_metrics"))
        if module == "external_input" and perturbation == "optogenetics":
            if not _contains_any(controls, "light_control", "light-only", "sham_light"):
                _add_formal_or_warning(issues, warnings, stage, {"line": line_number, "plan_id": plan_id, "type": "external_input_requires_light_control"})
            if not _contains_any(controls, "retinal", "retinal_control", "no_retinal"):
                _add_formal_or_warning(issues, warnings, stage, {"line": line_number, "plan_id": plan_id, "type": "optogenetics_requires_retinal_control"})
        if module == "external_input" and perturbation == "temperature_activation":
            if not _contains_any(controls, "temperature_control", "sham_temperature", "time_matched_temperature"):
                _add_formal_or_warning(issues, warnings, stage, {"line": line_number, "plan_id": plan_id, "type": "thermogenetics_requires_temperature_control"})
        if perturbation in {"pharmacology", "RNAi"}:
            if not _contains_any(controls, "vehicle", "vehicle_control", "driver_only", "effector_only", "background"):
                _add_formal_or_warning(issues, warnings, stage, {"line": line_number, "plan_id": plan_id, "type": "perturbation_requires_identity_controls"})
        if module in {"channel_screen", "channel_rhythm"} and not _contains_any(qc, "access", "seal", "cell_health", "roi"):
            _add_formal_or_warning(issues, warnings, stage, {"line": line_number, "plan_id": plan_id, "type": "channel_module_requires_assay_qc"})
        if stage == "formal_experiment":
            if power_report_path is None:
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_power_basis_report"})
            elif not isinstance(power_validation, dict) or power_validation.get("status") != "verified_power_basis_report":
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_valid_power_basis_report"})
            else:
                power_record = power_by_plan.get(plan_id)
                if power_record is None:
                    issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_power_record_missing"})
                else:
                    if not power_record.get("formal_eligible", False):
                        issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_power_basis_not_eligible"})
                    power_unit = str(power_record.get("independent_biological_unit", "")).strip().lower()
                    if power_unit and power_unit != experimental_unit:
                        issues.append({"line": line_number, "plan_id": plan_id, "type": "power_unit_mismatch", "plan_unit": experimental_unit, "power_unit": power_unit})
                    declared_total = power_record.get("declared_minimum_n_total")
                    try:
                        plan_n = int(str(row.get("minimum_n") or "").strip())
                    except ValueError:
                        plan_n = 0
                    if isinstance(declared_total, int) and plan_n < declared_total:
                        issues.append({"line": line_number, "plan_id": plan_id, "type": "plan_minimum_n_below_power_basis", "plan_minimum_n": plan_n, "power_minimum_n_total": declared_total})
                    analysis_text = str(row.get("analysis_plan") or "").strip().lower()
                    complex_tokens = ("mixed-effect", "mixed effect", "mixed model", "cosinor", "repeated", "nested", "cluster")
                    calculation_method = str((power_record.get("calculation") or {}).get("method", "")).strip().lower()
                    if calculation_method == "normal_approximation_two_group_equal_n" and any(token in analysis_text for token in complex_tokens):
                        issues.append({"line": line_number, "plan_id": plan_id, "type": "power_design_mismatch_complex_analysis", "calculation_method": calculation_method})
        if stage == "formal_experiment":
            formal_rows += 1
            if reagent_status not in {"verified", "not_applicable"}:
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_verified_reagent_or_na"})
            if stock_status not in {"verified", "not_applicable"}:
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_verified_stock_or_na"})
            if developmental == "unknown":
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_developmental_boundary"})
            if source_status == "blocked":
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_source_status_blocked"})
            if len(issues) == row_issue_count:
                formal_passes += 1
        elif source_status == "blocked":
            warnings.append({"line": line_number, "plan_id": plan_id, "type": "plan_source_status_blocked"})
    status = "verified_experiment_plan" if rows and not issues else "invalid_experiment_plan"
    if issues:
        formal_status = "blocked_by_validation_issues"
    elif formal_rows == 0:
        formal_status = "conditional_pilot_only"
    elif formal_passes == formal_rows:
        formal_status = "formal_gate_passed_external_checks_pending"
    else:
        formal_status = "formal_gate_blocked"
    return {
        "status": status,
        "formal_status": formal_status,
        "n_rows": len(rows),
        "n_plans": len(seen),
        "formal_rows": formal_rows,
        "formal_passes": formal_passes,
        "issues": issues,
        "warnings": warnings,
        "power_gate": power_validation,
        "inference_warning": "This validator checks experimental-plan completeness, stage gates, control declarations and (when supplied) a transparent power-basis report; it does not establish biological causality, assay performance, reagent selectivity or achieved power.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--power-report", type=Path, help="JSON power-basis report required for formal_experiment rows")
    args = parser.parse_args(argv[1:])
    try:
        result = validate(args.input, args.power_report)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_experiment_plan" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))








