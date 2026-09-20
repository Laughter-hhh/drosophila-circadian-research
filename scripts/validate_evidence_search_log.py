#!/usr/bin/env python3
"""Validate a structured literature/database evidence search log."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.score_candidates import UNVERIFIED_CELL, parse_cell_tokens


REQUIRED = {
    "record_id", "candidate", "query", "database", "search_date", "source_id", "source_url_or_identifier", "source_type",
    "organism", "target_cell_scope", "evidence_target_cells", "assay", "readout_match", "evidence_label", "claim_type", "source_support_status",
    "result_summary", "decision", "decision_reason",
}
SOURCE_TYPES = {"primary_paper", "preprint", "review", "FlyBase", "GEO", "stock_database", "other_database"}
TARGET_SCOPES = {"direct_target_neuron", "nearby_clock_neuron", "indirect_or_unverified", "none_or_unverified"}
READOUTS = {"membrane_potential_or_current", "expression_or_localization", "behavior_only", "none_or_unverified"}
LABELS = {"direct", "near_direct", "indirect", "unverified"}
CLAIMS = {"conclusion", "inference", "no_evidence"}
SUPPORT = {"checked", "not_checked", "conflict", "unavailable"}
DECISIONS = {"include", "conditional", "exclude_from_direct_shortlist"}


def _present(value: str | None) -> bool:
    token = (value or "").strip().upper()
    return token not in {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT_AVAILABLE", "NOT_APPLICABLE", "."}


def _required_present(field: str, value: str | None) -> bool:
    # `na` is a valid Drosophila gene symbol, so candidate identity is not
    # subject to the generic missing-token set.
    if field in {"candidate", "record_id"}:
        return bool((value or "").strip())
    return _present(value)


def validate(path: Path) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {"status": "invalid_evidence_search_log", "n_rows": 0, "issues": [{"type": "missing_columns", "columns": missing}]}
        rows = list(reader)
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        record_id = (row.get("record_id") or "").strip()
        candidate = (row.get("candidate") or "").strip()
        if not record_id:
            issues.append({"line": line_number, "type": "missing_record_id"})
        elif record_id in seen:
            issues.append({"line": line_number, "record_id": record_id, "type": "duplicate_record_id"})
        seen.add(record_id)
        for field in ("candidate", "query", "database", "source_id", "source_url_or_identifier", "organism", "assay", "result_summary", "decision_reason"):
            if not _required_present(field, row.get(field)):
                issues.append({"line": line_number, "record_id": record_id, "type": f"missing_{field}"})
        try:
            dt.date.fromisoformat((row.get("search_date") or "").strip())
        except ValueError:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_search_date"})
        source_type = (row.get("source_type") or "").strip()
        if source_type not in SOURCE_TYPES:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_source_type", "value": source_type})
        target = (row.get("target_cell_scope") or "").strip()
        if target not in TARGET_SCOPES:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_target_cell_scope", "value": target})
        try:
            evidence_cells = parse_cell_tokens(row.get("evidence_target_cells"))
        except ValueError as exc:
            evidence_cells = []
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_evidence_target_cells", "message": str(exc)})
        readout = (row.get("readout_match") or "").strip()
        if readout not in READOUTS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_readout_match", "value": readout})
        label = (row.get("evidence_label") or "").strip()
        if label not in LABELS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_evidence_label", "value": label})
        claim = (row.get("claim_type") or "").strip()
        if claim not in CLAIMS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_claim_type", "value": claim})
        support = (row.get("source_support_status") or "").strip()
        if support not in SUPPORT:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_source_support_status", "value": support})
        decision = (row.get("decision") or "").strip()
        if decision not in DECISIONS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_decision", "value": decision})
        if label == "direct" and (target != "direct_target_neuron" or readout not in {"membrane_potential_or_current", "expression_or_localization"} or not _present(row.get("assay"))):
            issues.append({"line": line_number, "record_id": record_id, "type": "direct_label_without_target_assay_readout"})
        if label == "direct" and (not evidence_cells or evidence_cells == [UNVERIFIED_CELL]):
            issues.append({"line": line_number, "record_id": record_id, "type": "direct_label_without_evidence_target_cells"})
        if label == "direct" and support != "checked":
            issues.append({"line": line_number, "record_id": record_id, "type": "direct_label_requires_checked_source"})
        if label == "unverified" and decision == "include":
            issues.append({"line": line_number, "record_id": record_id, "type": "unverified_cannot_be_directly_included"})
        if source_type in {"primary_paper", "preprint", "review"} and "thesis" in (row.get("source_url_or_identifier") or "").lower():
            issues.append({"line": line_number, "record_id": record_id, "type": "thesis_source_not_allowed"})
    status = "verified_evidence_search_log" if rows and not issues else "invalid_evidence_search_log"
    return {"status": status, "n_rows": len(rows), "n_records": len(seen), "issues": issues, "inference_warning": "Schema validation does not prove that a source supports the claim; each primary source still requires online/full-text review."}


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
    return 0 if result["status"] == "verified_evidence_search_log" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
