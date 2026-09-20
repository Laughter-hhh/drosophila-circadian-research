#!/usr/bin/env python3
"""Validate extracted construct-level genetics and conditions from a primary paper."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

REQUIRED = {
    "paper_id", "reported_genotype", "driver", "effector", "cell_scope",
    "temperature_C", "LD_schedule", "free_running_condition", "experimental_unit",
    "n", "readout", "source_url", "evidence_level", "genotype_completeness", "notes",
}
MISSING_TEXT = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED"}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING_TEXT


def validate(path: Path) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {"status": "invalid_primary_genetics", "issues": [{"type": "missing_columns", "columns": missing}], "n_rows": 0}
        rows = list(reader)
    for line_number, row in enumerate(rows, start=2):
        paper_id = (row.get("paper_id") or "").strip()
        for field in REQUIRED:
            if not _present(row.get(field)):
                issues.append({"line": line_number, "paper_id": paper_id, "type": "missing_field", "field": field})
        for field in ("temperature_C", "n"):
            if _present(row.get(field)):
                try:
                    value = float((row.get(field) or "").strip())
                    if value <= 0:
                        raise ValueError
                except ValueError:
                    issues.append({"line": line_number, "paper_id": paper_id, "type": "invalid_positive_number", "field": field})
        url = (row.get("source_url") or "").strip()
        if _present(url) and not re.match(r"^https?://", url, flags=re.IGNORECASE):
            issues.append({"line": line_number, "paper_id": paper_id, "type": "invalid_source_url"})
        completeness = (row.get("genotype_completeness") or "").strip().lower()
        if completeness == "construct-level only":
            warnings.append({"line": line_number, "paper_id": paper_id, "type": "stock_identity_still_required"})
        elif completeness != "stock-complete":
            issues.append({"line": line_number, "paper_id": paper_id, "type": "invalid_genotype_completeness", "value": row.get("genotype_completeness", "")})
    status = "verified_primary_genetics" if rows and not issues else "invalid_primary_genetics"
    return {
        "status": status,
        "n_rows": len(rows),
        "issues": issues,
        "warnings": warnings,
        "inference_warning": "Validation checks extraction completeness and format only; it does not verify stock identity, driver expression, background, or the reported biological effect.",
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
    return 0 if result["status"] == "verified_primary_genetics" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
