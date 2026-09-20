#!/usr/bin/env python3
"""Validate blocker-specific source records used by pharmacology plans."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


REQUIRED = {
    "record_id", "plan_id", "candidate", "blocker", "source_id",
    "source_url_or_identifier", "source_type", "organism", "target_neuron",
    "assay", "readout_match", "evidence_label", "claim_type",
    "source_support_status", "concentration_status", "reported_concentration",
    "reported_concentration_unit", "selectivity_support_status", "result_summary",
    "decision", "decision_reason",
}
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED"}
SOURCE_TYPES = {"primary_paper", "preprint", "review", "database", "other"}
EVIDENCE_LABELS = {"direct", "near_direct", "indirect", "unverified"}
CLAIM_TYPES = {"conclusion", "inference", "no_evidence"}
SOURCE_SUPPORT = {"checked", "not_checked", "conflict", "unavailable"}
CONCENTRATION_STATUS = {"matched", "not_assessed", "conflict"}
SELECTIVITY_STATUS = {"native_verified", "heterologous_only", "not_assessed", "conflict"}
DECISIONS = {"include", "conditional", "exclude_from_direct_shortlist"}
UNITS = {"NM", "UM", "ΜM", "MM"}
IDENTIFIER_PATTERN = re.compile(r"^(?:PMID|DOI|FBgn|GSE|GPL|BDSC|VDRC|NIG-FLY)[:_][A-Za-z0-9_.:/-]+$", re.IGNORECASE)


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _positive_number(value: str | None) -> bool:
    if not _present(value):
        return False
    try:
        return float((value or "").strip()) > 0
    except (TypeError, ValueError):
        return False


def _valid_source_reference(value: str) -> bool:
    return bool(re.match(r"^https?://", value, flags=re.IGNORECASE) or IDENTIFIER_PATTERN.match(value))


def validate(path: Path) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {
                "status": "invalid_pharmacology_source_log",
                "n_rows": 0,
                "issues": [{"type": "missing_columns", "columns": missing}],
            }
        rows = list(reader)
    seen_record_ids: set[str] = set()
    seen_keys: set[tuple[str, str, str]] = set()
    for line_number, row in enumerate(rows, start=2):
        record_id = (row.get("record_id") or "").strip()
        plan_id = (row.get("plan_id") or "").strip()
        candidate = (row.get("candidate") or "").strip()
        blocker = (row.get("blocker") or "").strip()
        key = (plan_id, candidate, blocker)
        concentration_status = (row.get("concentration_status") or "").strip().lower()
        if not record_id:
            issues.append({"line": line_number, "type": "missing_record_id"})
        elif record_id in seen_record_ids:
            issues.append({"line": line_number, "record_id": record_id, "type": "duplicate_record_id"})
        seen_record_ids.add(record_id)
        if key in seen_keys:
            issues.append({"line": line_number, "type": "duplicate_plan_candidate_blocker", "plan_id": plan_id, "candidate": candidate, "blocker": blocker})
        seen_keys.add(key)
        for field in REQUIRED:
            if field in {"reported_concentration", "reported_concentration_unit"} and concentration_status in {"not_assessed", "conflict"}:
                continue
            if not _present(row.get(field)):
                issues.append({"line": line_number, "record_id": record_id, "type": "missing_field", "field": field})
        source_ref = (row.get("source_url_or_identifier") or "").strip()
        if not _valid_source_reference(source_ref):
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_source_url_or_identifier"})
        source_type = (row.get("source_type") or "").strip().lower()
        if source_type not in SOURCE_TYPES:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_source_type", "value": row.get("source_type", "")})
        evidence_label = (row.get("evidence_label") or "").strip().lower()
        if evidence_label not in EVIDENCE_LABELS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_evidence_label", "value": row.get("evidence_label", "")})
        claim_type = (row.get("claim_type") or "").strip().lower()
        if claim_type not in CLAIM_TYPES:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_claim_type", "value": row.get("claim_type", "")})
        source_support = (row.get("source_support_status") or "").strip().lower()
        if source_support not in SOURCE_SUPPORT:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_source_support_status", "value": row.get("source_support_status", "")})
        if concentration_status not in CONCENTRATION_STATUS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_concentration_status", "value": row.get("concentration_status", "")})
        if concentration_status == "matched":
            if not _positive_number(row.get("reported_concentration")):
                issues.append({"line": line_number, "record_id": record_id, "type": "matched_concentration_requires_positive_value"})
            unit = (row.get("reported_concentration_unit") or "").strip().upper()
            if unit not in UNITS:
                issues.append({"line": line_number, "record_id": record_id, "type": "matched_concentration_requires_valid_unit"})
        selectivity_status = (row.get("selectivity_support_status") or "").strip().lower()
        if selectivity_status not in SELECTIVITY_STATUS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_selectivity_support_status", "value": row.get("selectivity_support_status", "")})
        decision = (row.get("decision") or "").strip().lower()
        if decision not in DECISIONS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_decision", "value": row.get("decision", "")})
    status = "verified_pharmacology_source_log" if rows and not issues else "invalid_pharmacology_source_log"
    return {
        "status": status,
        "n_rows": len(rows),
        "n_records": len(seen_record_ids),
        "n_plan_candidate_blockers": len(seen_keys),
        "issues": issues,
        "inference_warning": "This log validator checks blocker-specific source-record structure and self-consistency; it does not prove pharmacological selectivity, dose-response, washout, toxicity, or native-cell causality.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate(args.input)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_pharmacology_source_log" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
