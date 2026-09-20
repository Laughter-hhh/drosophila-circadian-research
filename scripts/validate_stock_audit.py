#!/usr/bin/env python3
"""Validate stock identity records before formal Drosophila crosses."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

REQUIRED = {
    "candidate", "flybase_id", "flybase_url", "stock_center", "stock_number",
    "full_genotype", "insertion_chromosome", "genetic_background",
    "balancer_or_marker", "availability_status", "source_checked_date",
    "source_url", "verification_status", "notes",
}
MISSING_TEXT = {
    "", "NA", "N/A", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NONE REPORTED",
}
FLYBASE_ID_RE = re.compile(r"FB(?:gn|st|ti|tp|al|ba|ab)\d+")


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING_TEXT


def _extract_report_id(url: str) -> str | None:
    """Extract the FlyBase object ID encoded in a /reports/<ID> URL."""
    match = re.search(r"/reports/(FB(?:gn|st|ti|tp|al|ba|ab)\d+)(?:[/?.#]|$)", url, flags=re.IGNORECASE)
    return match.group(1).upper() if match else None


def validate(path: Path) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {"status": "invalid_stock_audit", "formal_status": "blocked_by_validation_issues", "issues": [{"type": "missing_columns", "columns": missing}], "n_rows": 0}
        rows = list(reader)
    seen: set[str] = set()
    identity_fields = {"stock_number", "full_genotype", "insertion_chromosome", "genetic_background", "balancer_or_marker"}
    verification_values: list[str] = []
    for line_number, row in enumerate(rows, start=2):
        candidate = (row.get("candidate") or "").strip()
        if not candidate:
            issues.append({"line": line_number, "type": "missing_candidate"})
        elif candidate in seen:
            issues.append({"line": line_number, "candidate": candidate, "type": "duplicate_candidate"})
        seen.add(candidate)
        for field in REQUIRED:
            if not _present(row.get(field)):
                issues.append({"line": line_number, "candidate": candidate, "type": "missing_field", "field": field})
        flybase_id = (row.get("flybase_id") or "").strip()
        if _present(flybase_id) and not FLYBASE_ID_RE.fullmatch(flybase_id):
            issues.append({"line": line_number, "candidate": candidate, "type": "invalid_flybase_id", "value": flybase_id})
        flybase_url = (row.get("flybase_url") or "").strip()
        if _present(flybase_url):
            if not re.match(r"^https?://", flybase_url, flags=re.IGNORECASE):
                issues.append({"line": line_number, "candidate": candidate, "type": "invalid_url", "field": "flybase_url"})
            elif _present(flybase_id):
                report_id = _extract_report_id(flybase_url)
                if report_id is None:
                    issues.append({"line": line_number, "candidate": candidate, "type": "unparseable_flybase_url", "value": flybase_url})
                elif report_id != flybase_id.upper():
                    issues.append({"line": line_number, "candidate": candidate, "type": "flybase_url_id_mismatch", "expected": flybase_id.upper(), "observed": report_id})
        value = (row.get("source_url") or "").strip()
        if _present(value) and not re.match(r"^https?://", value, flags=re.IGNORECASE):
            issues.append({"line": line_number, "candidate": candidate, "type": "invalid_url", "field": "source_url"})
        checked = (row.get("source_checked_date") or "").strip()
        if _present(checked):
            try:
                date.fromisoformat(checked)
            except ValueError:
                issues.append({"line": line_number, "candidate": candidate, "type": "invalid_source_checked_date", "value": checked})
        status = (row.get("verification_status") or "").strip().lower()
        verification_values.append(status)
        if status == "identity_verified":
            for field in identity_fields:
                if not _present(row.get(field)):
                    issues.append({"line": line_number, "candidate": candidate, "type": "verified_identity_missing_field", "field": field})
        elif status in {"partial", "not_verified"}:
            warnings.append({"line": line_number, "candidate": candidate, "type": "identity_not_ready_for_formal_cross", "verification_status": status})
        else:
            issues.append({"line": line_number, "candidate": candidate, "type": "invalid_verification_status", "value": row.get("verification_status", "")})
    status = "verified_stock_audit" if rows and not issues else "invalid_stock_audit"
    if issues:
        formal_status = "blocked_by_validation_issues"
    elif any(value != "identity_verified" for value in verification_values):
        formal_status = "blocked_identity_not_verified"
    else:
        formal_status = "identity_gate_passed_external_checks_pending"
    return {
        "status": status,
        "formal_status": formal_status,
        "n_rows": len(rows),
        "n_candidates": len(seen),
        "n_identity_verified": sum(value == "identity_verified" for value in verification_values),
        "n_identity_not_verified": sum(value != "identity_verified" for value in verification_values),
        "issues": issues,
        "warnings": warnings,
        "inference_warning": "Validation checks identity-field completeness, FlyBase URL/ID consistency, and format only; it does not verify current inventory, genotype correctness, chromosome location, driver expression, background purity, or construct function. formal_status therefore never means a complete experimental readiness decision.",
    }


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
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_stock_audit" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
