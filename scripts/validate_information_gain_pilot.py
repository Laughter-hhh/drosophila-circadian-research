#!/usr/bin/env python3
"""Validate information-gain and pilot experiment plans without guessing reagents."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REQUIRED = {
    "plan_id", "candidate", "missing_fact", "causal_link", "target_neuron", "stage", "perturbation",
    "reagent_identifier", "reagent_identity_status", "stock_identifier", "stock_identity_status", "readout",
    "experimental_unit", "minimum_n", "sample_size_basis", "positive_control", "negative_control",
    "developmental_boundary", "go_no_go_rule", "source_status",
}
STAGES = {"information_gain_pilot", "conditional_pilot", "formal_experiment"}
PERTURBATIONS = {"observation_only", "RNAi", "pharmacology", "temperature_activation", "optogenetics", "other"}
IDENTITY = {"verified", "pending_audit", "not_applicable", "unknown"}
SOURCE_STATUS = {"planning", "executed", "verified", "blocked"}
DEVELOPMENT = {"adult_restricted", "developmental_aware", "not_applicable", "unknown"}
PENDING_HINTS = ("not_yet_selected", "pending", "to_be_audited")
MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT_AVAILABLE", "NOT_APPLICABLE", "."}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _required_present(field: str, value: str | None) -> bool:
    # `na` is a valid Drosophila gene symbol; do not treat it as missing.
    if field in {"candidate", "plan_id"}:
        return bool((value or "").strip())
    return _present(value)


def _identity_matches(status: str, identifier: str) -> bool:
    normalized = status.strip().lower()
    value = identifier.strip().lower()
    if normalized == "not_applicable":
        return value in {"not_applicable", "n/a", "na"}
    return bool(value)


def validate(path: Path) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {"status": "invalid_information_gain_pilot", "n_rows": 0, "issues": [{"type": "missing_columns", "columns": missing}]}
        rows = list(reader)
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        plan_id = (row.get("plan_id") or "").strip()
        if not plan_id:
            issues.append({"line": line_number, "type": "missing_plan_id"})
        elif plan_id in seen:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "duplicate_plan_id"})
        seen.add(plan_id)
        for field in ("candidate", "missing_fact", "causal_link", "target_neuron", "readout", "experimental_unit", "sample_size_basis", "positive_control", "negative_control", "go_no_go_rule"):
            if not _required_present(field, row.get(field)):
                issues.append({"line": line_number, "plan_id": plan_id, "type": f"missing_{field}"})
        stage = (row.get("stage") or "").strip()
        if stage not in STAGES:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_stage", "value": stage})
        perturbation = (row.get("perturbation") or "").strip()
        if perturbation not in PERTURBATIONS:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_perturbation", "value": perturbation})
        reagent_status = (row.get("reagent_identity_status") or "").strip()
        stock_status = (row.get("stock_identity_status") or "").strip()
        if reagent_status not in IDENTITY:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_reagent_identity_status", "value": reagent_status})
        if stock_status not in IDENTITY:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_stock_identity_status", "value": stock_status})
        if reagent_status in IDENTITY and not _identity_matches(reagent_status, row.get("reagent_identifier", "")):
            issues.append({"line": line_number, "plan_id": plan_id, "type": "reagent_identifier_status_mismatch"})
        if stock_status in IDENTITY and not _identity_matches(stock_status, row.get("stock_identifier", "")):
            issues.append({"line": line_number, "plan_id": plan_id, "type": "stock_identifier_status_mismatch"})
        developmental = (row.get("developmental_boundary") or "").strip()
        if developmental not in DEVELOPMENT:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_developmental_boundary", "value": developmental})
        source_status = (row.get("source_status") or "").strip()
        if source_status not in SOURCE_STATUS:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_source_status", "value": source_status})
        try:
            minimum_n = int((row.get("minimum_n") or "").strip())
            if minimum_n <= 0:
                raise ValueError
        except ValueError:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_minimum_n"})
        if perturbation == "pharmacology":
            if reagent_status == "pending_audit" and not any(hint in row.get("reagent_identifier", "").strip().lower() for hint in PENDING_HINTS):
                issues.append({"line": line_number, "plan_id": plan_id, "type": "pending_reagent_must_not_look_verified"})
            if reagent_status == "unknown":
                warnings.append({"line": line_number, "plan_id": plan_id, "type": "unknown_reagent_identity"})
        if perturbation == "RNAi":
            if stock_status == "pending_audit" and not any(hint in row.get("stock_identifier", "").strip().lower() for hint in PENDING_HINTS):
                issues.append({"line": line_number, "plan_id": plan_id, "type": "pending_stock_must_not_look_verified"})
            if stock_status == "unknown":
                warnings.append({"line": line_number, "plan_id": plan_id, "type": "unknown_stock_identity"})
        if stage == "formal_experiment":
            if reagent_status not in {"verified", "not_applicable"}:
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_verified_reagent_or_na"})
            if stock_status not in {"verified", "not_applicable"}:
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_verified_stock_or_na"})
            if developmental not in {"adult_restricted", "developmental_aware", "not_applicable"}:
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_developmental_boundary"})
        if source_status == "blocked":
            warnings.append({"line": line_number, "plan_id": plan_id, "type": "plan_source_status_blocked"})
    status = "verified_information_gain_pilot" if rows and not issues else "invalid_information_gain_pilot"
    return {"status": status, "n_rows": len(rows), "n_plans": len(seen), "issues": issues, "warnings": warnings, "inference_warning": "Validation checks plan completeness and anti-guessing gates; it does not establish biological causality, drug selectivity, stock genotype, driver expression or statistical power."}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate(args.input)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_information_gain_pilot" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
