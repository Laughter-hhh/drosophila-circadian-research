#!/usr/bin/env python3
"""Validate an auditable candidate evidence table before scoring.

The default mode checks the candidate-table schema. ``--search-log`` adds a
joint provenance gate: every scored candidate must occur in a valid evidence
search log, at least one log source must be marked ``checked`` when the row is
labelled direct/near_direct/indirect, and at least one source identifier or
URL must be shared between the two tables.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.score_candidates import DIMENSIONS, DIRECTNESS_LABELS, MISSING, READOUT_MATCHES, TARGET_SCOPES, UNVERIFIED_CELL, _rating, parse_cell_tokens
from scripts.validate_evidence_search_log import validate as validate_search_log


REQUIRED = {
    "candidate", "class", "organism", "target_cell_scope", "evidence_target_cells", "assay", "readout_match", "evidence_label",
    "expression", "electrophysiology", "genetic_tools", "class_match", "rhythmic_evidence", "fly_causal", "cross_species",
    "keep_drop_reason", "sources", "confidence", "evidence_notes",
}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _source_tokens(value: str | None) -> set[str]:
    return {token.strip().lower() for token in (value or "").replace(",", ";").split(";") if token.strip()}


def _base_validate(rows: list[dict[str, str]], fieldnames: set[str]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        candidate = (row.get("candidate") or "").strip()
        if not candidate:
            issues.append({"line": line_number, "type": "missing_candidate"})
            continue
        if candidate in seen:
            issues.append({"line": line_number, "candidate": candidate, "type": "duplicate_candidate"})
        seen.add(candidate)
        for field in ("class", "organism", "target_cell_scope", "evidence_target_cells", "assay", "readout_match", "evidence_label", "keep_drop_reason", "confidence", "evidence_notes"):
            if not _present(row.get(field)):
                issues.append({"line": line_number, "candidate": candidate, "type": f"missing_{field}"})
        target = (row.get("target_cell_scope") or "").strip().lower()
        if _present(target) and target not in TARGET_SCOPES:
            issues.append({"line": line_number, "candidate": candidate, "type": "invalid_target_cell_scope", "value": target})
        readout = (row.get("readout_match") or "").strip().lower()
        if _present(readout) and readout not in READOUT_MATCHES:
            issues.append({"line": line_number, "candidate": candidate, "type": "invalid_readout_match", "value": readout})
        label = (row.get("evidence_label") or "").strip().lower()
        if _present(label) and label not in DIRECTNESS_LABELS:
            issues.append({"line": line_number, "candidate": candidate, "type": "invalid_evidence_label", "value": label})
        if label == "direct" and (target != "direct_target_neuron" or not _present(row.get("assay")) or readout not in {"membrane_potential_or_current", "expression_or_localization", "intracellular_ion_concentration"}):
            issues.append({"line": line_number, "candidate": candidate, "type": "direct_label_without_target_assay_readout"})
        try:
            evidence_cells = parse_cell_tokens(row.get("evidence_target_cells"))
        except ValueError as exc:
            evidence_cells = []
            issues.append({"line": line_number, "candidate": candidate, "type": "invalid_evidence_target_cells", "message": str(exc)})
        if label == "direct" and (not evidence_cells or evidence_cells == [UNVERIFIED_CELL]):
            issues.append({"line": line_number, "candidate": candidate, "type": "direct_label_without_evidence_target_cells"})
        observed = 0
        for field in DIMENSIONS:
            try:
                rating = _rating(row.get(field, "NA"))
            except ValueError as exc:
                issues.append({"line": line_number, "candidate": candidate, "dimension": field, "type": "invalid_rating", "message": str(exc)})
                continue
            observed += rating is not None
        if (observed or label in {"direct", "near_direct", "indirect"}) and not _present(row.get("sources")):
            issues.append({"line": line_number, "candidate": candidate, "type": "missing_sources_for_rated_evidence"})
        if label in {"direct", "near_direct", "indirect"} and not _present(row.get("evidence_notes")):
            issues.append({"line": line_number, "candidate": candidate, "type": "missing_evidence_notes_for_label"})
    return issues


def _apply_search_log_gate(rows: list[dict[str, str]], search_log_path: Path, issues: list[dict[str, object]]) -> dict[str, object]:
    try:
        log_result = validate_search_log(search_log_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        issues.append({"type": "evidence_search_log_read_error", "message": str(exc)})
        return {"status": "invalid_evidence_search_log", "issues": [{"type": "read_error", "message": str(exc)}]}
    if log_result.get("status") != "verified_evidence_search_log":
        issues.append({"type": "evidence_search_log_gate_failed", "status": log_result.get("status")})
        return log_result
    with search_log_path.open(newline="", encoding="utf-8") as handle:
        log_rows = list(csv.DictReader(handle))
    by_candidate: dict[str, list[dict[str, str]]] = {}
    for row in log_rows:
        by_candidate.setdefault((row.get("candidate") or "").strip(), []).append(row)
    for line_number, row in enumerate(rows, start=2):
        candidate = (row.get("candidate") or "").strip()
        label = (row.get("evidence_label") or "").strip().lower()
        candidate_logs = by_candidate.get(candidate, [])
        if not candidate_logs:
            issues.append({"line": line_number, "candidate": candidate, "type": "candidate_missing_from_search_log"})
            continue
        candidate_sources = _source_tokens(row.get("sources"))
        log_sources = set()
        for log_row in candidate_logs:
            log_sources.update(_source_tokens(log_row.get("source_id")))
            log_sources.update(_source_tokens(log_row.get("source_url_or_identifier")))
        if candidate_sources and not candidate_sources.intersection(log_sources):
            issues.append({"line": line_number, "candidate": candidate, "type": "candidate_source_not_linked_to_search_log"})
        if label in {"direct", "near_direct", "indirect"}:
            checked = [log_row for log_row in candidate_logs if (log_row.get("source_support_status") or "").strip().lower() == "checked"]
            if not checked:
                issues.append({"line": line_number, "candidate": candidate, "type": "label_requires_checked_search_log_source", "evidence_label": label})
        if label in {"direct", "near_direct", "indirect"}:
            candidate_sources = _source_tokens(row.get("sources"))
            candidate_readout = (row.get("readout_match") or "").strip()
            candidate_scope = (row.get("target_cell_scope") or "").strip()
            allowed_log_labels = {
                "direct": {"direct"},
                "near_direct": {"direct", "near_direct"},
                "indirect": {"direct", "near_direct", "indirect"},
            }[label]
            matching = []
            for log_row in candidate_logs:
                log_sources = _source_tokens(log_row.get("source_id")) | _source_tokens(log_row.get("source_url_or_identifier"))
                if (
                    (log_row.get("source_support_status") or "").strip().lower() == "checked"
                    and (log_row.get("readout_match") or "").strip() == candidate_readout
                    and (log_row.get("target_cell_scope") or "").strip() == candidate_scope
                    and (log_row.get("evidence_label") or "").strip().lower() in allowed_log_labels
                    and candidate_sources.intersection(log_sources)
                ):
                    matching.append(log_row)
            if not matching:
                issues.append({
                    "line": line_number,
                    "candidate": candidate,
                    "type": "candidate_readout_not_supported_by_linked_search_log",
                    "readout_match": candidate_readout,
                    "target_cell_scope": candidate_scope,
                })
            else:
                try:
                    candidate_cells = set(parse_cell_tokens(row.get("evidence_target_cells")))
                except ValueError:
                    candidate_cells = set()
                log_cells: set[str] = set()
                for log_row in matching:
                    try:
                        log_cells.update(parse_cell_tokens(log_row.get("evidence_target_cells")))
                    except ValueError:
                        continue
                if candidate_cells and candidate_cells != {UNVERIFIED_CELL} and not candidate_cells.issubset(log_cells):
                    issue_type = {
                        "direct": "direct_candidate_not_supported_by_matching_log_cells",
                        "near_direct": "near_direct_candidate_not_supported_by_matching_log_cells",
                        "indirect": "indirect_candidate_not_supported_by_matching_log_cells",
                    }[label]
                    issues.append({"line": line_number, "candidate": candidate, "type": issue_type})
    return log_result


def validate(path: Path, search_log_path: Path | None = None) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - fieldnames)
        if missing:
            return {"status": "invalid_candidate_evidence_table", "issues": [{"type": "missing_columns", "columns": missing}], "n_rows": 0}
        rows = list(reader)
    issues.extend(_base_validate(rows, fieldnames))
    search_log_result = None
    if search_log_path is not None:
        search_log_result = _apply_search_log_gate(rows, search_log_path, issues)
    status = "verified_candidate_evidence_table" if not issues and rows else "invalid_candidate_evidence_table"
    result: dict[str, object] = {
        "status": status,
        "n_rows": len(rows),
        "n_candidates": len({(row.get("candidate") or "").strip() for row in rows}),
        "issues": issues,
        "search_log_path": str(search_log_path) if search_log_path else None,
        "inference_warning": "Validation checks schema, evidence labels and traceability fields; source-log mode checks linkage and declared support status but still does not replace online/full-text review.",
    }
    if search_log_result is not None:
        result["evidence_search_log"] = search_log_result
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--search-log", type=Path, help="Require candidate/source linkage to this validated evidence-search log.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate(args.input, args.search_log)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_candidate_evidence_table" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
