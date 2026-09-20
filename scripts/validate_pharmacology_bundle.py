#!/usr/bin/env python3
"""Join a pharmacology plan with blocker-specific source provenance."""

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

from scripts.validate_pharmacology_plan import validate as validate_plan
from scripts.validate_pharmacology_source_log import validate as validate_source_log


ACTIONABLE_LABELS = {"direct", "near_direct", "indirect"}
UNITS = {"NM", "UM", "ΜM", "MM"}


def _tokens(value: str | None) -> set[str]:
    """Return stable tokens so a URL and its PMID/DOI identifier can match."""
    tokens: set[str] = set()
    for token in (value or "").replace(",", ";").split(";"):
        raw = token.strip().lower().rstrip("/")
        if not raw:
            continue
        tokens.add(raw)
        pmid_match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", raw)
        if pmid_match:
            tokens.add(f"pmid:{pmid_match.group(1)}")
        doi_match = re.search(r"doi\.org/(.+)$", raw)
        if doi_match:
            tokens.add(f"doi:{doi_match.group(1)}")
    return tokens


def _number(value: str | None) -> float | None:
    try:
        return float((value or "").strip())
    except (TypeError, ValueError):
        return None


def _source_gate(
    plan_path: Path,
    source_log_path: Path | None,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    if source_log_path is None:
        issues.append({"type": "pharmacology_source_log_required"})
        return {"status": "blocked_blocker_source_linkage", "records": []}, issues, warnings
    try:
        source_result = validate_source_log(source_log_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        issues.append({"type": "pharmacology_source_log_read_error", "message": str(exc)})
        return {"status": "blocked_blocker_source_linkage", "records": []}, issues, warnings
    if source_result.get("status") != "verified_pharmacology_source_log":
        issues.append({
            "type": "pharmacology_source_log_gate_failed",
            "status": source_result.get("status"),
            "issues": source_result.get("issues", []),
        })
        return {
            "status": "blocked_blocker_source_linkage",
            "source_log_validation": source_result,
            "records": [],
        }, issues, warnings
    with plan_path.open(newline="", encoding="utf-8") as handle:
        plan_rows = list(csv.DictReader(handle))
    with source_log_path.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in source_rows:
        key = (
            (row.get("plan_id") or "").strip(),
            (row.get("candidate") or "").strip(),
            (row.get("blocker") or "").strip(),
        )
        by_key[key] = row
    records: list[dict[str, object]] = []
    for line_number, plan_row in enumerate(plan_rows, start=2):
        plan_id = (plan_row.get("plan_id") or "").strip()
        candidate = (plan_row.get("candidate") or "").strip()
        blocker = (plan_row.get("blocker") or "").strip()
        stage = (plan_row.get("stage") or "").strip().lower()
        key = (plan_id, candidate, blocker)
        source_row = by_key.get(key)
        if source_row is None:
            issues.append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "blocker_missing_from_source_log",
            })
            continue
        source_linked = bool(
            _tokens(plan_row.get("source_url")).intersection(
                _tokens(source_row.get("source_url_or_identifier"))
            )
        )
        if not source_linked:
            issues.append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "blocker_source_not_linked_to_plan_source",
            })
        if (source_row.get("target_neuron") or "").strip() != (plan_row.get("neuron") or "").strip():
            issues.append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "blocker_target_neuron_mismatch",
                "plan_neuron": plan_row.get("neuron", ""),
                "source_log_neuron": source_row.get("target_neuron", ""),
            })
        source_support = (source_row.get("source_support_status") or "").strip().lower()
        if source_support != "checked":
            (issues if stage == "formal" else warnings).append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "blocker_source_not_checked",
                "source_support_status": source_row.get("source_support_status", ""),
            })
        evidence_label = (source_row.get("evidence_label") or "").strip().lower()
        if evidence_label not in ACTIONABLE_LABELS:
            (issues if stage == "formal" else warnings).append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "blocker_evidence_label_not_actionable",
                "evidence_label": source_row.get("evidence_label", ""),
            })
        concentration_status = (source_row.get("concentration_status") or "").strip().lower()
        if concentration_status == "matched":
            plan_value = _number(plan_row.get("concentration"))
            source_value = _number(source_row.get("reported_concentration"))
            plan_unit = (plan_row.get("concentration_unit") or "").strip().upper()
            source_unit = (source_row.get("reported_concentration_unit") or "").strip().upper()
            if (
                plan_value is None
                or source_value is None
                or abs(plan_value - source_value) > 1e-12
                or plan_unit not in UNITS
                or source_unit != plan_unit
            ):
                issues.append({
                    "line": line_number,
                    "plan_id": plan_id,
                    "candidate": candidate,
                    "blocker": blocker,
                    "type": "blocker_concentration_mismatch",
                })
        elif stage == "formal":
            issues.append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "formal_requires_blocker_concentration_match",
                "concentration_status": source_row.get("concentration_status", ""),
            })
        else:
            warnings.append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "blocker_concentration_not_verified",
                "concentration_status": source_row.get("concentration_status", ""),
            })
        selectivity_status = (source_row.get("selectivity_support_status") or "").strip().lower()
        if selectivity_status != "native_verified":
            (issues if stage == "formal" else warnings).append({
                "line": line_number,
                "plan_id": plan_id,
                "candidate": candidate,
                "blocker": blocker,
                "type": "blocker_native_selectivity_not_verified",
                "selectivity_support_status": source_row.get("selectivity_support_status", ""),
            })
        records.append({
            "line": line_number,
            "plan_id": plan_id,
            "candidate": candidate,
            "blocker": blocker,
            "source_linked": source_linked,
            "source_support_status": source_support,
            "evidence_label": evidence_label,
            "concentration_status": concentration_status,
            "selectivity_support_status": selectivity_status,
            "source_record_id": source_row.get("record_id", ""),
        })
    status = "verified_blocker_source_linkage" if not issues and not warnings else (
        "conditional_blocker_source_linkage" if not issues else "blocked_blocker_source_linkage"
    )
    return {
        "status": status,
        "source_log_validation": source_result,
        "n_records": len(records),
        "records": records,
    }, issues, warnings


