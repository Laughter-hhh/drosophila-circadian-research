#!/usr/bin/env python3
"""Validate a traceable acute pharmacology plan for whole-cell recordings."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_candidate_evidence import validate as validate_candidate_evidence


REQUIRED = {
    "plan_id", "candidate", "neuron", "readout", "blocker", "concentration",
    "concentration_unit", "application", "vehicle", "washout",
    "blocker_selectivity_source", "concentration_source", "positive_control",
    "negative_control", "off_target_risk", "stage", "source_url",
    "selectivity_status", "dose_response_status", "washout_status",
}
MAPPING_REQUIRED = {"source_candidate", "evidence_candidate", "mapping_type", "mapping_status", "mapping_source"}
MISSING_TEXT = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED"}
VALID_UNITS = {"NM", "UM", "ΜM", "MM"}
VALID_SELECTIVITY = {"NATIVE_VERIFIED", "HETEROLOGOUS_ONLY", "NOT_ASSESSED", "UNKNOWN"}
VALID_DOSE_RESPONSE = {"VALIDATED", "NOT_ASSESSED", "UNKNOWN"}
VALID_WASHOUT = {"VALIDATED", "NEEDS_CONFIRMATION", "NOT_APPLICABLE", "UNKNOWN"}
VALID_STAGES = {"pilot", "conditional_pilot", "formal"}
VALID_MAPPING_TYPES = {"official_symbol_alias", "curated_synonym"}
VALID_MAPPING_STATUSES = {"checked"}
PRIMARY_HINTS = ("pubmed", "pmc", "doi.org", "nature.com", "cell.com", "wiley.com", "bristol.ac.uk")
ACTIONABLE_EVIDENCE_LABELS = {"direct", "near_direct", "indirect"}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING_TEXT


def _valid_concentration(value: str | None) -> bool:
    if not _present(value):
        return False
    try:
        return float((value or "").strip()) > 0
    except ValueError:
        return False


def _source_tokens(value: str | None) -> set[str]:
    return {
        token.strip().lower().rstrip("/")
        for token in (value or "").replace(",", ";").split(";")
        if token.strip()
    }


def _load_candidate_mapping(path: Path, issues: list[dict[str, object]]) -> tuple[dict[str, dict[str, str]], dict[str, object]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(MAPPING_REQUIRED - set(reader.fieldnames or []))
            if missing:
                issue = {"type": "candidate_mapping_missing_columns", "columns": missing}
                issues.append(issue)
                return {}, {"status": "blocked_candidate_mapping", "issues": [issue]}
            rows = list(reader)
    except (OSError, UnicodeDecodeError) as exc:
        issue = {"type": "candidate_mapping_read_error", "message": str(exc)}
        issues.append(issue)
        return {}, {"status": "blocked_candidate_mapping", "issues": [issue]}
    mapping: dict[str, dict[str, str]] = {}
    local_issues: list[dict[str, object]] = []
    for line_number, row in enumerate(rows, start=2):
        source_candidate = (row.get("source_candidate") or "").strip()
        evidence_candidate = (row.get("evidence_candidate") or "").strip()
        mapping_type = (row.get("mapping_type") or "").strip().lower()
        mapping_status = (row.get("mapping_status") or "").strip().lower()
        mapping_source = (row.get("mapping_source") or "").strip()
        if not source_candidate or not evidence_candidate:
            local_issues.append({"line": line_number, "type": "candidate_mapping_missing_candidate"})
            continue
        if mapping_type not in VALID_MAPPING_TYPES:
            local_issues.append({"line": line_number, "type": "candidate_mapping_invalid_type", "value": row.get("mapping_type", "")})
        if mapping_status not in VALID_MAPPING_STATUSES:
            local_issues.append({"line": line_number, "type": "candidate_mapping_not_checked", "value": row.get("mapping_status", "")})
        if not re.match(r"^https?://", mapping_source, flags=re.IGNORECASE):
            local_issues.append({"line": line_number, "type": "candidate_mapping_invalid_source"})
        previous = mapping.get(source_candidate)
        if previous is not None and previous["evidence_candidate"] != evidence_candidate:
            local_issues.append({"line": line_number, "type": "candidate_mapping_conflicting_targets", "source_candidate": source_candidate})
            continue
        if mapping_type in VALID_MAPPING_TYPES and mapping_status in VALID_MAPPING_STATUSES and re.match(r"^https?://", mapping_source, flags=re.IGNORECASE):
            mapping[source_candidate] = {
                "source_candidate": source_candidate,
                "evidence_candidate": evidence_candidate,
                "mapping_type": mapping_type,
                "mapping_status": mapping_status,
                "mapping_source": mapping_source,
            }
    issues.extend(local_issues)
    return mapping, {
        "status": "verified_candidate_mapping" if not local_issues else "blocked_candidate_mapping",
        "n_rows": len(rows),
        "n_mappings": len(mapping),
        "issues": local_issues,
    }


def _joint_candidate_gate(
    rows: list[dict[str, str]],
    candidate_evidence_path: Path | None,
    search_log_path: Path | None,
    candidate_mapping_path: Path | None,
    issues: list[dict[str, object]],
) -> dict[str, object]:
    """Require explicit candidate/evidence/search-log linkage when requested."""
    if candidate_evidence_path is None:
        if candidate_mapping_path is not None:
            issues.append({"type": "candidate_mapping_requires_evidence_table"})
            return {"status": "blocked_candidate_evidence_linkage", "records": []}
        return {"status": "not_requested", "records": []}
    if search_log_path is None:
        issues.append({"type": "candidate_evidence_search_log_required"})
        return {"status": "blocked_candidate_evidence_linkage", "records": []}
    mapping: dict[str, dict[str, str]] = {}
    mapping_result: dict[str, object] | None = None
    if candidate_mapping_path is not None:
        mapping, mapping_result = _load_candidate_mapping(candidate_mapping_path, issues)
    try:
        evidence_result = validate_candidate_evidence(candidate_evidence_path, search_log_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        issues.append({"type": "candidate_evidence_read_error", "message": str(exc)})
        return {"status": "blocked_candidate_evidence_linkage", "records": []}
    if evidence_result.get("status") != "verified_candidate_evidence_table":
        issues.append({
            "type": "candidate_evidence_gate_failed",
            "status": evidence_result.get("status"),
            "issues": evidence_result.get("issues", []),
        })
        return {
            "status": "blocked_candidate_evidence_linkage",
            "candidate_evidence_validation": evidence_result,
            "mapping_validation": mapping_result,
            "records": [],
        }
    with candidate_evidence_path.open(newline="", encoding="utf-8") as handle:
        evidence_rows = list(csv.DictReader(handle))
    by_candidate: dict[str, list[dict[str, str]]] = {}
    for evidence_row in evidence_rows:
        by_candidate.setdefault((evidence_row.get("candidate") or "").strip(), []).append(evidence_row)
    records: list[dict[str, object]] = []
    issue_start = len(issues)
    for line_number, row in enumerate(rows, start=2):
        candidate = (row.get("candidate") or "").strip()
        resolved_candidate = candidate
        mapping_used = False
        matches = by_candidate.get(candidate, [])
        if not matches and candidate in mapping:
            resolved_candidate = mapping[candidate]["evidence_candidate"]
            matches = by_candidate.get(resolved_candidate, [])
            mapping_used = True
        if not matches:
            issues.append({
                "line": line_number,
                "plan_id": row.get("plan_id", ""),
                "candidate": candidate,
                "type": "candidate_missing_from_evidence_table",
                "mapping_attempted": candidate in mapping,
            })
            continue
        evidence_row = matches[0]
        label = (evidence_row.get("evidence_label") or "").strip().lower()
        pharm_sources = _source_tokens(row.get("source_url"))
        evidence_sources = _source_tokens(evidence_row.get("sources"))
        source_linked = bool(pharm_sources.intersection(evidence_sources))
        if not source_linked:
            issues.append({
                "line": line_number,
                "plan_id": row.get("plan_id", ""),
                "candidate": candidate,
                "evidence_candidate": resolved_candidate,
                "type": "pharmacology_source_not_linked_to_candidate_evidence",
            })
        if label not in ACTIONABLE_EVIDENCE_LABELS:
            issues.append({
                "line": line_number,
                "plan_id": row.get("plan_id", ""),
                "candidate": candidate,
                "evidence_candidate": resolved_candidate,
                "type": "candidate_evidence_label_not_actionable",
                "evidence_label": label,
            })
        records.append({
            "line": line_number,
            "plan_id": row.get("plan_id", ""),
            "candidate": candidate,
            "evidence_candidate": resolved_candidate,
            "mapping_used": mapping_used,
            "mapping_source": mapping.get(candidate, {}).get("mapping_source"),
            "evidence_label": label,
            "target_cell_scope": evidence_row.get("target_cell_scope", ""),
            "readout_match": evidence_row.get("readout_match", ""),
            "source_linked": source_linked,
            "evidence_sources": evidence_row.get("sources", ""),
        })
    status = "verified_candidate_evidence_linkage" if len(issues) == issue_start and (mapping_result is None or mapping_result.get("status") == "verified_candidate_mapping") else "blocked_candidate_evidence_linkage"
    return {
        "status": status,
        "candidate_evidence_validation": evidence_result,
        "mapping_validation": mapping_result,
        "records": records,
    }


def validate(
    path: Path,
    candidate_evidence_path: Path | None = None,
    search_log_path: Path | None = None,
    candidate_mapping_path: Path | None = None,
) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {
                "status": "invalid_pharmacology_plan",
                "formal_status": "blocked_by_validation_issues",
                "issues": [{"type": "missing_columns", "columns": missing}],
                "n_rows": 0,
            }
        rows = list(reader)
    seen: set[str] = set()
    formal_rows = 0
    formal_passes = 0
    for line_number, row in enumerate(rows, start=2):
        plan_id = (row.get("plan_id") or "").strip()
        if not plan_id:
            issues.append({"line": line_number, "type": "missing_plan_id"})
        elif plan_id in seen:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "duplicate_plan_id"})
        seen.add(plan_id)
        for field in REQUIRED - {"concentration", "concentration_unit", "source_url"}:
            if not _present(row.get(field)):
                issues.append({"line": line_number, "plan_id": plan_id, "type": "missing_field", "field": field})
        if not _valid_concentration(row.get("concentration")):
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_concentration"})
        unit = (row.get("concentration_unit") or "").strip().upper()
        if unit not in VALID_UNITS:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_concentration_unit", "value": row.get("concentration_unit", "")})
        url = (row.get("source_url") or "").strip()
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_source_url"})
        elif not any(hint in url.lower() for hint in PRIMARY_HINTS):
            warnings.append({"line": line_number, "plan_id": plan_id, "type": "source_not_obviously_primary", "source_url": url})

        statuses = {
            "selectivity_status": VALID_SELECTIVITY,
            "dose_response_status": VALID_DOSE_RESPONSE,
            "washout_status": VALID_WASHOUT,
        }
        normalized: dict[str, str] = {}
        for field, allowed in statuses.items():
            value = (row.get(field) or "").strip().upper().replace("-", "_").replace(" ", "_")
            normalized[field] = value
            if not _present(value):
                issues.append({"line": line_number, "plan_id": plan_id, "type": "missing_field", "field": field})
            elif value not in allowed:
                issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_status", "field": field, "value": row.get(field, "")})

        stage = (row.get("stage") or "").strip().lower()
        if stage not in VALID_STAGES:
            issues.append({"line": line_number, "plan_id": plan_id, "type": "invalid_stage", "value": row.get("stage", "")})
            continue
        gate_failures: list[str] = []
        if stage == "formal":
            formal_rows += 1
            if normalized.get("selectivity_status") != "NATIVE_VERIFIED":
                gate_failures.append("native_selectivity")
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_native_selectivity", "value": row.get("selectivity_status", "")})
            if normalized.get("dose_response_status") != "VALIDATED":
                gate_failures.append("dose_response")
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_validated_dose_response", "value": row.get("dose_response_status", "")})
            if normalized.get("washout_status") not in {"VALIDATED", "NOT_APPLICABLE"}:
                gate_failures.append("washout")
                issues.append({"line": line_number, "plan_id": plan_id, "type": "formal_requires_validated_washout", "value": row.get("washout_status", "")})
            if not gate_failures:
                formal_passes += 1
        else:
            if normalized.get("selectivity_status") != "NATIVE_VERIFIED":
                gate_failures.append("native_selectivity")
                warnings.append({"line": line_number, "plan_id": plan_id, "type": "native_selectivity_not_verified", "status": row.get("selectivity_status", "")})
            if normalized.get("dose_response_status") != "VALIDATED":
                gate_failures.append("dose_response")
                warnings.append({"line": line_number, "plan_id": plan_id, "type": "dose_response_not_validated", "status": row.get("dose_response_status", "")})
            if normalized.get("washout_status") not in {"VALIDATED", "NOT_APPLICABLE"}:
                gate_failures.append("washout")
                warnings.append({"line": line_number, "plan_id": plan_id, "type": "washout_not_validated", "status": row.get("washout_status", "")})
            if gate_failures:
                warnings.append({"line": line_number, "plan_id": plan_id, "type": "blocked_for_formal", "gates": sorted(set(gate_failures))})
    candidate_provenance = _joint_candidate_gate(rows, candidate_evidence_path, search_log_path, candidate_mapping_path, issues)
    status = "verified_pharmacology_plan" if rows and not issues else "invalid_pharmacology_plan"
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
        "candidate_evidence_path": str(candidate_evidence_path) if candidate_evidence_path else None,
        "search_log_path": str(search_log_path) if search_log_path else None,
        "candidate_mapping_path": str(candidate_mapping_path) if candidate_mapping_path else None,
        "candidate_provenance": candidate_provenance,
        "inference_warning": "Validation checks completeness, format, formal-stage status gates, and optional candidate/source/mapping linkage; it does not verify native-cell selectivity, dose-response values, onset, washout kinetics, toxicity, or that cited sources support the chosen conditions. formal_status is a stage-gate summary, not a biological result.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--candidate-evidence", type=Path, help="Require exact candidate/source linkage to this validated evidence table.")
    parser.add_argument("--search-log", type=Path, help="Require the candidate evidence table to pass this validated evidence-search log.")
    parser.add_argument("--candidate-mapping", type=Path, help="Use only checked, source-backed candidate synonym mappings.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate(args.input, args.candidate_evidence, args.search_log, args.candidate_mapping)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_pharmacology_plan" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
