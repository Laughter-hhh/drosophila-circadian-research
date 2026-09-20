#!/usr/bin/env python3
"""Validate automated or manual source-access reports before stage-gate use."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


REPORT_STATUSES = {"verified_source_access", "conditional_source_access", "blocked_source_access"}
ACCESS_STATUSES = {"reachable_content_verified", "reachable_content_unverified", "blocked_http_or_network"}


def _present(value: object) -> bool:
    return value is not None and str(value).strip() not in {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED"}


def _tokens(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if _present(item)]
    return [token.strip() for token in re.split(r"[;,]", str(value or "")) if token.strip()]


def _valid_timestamp(value: object) -> bool:
    if not _present(value):
        return False
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt.datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def validate(path: Path) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid_source_access_report",
            "formal_status": "blocked_by_validation_issues",
            "n_records": 0,
            "issues": [{"type": "report_read_error", "message": str(exc)}],
            "warnings": [],
        }
    if not isinstance(payload, dict):
        return {
            "status": "invalid_source_access_report",
            "formal_status": "blocked_by_validation_issues",
            "n_records": 0,
            "issues": [{"type": "report_must_be_object"}],
            "warnings": [],
        }
    report_status = str(payload.get("status") or "").strip().lower()
    if report_status not in REPORT_STATUSES:
        issues.append({"type": "invalid_report_status", "value": payload.get("status", "")})
    rows = payload.get("records")
    if not isinstance(rows, list) or not rows:
        issues.append({"type": "records_must_be_nonempty_list"})
        rows = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            issues.append({"record_index": index, "type": "record_must_be_object"})
            continue
        record_id = str(row.get("record_id") or "").strip()
        if not record_id:
            issues.append({"record_index": index, "type": "missing_record_id"})
            continue
        if record_id in seen:
            issues.append({"record_index": index, "record_id": record_id, "type": "duplicate_record_id"})
        seen.add(record_id)
        source_url = str(row.get("source_url") or "").strip()
        if not re.match(r"^https?://", source_url, flags=re.IGNORECASE):
            issues.append({"record_index": index, "record_id": record_id, "type": "invalid_source_url"})
        access_status = str(row.get("access_status") or "").strip().lower()
        if access_status not in ACCESS_STATUSES:
            issues.append({"record_index": index, "record_id": record_id, "type": "invalid_access_status", "value": row.get("access_status", "")})
            continue
        method = str(row.get("verification_method") or "").strip().lower()
        if access_status == "reachable_content_verified":
            if method == "browser_manual":
                if not _valid_timestamp(row.get("checked_at_utc")):
                    issues.append({"record_index": index, "record_id": record_id, "type": "manual_verified_requires_timestamp"})
                if not _tokens(row.get("observed_tokens")):
                    issues.append({"record_index": index, "record_id": record_id, "type": "manual_verified_requires_observed_tokens"})
                if not _present(row.get("observation_note")):
                    issues.append({"record_index": index, "record_id": record_id, "type": "manual_verified_requires_observation_note"})
            else:
                if row.get("http_status") is None or not isinstance(row.get("http_status"), int) or row.get("http_status") >= 400:
                    issues.append({"record_index": index, "record_id": record_id, "type": "automated_verified_requires_success_http_status"})
                if not _tokens(row.get("matched_tokens")):
                    issues.append({"record_index": index, "record_id": record_id, "type": "automated_verified_requires_matched_tokens"})
                if not _present(row.get("body_sha256")):
                    issues.append({"record_index": index, "record_id": record_id, "type": "automated_verified_requires_body_hash"})
        elif method == "browser_manual" and not _valid_timestamp(row.get("checked_at_utc")):
            warnings.append({"record_index": index, "record_id": record_id, "type": "manual_unverified_timestamp_missing"})
    status = "verified_source_access_report" if not issues and rows else "invalid_source_access_report"
    return {
        "status": status,
        "formal_status": "report_schema_verified" if status == "verified_source_access_report" else "blocked_by_validation_issues",
        "report_status": report_status,
        "n_records": len(rows),
        "issues": issues,
        "warnings": warnings,
        "inference_warning": "This validator checks report structure and provenance fields; it does not independently prove that an automated token match or manual observation is true.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    result = validate(args.input)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_source_access_report" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
