#!/usr/bin/env python3
"""Audit a machine-readable Drosophila cross plan before ordering or setting crosses."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REQUIRED = {
    "cross_id",
    "purpose",
    "virgin_parent_sex",
    "virgin_parent_genotype",
    "virgin_parent_stock",
    "other_parent_sex",
    "other_parent_genotype",
    "other_parent_stock",
    "f1_target_genotype",
    "balancer_or_selection",
    "reciprocal_cross",
    "background_control",
    "temperature_C",
    "LD_schedule",
    "timeline_days",
    "stock_source_urls",
}
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED"}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def validate(path: Path, require_numeric_schedule: bool = True) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - fieldnames)
        if missing:
            return {"status": "invalid_cross_plan", "n_rows": 0, "issues": [{"type": "missing_columns", "columns": missing}], "warnings": []}
        rows = list(reader)
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        cross_id = (row.get("cross_id") or "").strip()
        if not cross_id:
            issues.append({"line": line_number, "type": "missing_cross_id"})
            continue
        if cross_id in seen:
            issues.append({"line": line_number, "cross_id": cross_id, "type": "duplicate_cross_id"})
        seen.add(cross_id)
        for column in sorted(REQUIRED - {"cross_id"}):
            if not _present(row.get(column)):
                issues.append({"line": line_number, "cross_id": cross_id, "column": column, "type": "missing_required_field"})
        if (row.get("virgin_parent_sex") or "").strip().lower() not in {"female", "f", "virgin female"}:
            issues.append({"line": line_number, "cross_id": cross_id, "type": "virgin_parent_must_be_female"})
        for column in ("other_parent_sex",):
            sex = (row.get(column) or "").strip().lower()
            if sex not in {"female", "male", "f", "m"}:
                issues.append({"line": line_number, "cross_id": cross_id, "column": column, "type": "invalid_sex_label"})
        if require_numeric_schedule:
            for column in ("temperature_C", "timeline_days"):
                try:
                    value = float(row.get(column, ""))
                    if value <= 0:
                        raise ValueError
                except ValueError:
                    issues.append({"line": line_number, "cross_id": cross_id, "column": column, "type": "must_be_positive_numeric"})
        reciprocal = (row.get("reciprocal_cross") or "").strip().lower()
        if reciprocal not in {"yes", "no", "planned", "not_needed"}:
            warnings.append({"line": line_number, "cross_id": cross_id, "type": "reciprocal_cross_label_not_standardized", "value": row.get("reciprocal_cross", "")})
        urls = row.get("stock_source_urls") or ""
        if _present(urls) and "flybase.org" not in urls.lower() and "bdsc.indiana.edu" not in urls.lower() and "vdrc" not in urls.lower():
            warnings.append({"line": line_number, "cross_id": cross_id, "type": "stock_source_needs_database_url"})
    status = "verified_cross_plan" if rows and not issues else "invalid_cross_plan"
    return {
        "status": status,
        "n_rows": len(rows),
        "n_crosses": len(seen),
        "issues": issues,
        "warnings": warnings,
        "inference_warning": "This audit checks completeness and formatting only; it does not confirm stock identity, genotype correctness, insertion chromosome, driver expression, or current availability.",
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
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_cross_plan" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
