#!/usr/bin/env python3
"""Validate assay-specific experiment metadata before rhythm or causal fitting."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


BASE_FIELDS = ("species", "genotype", "sex", "age_days", "temperature_C", "lighting", "ZT_or_CT", "experimental_unit", "biological_replicate_id", "batch_id")
ASSAY_FIELDS = {
    "ephys": ("preparation", "cell_type", "recording_id", "technical_replicate_id"),
    "imaging": ("preparation", "cell_type", "roi_id", "technical_replicate_id"),
    "expression": ("preparation", "cell_type", "library_id", "technical_replicate_id"),
    "behavior": ("cage_id",),
}
MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT_AVAILABLE", "NOT_APPLICABLE", "."}
ZT_RE = re.compile(r"(?:ZT|CT)\s*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
VALID_UNITS = {"fly", "brain", "cell", "library", "cage", "animal", "sample"}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _recorded_path(path: Path, provenance_root: Path | None = None) -> str:
    resolved = path.resolve()
    if provenance_root is not None:
        try:
            return resolved.relative_to(provenance_root.resolve()).as_posix()
        except ValueError:
            pass
    return str(path)


def _file_metadata(path: Path, provenance_root: Path | None = None) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": _recorded_path(path, provenance_root), "size_bytes": int(path.stat().st_size), "sha256": digest.hexdigest()}


def _parse_time(value: str) -> float | None:
    match = ZT_RE.fullmatch(value.strip())
    if not match:
        return None
    hour = float(match.group(1))
    return hour % 24.0 if math.isfinite(hour) else None


def validate(path: Path, assay: str = "ephys", stage: str = "exploratory", provenance_root: Path | None = None) -> dict[str, object]:
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    if assay not in ASSAY_FIELDS:
        return {"status": "blocked_metadata_schema", "issues": [{"type": "invalid_assay", "value": assay}], "warnings": []}
    required = BASE_FIELDS + ASSAY_FIELDS[assay]
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            missing_columns = [field for field in required if field not in fieldnames]
            if missing_columns:
                return {"status": "blocked_metadata_schema", "issues": [{"type": "missing_columns", "columns": missing_columns}], "warnings": [], "required_fields": list(required)}
            rows = list(reader)
    except (OSError, UnicodeDecodeError) as exc:
        return {"status": "blocked_metadata_schema", "issues": [{"type": "input_read_error", "message": str(exc)}], "warnings": [], "required_fields": list(required)}
    if not rows:
        errors.append({"type": "empty_table"})
    unit_values: set[str] = set()
    bio_to_rows: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for line_number, row in enumerate(rows, start=2):
        for field in required:
            if not _present(row.get(field)):
                target = "high_impact_missing" if field in {"species", "genotype", "sex", "age_days", "temperature_C", "lighting", "ZT_or_CT", "experimental_unit", "biological_replicate_id", "batch_id"} else "missing_assay_field"
                issue = {"line": line_number, "type": target, "field": field}
                (errors if stage == "formal" and target == "high_impact_missing" else warnings).append(issue)
        unit = (row.get("experimental_unit") or "").strip().lower()
        if _present(unit):
            unit_values.add(unit)
            if unit not in VALID_UNITS:
                errors.append({"line": line_number, "type": "invalid_experimental_unit", "value": unit})
        for field in ("age_days", "temperature_C"):
            value = (row.get(field) or "").strip()
            if _present(value):
                try:
                    if not math.isfinite(float(value)):
                        raise ValueError
                except ValueError:
                    errors.append({"line": line_number, "type": "non_numeric_or_nonfinite", "field": field, "value": value})
        time_value = (row.get("ZT_or_CT") or "").strip()
        if _present(time_value) and _parse_time(time_value) is None:
            errors.append({"line": line_number, "type": "invalid_circadian_time", "value": time_value})
        bio_id = (row.get("biological_replicate_id") or "").strip()
        if _present(bio_id):
            bio_to_rows[bio_id].append(row)
    for bio_id, bio_rows in bio_to_rows.items():
        for field in ("genotype", "sex", "age_days", "temperature_C", "batch_id"):
            values = {(row.get(field) or "").strip() for row in bio_rows if _present(row.get(field))}
            if len(values) > 1:
                errors.append({"type": "biological_replicate_metadata_conflict", "biological_replicate_id": bio_id, "field": field, "values": sorted(values)})
    if len(unit_values) > 1:
        errors.append({"type": "mixed_experimental_units", "values": sorted(unit_values)})
    if stage == "formal" and len(bio_to_rows) < 3:
        errors.append({"type": "too_few_biological_replicates_for_formal_gate", "n_biological_replicates": len(bio_to_rows)})
    elif len(bio_to_rows) < 3:
        warnings.append({"type": "few_biological_replicates_for_exploration", "n_biological_replicates": len(bio_to_rows)})
    status = "verified_metadata" if not errors else "blocked_metadata_schema"
    return {"status": status, "assay": assay, "stage": stage, "required_fields": list(required), "n_rows": len(rows), "n_biological_replicates": len(bio_to_rows), "experimental_units": sorted(unit_values), "issues": errors, "warnings": warnings, "input_file_metadata": _file_metadata(path, provenance_root), "inference_warning": "Metadata verification is a schema/QC result; it does not establish rhythm, causality, power, cell identity or source-data validity."}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--assay", choices=sorted(ASSAY_FIELDS), default="ephys")
    parser.add_argument("--stage", choices=("exploratory", "formal"), default="exploratory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance-root", type=Path, help="Root used to record portable relative provenance paths.")
    args = parser.parse_args(argv[1:])
    result = validate(args.input, args.assay, args.stage, args.provenance_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_metadata" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


