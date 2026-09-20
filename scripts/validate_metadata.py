#!/usr/bin/env python3
"""Validate a CSV data dictionary/sample sheet before formal analysis."""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path


DEFAULT_REQUIRED = (
    "species",
    "genotype",
    "sex",
    "age_days",
    "temperature_C",
    "lighting",
    "ZT_or_CT",
    "experimental_unit",
    "biological_replicate_id",
    "batch_id",
)
NUMERIC_FIELDS = {"age_days", "temperature_C"}


def validate(path: Path, required: tuple[str, ...] = DEFAULT_REQUIRED) -> list[str]:
    errors: list[str] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return ["CSV has no header"]
            missing_columns = [name for name in required if name not in reader.fieldnames]
            errors.extend(f"missing required column: {name}" for name in missing_columns)
            if missing_columns:
                return errors
            rows = list(reader)
    except FileNotFoundError:
        return [f"file not found: {path}"]
    except UnicodeDecodeError as exc:
        return [f"file is not UTF-8: {exc}"]

    if not rows:
        errors.append("CSV contains no data rows")
        return errors

    for line_no, row in enumerate(rows, start=2):
        for name in required:
            if not (row.get(name) or "").strip():
                errors.append(f"line {line_no}: blank required field: {name}")
        for name in NUMERIC_FIELDS.intersection(required):
            value = (row.get(name) or "").strip()
            if value:
                try:
                    if not math.isfinite(float(value)):
                        errors.append(f"line {line_no}: non-finite {name}")
                except ValueError:
                    errors.append(f"line {line_no}: {name} is not numeric: {value}")

    return errors


def main(argv: list[str]) -> int:
    if len(argv) not in {2, 3}:
        print("usage: validate_metadata.py DATA.csv [comma,separated,required,fields]", file=sys.stderr)
        return 2
    required = DEFAULT_REQUIRED if len(argv) == 2 else tuple(x for x in argv[2].split(",") if x)
    errors = validate(Path(argv[1]), required)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: metadata passed required-field and numeric checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
