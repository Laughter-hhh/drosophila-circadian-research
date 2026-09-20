#!/usr/bin/env python3
"""Audit whether a Drosophila genetic plan is ready for a formal cross."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    from scripts.validate_source_access_report import validate as validate_source_access_report
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.validate_source_access_report import validate as validate_source_access_report

REQUIRED = {
    "cross_id", "candidate", "stage", "driver_stock_candidate", "effector_stock_candidate",
    "driver_identity_status", "effector_identity_status", "driver_expression_status",
    "adult_restriction_strategy", "developmental_control", "background_match_status",
    "source_urls", "notes",
}
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NONE REPORTED"}
STAGES = {"pilot", "conditional_pilot", "formal"}
IDENTITY = {"identity_verified", "partial", "not_verified"}
EXPRESSION = {"verified", "not_assessed", "unknown"}
ADULT_RESTRICTION = {"verified", "not_applicable", "planned", "unknown"}
DEVELOPMENTAL = {"present", "absent", "not_applicable", "not_assessed"}
BACKGROUND = {"matched", "unmatched", "not_applicable", "not_assessed"}


def _present(value: str | None, *, allow_na_symbol: bool = False) -> bool:
    normalized = (value or "").strip().upper()
    if allow_na_symbol and normalized == "NA":
        return True
    return normalized not in MISSING


def _load_stock_audit(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"candidate", "verification_status"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"stock audit missing columns: {', '.join(missing)}")
        return {
            (row.get("candidate") or "").strip(): (row.get("verification_status") or "").strip().lower()
            for row in reader
            if _present(row.get("candidate"), allow_na_symbol=True)
        }



def _load_source_access(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"status": None, "validation_status": None, "records": {}, "validation": None}
    validation = validate_source_access_report(path)
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    records = {
        (record.get("record_id") or "").strip(): (record.get("access_status") or "").strip().lower()
        for record in payload.get("records", [])
        if (record.get("record_id") or "").strip()
    }
    return {
        "status": payload.get("status"),
        "validation_status": validation.get("status"),
        "records": records,
        "validation": validation,
    }

def _source_url_present(value: str) -> bool:
    return bool(re.search(r"https?://(?:www\.)?(?:flybase\.org|bdsc\.indiana\.edu|stockcenter\.vt\.edu|vdrc\.at|vdrc\.org)", value, re.IGNORECASE))


def validate(path: Path, stock_audit_path: Path | None = None, source_access_path: Path | None = None) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {"status": "invalid_genetic_stage_gate", "formal_status": "blocked_by_validation_issues", "n_rows": 0, "issues": [{"type": "missing_columns", "columns": missing}], "warnings": []}
        rows = list(reader)
    stock_status = _load_stock_audit(stock_audit_path)
    source_access = _load_source_access(source_access_path)
    seen: set[str] = set()
    formal_rows = 0
    formal_passes = 0
    for line_number, row in enumerate(rows, start=2):
        cross_id = (row.get("cross_id") or "").strip()
        stage = (row.get("stage") or "").strip().lower()
        if not cross_id:
            issues.append({"line": line_number, "type": "missing_cross_id"})
            continue
        if cross_id in seen:
            issues.append({"line": line_number, "cross_id": cross_id, "type": "duplicate_cross_id"})
        seen.add(cross_id)
        for field in sorted(REQUIRED - {"cross_id"}):
            if not _present(row.get(field), allow_na_symbol=(field == "candidate")):
                issues.append({"line": line_number, "cross_id": cross_id, "field": field, "type": "missing_required_field"})
        if stage not in STAGES:
            issues.append({"line": line_number, "cross_id": cross_id, "type": "invalid_stage", "value": row.get("stage", "")})
        if _present(row.get("source_urls")) and not _source_url_present(row.get("source_urls", "")):
            warnings.append({"line": line_number, "cross_id": cross_id, "type": "source_url_needs_database_or_primary_source"})
        statuses = {
            "driver_identity_status": (row.get("driver_identity_status") or "").strip().lower(),
            "effector_identity_status": (row.get("effector_identity_status") or "").strip().lower(),
            "driver_expression_status": (row.get("driver_expression_status") or "").strip().lower(),
            "adult_restriction_strategy": (row.get("adult_restriction_strategy") or "").strip().lower(),
            "developmental_control": (row.get("developmental_control") or "").strip().lower(),
            "background_match_status": (row.get("background_match_status") or "").strip().lower(),
        }
        allowed = {
            "driver_identity_status": IDENTITY, "effector_identity_status": IDENTITY,
            "driver_expression_status": EXPRESSION, "adult_restriction_strategy": ADULT_RESTRICTION,
            "developmental_control": DEVELOPMENTAL, "background_match_status": BACKGROUND,
        }
        for field, value in statuses.items():
            if value not in allowed[field]:
                issues.append({"line": line_number, "cross_id": cross_id, "field": field, "type": "invalid_status_label", "value": row.get(field, "")})
        gate_failures: list[str] = []
        driver_candidate = (row.get("driver_stock_candidate") or "").strip()
        effector_candidate = (row.get("effector_stock_candidate") or "").strip()
        if stage == "formal" and not stock_status:
            gate_failures.append("stock_audit_required")
        if stage == "formal" and source_access_path is None:
            gate_failures.append("online_source_access_required")
        if stage == "formal" and source_access_path is not None and source_access["validation_status"] != "verified_source_access_report":
            gate_failures.append("online_source_report_invalid")
            (issues if stage == "formal" else warnings).append({
                "line": line_number,
                "cross_id": cross_id,
                "type": "online_source_report_invalid",
                "validation_status": source_access.get("validation_status"),
            })
        if stock_status:
            for field, stock_candidate in (("driver_stock_candidate", driver_candidate), ("effector_stock_candidate", effector_candidate)):
                audited = stock_status.get(stock_candidate)
                if audited is None:
                    gate_failures.append("stock_candidate_not_in_audit")
                    (issues if stage == "formal" else warnings).append({"line": line_number, "cross_id": cross_id, "field": field, "type": "stock_candidate_not_in_audit", "value": stock_candidate})
                elif statuses["driver_identity_status" if field.startswith("driver") else "effector_identity_status"] == "identity_verified" and audited != "identity_verified":
                    gate_failures.append("declared_status_exceeds_audit")
                    (issues if stage == "formal" else warnings).append({"line": line_number, "cross_id": cross_id, "field": field, "type": "declared_status_exceeds_audit", "audit_status": audited, "declared_status": "identity_verified"})
                if audited != "identity_verified":
                    gate_failures.append("stock_identity_not_verified")
        for field, stock_candidate in (("driver_stock_candidate", driver_candidate), ("effector_stock_candidate", effector_candidate)):
            if source_access_path is not None:
                access_status = source_access["records"].get(stock_candidate)
                if access_status != "reachable_content_verified":
                    gate_failures.append("online_source_not_verified")
                    (issues if stage == "formal" else warnings).append({
                        "line": line_number,
                        "cross_id": cross_id,
                        "field": field,
                        "type": "online_source_not_verified",
                        "access_status": access_status or "missing",
                    })
        if statuses["driver_identity_status"] != "identity_verified": gate_failures.append("driver_identity")
        if statuses["effector_identity_status"] != "identity_verified": gate_failures.append("effector_identity")
        if statuses["driver_expression_status"] != "verified": gate_failures.append("driver_expression")
        if statuses["adult_restriction_strategy"] not in {"verified", "not_applicable"}: gate_failures.append("adult_restriction")
        if statuses["developmental_control"] not in {"present", "not_applicable"}: gate_failures.append("developmental_control")
        if statuses["background_match_status"] not in {"matched", "not_applicable"}: gate_failures.append("background_match")
        if stage == "formal":
            formal_rows += 1
            if gate_failures:
                mapping = {
                    "stock_audit_required": "formal_requires_stock_audit",
                    "online_source_access_required": "formal_requires_online_source_access",
                    "online_source_not_verified": "formal_requires_verified_online_source_access",
                    "online_source_report_invalid": "formal_requires_valid_online_source_report",
                    "stock_identity_not_verified": "formal_requires_audited_stock_identity",
                    "driver_identity": "formal_requires_driver_identity",
                    "effector_identity": "formal_requires_effector_identity",
                    "driver_expression": "formal_requires_driver_expression",
                    "adult_restriction": "formal_requires_adult_restriction",
                    "developmental_control": "formal_requires_developmental_control",
                    "background_match": "formal_requires_background_match",
                }
                for failure in sorted(set(gate_failures)):
                    if failure in mapping:
                        issues.append({"line": line_number, "cross_id": cross_id, "type": mapping[failure]})
            else:
                formal_passes += 1
        elif gate_failures:
            warnings.append({"line": line_number, "cross_id": cross_id, "type": "blocked_for_formal", "gates": sorted(set(gate_failures))})
    status = "verified_genetic_stage_gate" if rows and not issues else "invalid_genetic_stage_gate"
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
        "n_crosses": len(seen),
        "formal_rows": formal_rows,
        "formal_passes": formal_passes,
        "issues": issues,
        "warnings": warnings,
        "source_access_report": {"status": source_access.get("status"), "validation_status": source_access.get("validation_status"), "n_records": len(source_access.get("records", {}))},
        "inference_warning": "This gate checks declared fields and, when supplied, joins stock candidates to the stock audit; it does not verify expression, knockdown efficiency, insertion direction, background purity, or current inventory. formal_status is a stage-gate summary, not a biological result.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--stock-audit", type=Path)
    parser.add_argument("--source-access-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate(args.input, args.stock_audit, args.source_access_report)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_genetic_stage_gate" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))