def validate(
    plan_path: Path,
    source_log_path: Path | None = None,
    candidate_evidence_path: Path | None = None,
    search_log_path: Path | None = None,
    candidate_mapping_path: Path | None = None,
) -> dict[str, object]:
    plan_result = validate_plan(plan_path, candidate_evidence_path, search_log_path, candidate_mapping_path)
    blocker_result, blocker_issues, blocker_warnings = _source_gate(plan_path, source_log_path)
    issues = list(plan_result.get("issues", [])) + blocker_issues
    warnings = list(plan_result.get("warnings", [])) + blocker_warnings
    status = (
        "verified_pharmacology_bundle"
        if plan_result.get("status") == "verified_pharmacology_plan" and not issues
        else "invalid_pharmacology_bundle"
    )
    formal_status = "blocked_by_validation_issues" if issues else str(
        plan_result.get("formal_status", "conditional_pilot_only")
    )
    return {
        "status": status,
        "formal_status": formal_status,
        "plan_validation": plan_result,
        "blocker_provenance": blocker_result,
        "issues": issues,
        "warnings": warnings,
        "inference_warning": "This bundle gate joins plan fields to blocker-specific source records; it does not prove native-cell selectivity, dose-response, washout kinetics, toxicity, or causal channel function.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Pharmacology plan CSV.")
    parser.add_argument("--source-log", type=Path, help="Blocker-specific pharmacology source log CSV.")
    parser.add_argument("--candidate-evidence", type=Path)
    parser.add_argument("--search-log", type=Path)
    parser.add_argument("--candidate-mapping", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate(
            args.input,
            args.source_log,
            args.candidate_evidence,
            args.search_log,
            args.candidate_mapping,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_pharmacology_bundle" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
