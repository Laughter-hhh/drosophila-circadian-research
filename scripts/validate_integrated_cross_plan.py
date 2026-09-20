#!/usr/bin/env python3
"""Validate a complete Drosophila cross plan plus stock-to-cross stage gates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

try:
    from scripts.validate_cross_plan import REQUIRED as CROSS_REQUIRED
    from scripts.validate_cross_plan import validate as validate_cross_plan
    from scripts.validate_genetic_stage_gate import REQUIRED as GATE_REQUIRED
    from scripts.validate_genetic_stage_gate import validate as validate_gate
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.validate_cross_plan import REQUIRED as CROSS_REQUIRED
    from scripts.validate_cross_plan import validate as validate_cross_plan
    from scripts.validate_genetic_stage_gate import REQUIRED as GATE_REQUIRED
    from scripts.validate_genetic_stage_gate import validate as validate_gate

REQUIRED = CROSS_REQUIRED | (GATE_REQUIRED - {"source_urls"})
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NONE REPORTED"}


def _present(value: str | None, *, allow_na_symbol: bool = False) -> bool:
    normalized = (value or "").strip().upper()
    if allow_na_symbol and normalized == "NA":
        return True
    return normalized not in MISSING


def _load_rows(path: Path) -> tuple[list[dict[str, str]], list[str], list[dict[str, object]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        missing = sorted(REQUIRED - set(fieldnames))
        if missing:
            return [], fieldnames, [{"type": "missing_columns", "columns": missing}]
        return list(reader), fieldnames, []


def _normalise_gate_input(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> tuple[Path, Path | None]:
    """Add the gate's source_urls alias without forcing duplicate user columns."""
    if "source_urls" in fieldnames:
        return path, None
    handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
    normalised_fields = list(fieldnames) + ["source_urls"]
    writer = csv.DictWriter(handle, fieldnames=normalised_fields)
    writer.writeheader()
    for row in rows:
        normalised = dict(row)
        normalised["source_urls"] = row.get("stock_source_urls", "")
        writer.writerow(normalised)
    handle.close()
    return Path(handle.name), Path(handle.name)


def validate(path: Path, stock_audit_path: Path | None = None, source_access_path: Path | None = None) -> dict[str, object]:
    rows, fieldnames, structural_issues = _load_rows(path)
    if structural_issues:
        return {"status": "invalid_integrated_cross_plan", "formal_status": "blocked_by_validation_issues", "n_rows": 0, "issues": structural_issues, "warnings": []}
    gate_path, temporary_path = _normalise_gate_input(path, rows, fieldnames)
    try:
        cross_result = validate_cross_plan(path)
        gate_result = validate_gate(gate_path, stock_audit_path, source_access_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    issues: list[dict[str, object]] = list(cross_result.get("issues", [])) + list(gate_result.get("issues", []))
    warnings: list[dict[str, object]] = list(cross_result.get("warnings", [])) + list(gate_result.get("warnings", []))
    for line_number, row in enumerate(rows, start=2):
        cross_id = (row.get("cross_id") or "").strip()
        stage = (row.get("stage") or "").strip().lower()
        parents = {(row.get("virgin_parent_stock") or "").strip(), (row.get("other_parent_stock") or "").strip()}
        for field in ("driver_stock_candidate", "effector_stock_candidate"):
            candidate = (row.get(field) or "").strip()
            if _present(candidate) and candidate not in parents:
                record = {"line": line_number, "cross_id": cross_id, "field": field, "type": "parent_stock_link_missing", "value": candidate}
                (issues if stage == "formal" else warnings).append(record)
        if stage in {"pilot", "conditional_pilot"}:
            missing_links = [field for field in ("driver_stock_candidate", "effector_stock_candidate") if (row.get(field) or "").strip() not in parents]
            if missing_links:
                warnings.append({"line": line_number, "cross_id": cross_id, "type": "blocked_for_formal_parent_link", "fields": missing_links})
    formal_rows = int(gate_result.get("formal_rows", 0) or 0)
    formal_passes = int(gate_result.get("formal_passes", 0) or 0)
    status = "verified_integrated_cross_plan" if rows and not issues else "invalid_integrated_cross_plan"
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
        "n_crosses": len({(row.get("cross_id") or "").strip() for row in rows}),
        "formal_rows": formal_rows,
        "formal_passes": formal_passes,
        "issues": issues,
        "warnings": warnings,
        "source_access_report": gate_result.get("source_access_report", {}),
        "inference_warning": "This audit combines cross-plan completeness and stock-to-cross name linkage; it does not prove Mendelian segregation, expression, knockdown efficiency, insertion direction, background purity, or current stock inventory. formal_status is a stage-gate summary, not a biological result.",
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
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_integrated_cross_plan" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))




