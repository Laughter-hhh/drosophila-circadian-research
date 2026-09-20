#!/usr/bin/env python3
"""Validate raw ephys/imaging provenance, QC and metadata joins."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path


COMMON = ("record_id", "raw_file_path", "raw_file_sha256", "file_status", "metadata_row_id", "biological_replicate_id", "experimental_unit", "assay", "cell_type", "cell_identity_method", "qc_status", "exclusion_reason", "blinding_status", "derived_output_path")
ASSAY_FIELDS = {
    "ephys": ("seal_MOhm", "access_resistance_MOhm", "holding_current_pA", "baseline_drift_mV_per_min", "sampling_rate_Hz"),
    "imaging": ("roi_count", "motion_qc", "focus_qc", "signal_to_noise"),
}
MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT_AVAILABLE", "NOT_APPLICABLE", "."}
FILE_STATUS = {"present", "not_attached", "unknown"}
QC_STATUS = {"pass", "fail", "excluded", "pending"}
BLINDING = {"blinded", "unblinded", "not_applicable"}
UNIT = {"fly", "brain", "cell", "library", "cage", "animal", "sample"}


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
    return {"path": _recorded_path(path, provenance_root), "size_bytes": int(path.stat().st_size), "sha256": _sha256(path)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: str | None) -> bool:
    if not _present(value):
        return False
    try:
        return math.isfinite(float((value or "").strip()))
    except ValueError:
        return False


def _load_metadata(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        key = "metadata_row_id" if "metadata_row_id" in fields else ("sample_id" if "sample_id" in fields else None)
        if key is None:
            raise ValueError("metadata join file needs metadata_row_id or sample_id")
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            identifier = (row.get(key) or "").strip()
            if identifier:
                if identifier in rows:
                    raise ValueError(f"duplicate metadata identifier: {identifier}")
                rows[identifier] = row
    return rows


def validate(path: Path, assay: str = "ephys", check_files: bool = False, metadata_path: Path | None = None, provenance_root: Path | None = None) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    if assay not in ASSAY_FIELDS:
        return {"status": "blocked_raw_qc_provenance", "issues": [{"type": "invalid_assay", "value": assay}], "warnings": []}
    required = COMMON + ASSAY_FIELDS[assay]
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing_columns = [field for field in required if field not in set(reader.fieldnames or [])]
            if missing_columns:
                return {"status": "blocked_raw_qc_provenance", "issues": [{"type": "missing_columns", "columns": missing_columns}], "warnings": [], "required_fields": list(required)}
            rows = list(reader)
        metadata = _load_metadata(metadata_path) if metadata_path else {}
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return {"status": "blocked_raw_qc_provenance", "issues": [{"type": "input_read_error", "message": str(exc)}], "warnings": [], "required_fields": list(required)}
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        record_id = (row.get("record_id") or "").strip()
        if not record_id:
            issues.append({"line": line_number, "type": "missing_record_id"})
        elif record_id in seen:
            issues.append({"line": line_number, "record_id": record_id, "type": "duplicate_record_id"})
        seen.add(record_id)
        for field in ("raw_file_path", "metadata_row_id", "biological_replicate_id", "cell_identity_method", "derived_output_path"):
            if not _present(row.get(field)):
                issues.append({"line": line_number, "record_id": record_id, "type": f"missing_{field}"})
        if metadata_path:
            metadata_row = metadata.get((row.get("metadata_row_id") or "").strip())
            if metadata_row is None:
                issues.append({"line": line_number, "record_id": record_id, "type": "metadata_row_not_found"})
            else:
                for field in ("biological_replicate_id", "cell_type"):
                    manifest_value = (row.get(field) or "").strip()
                    metadata_value = (metadata_row.get(field) or "").strip()
                    if _present(manifest_value) and _present(metadata_value) and manifest_value != metadata_value:
                        issues.append({"line": line_number, "record_id": record_id, "type": "metadata_join_conflict", "field": field, "manifest_value": manifest_value, "metadata_value": metadata_value})
        file_status = (row.get("file_status") or "").strip()
        if file_status not in FILE_STATUS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_file_status", "value": file_status})
        digest = (row.get("raw_file_sha256") or "").strip().lower()
        if file_status == "present":
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                issues.append({"line": line_number, "record_id": record_id, "type": "invalid_raw_file_sha256"})
            if check_files:
                raw_path = Path(row.get("raw_file_path", ""))
                if not raw_path.is_absolute():
                    raw_path = (path.parent / raw_path).resolve()
                if not raw_path.is_file():
                    issues.append({"line": line_number, "record_id": record_id, "type": "raw_file_not_found", "path": str(raw_path)})
                elif _sha256(raw_path) != digest:
                    issues.append({"line": line_number, "record_id": record_id, "type": "raw_file_hash_mismatch"})
        elif file_status == "not_attached":
            if digest not in {"not_available", "pending"}:
                issues.append({"line": line_number, "record_id": record_id, "type": "not_attached_requires_not_available_hash"})
            warnings.append({"line": line_number, "record_id": record_id, "type": "raw_file_not_attached"})
        else:
            warnings.append({"line": line_number, "record_id": record_id, "type": "raw_file_status_unknown"})
        unit = (row.get("experimental_unit") or "").strip().lower()
        if unit not in UNIT:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_experimental_unit", "value": unit})
        row_assay = (row.get("assay") or "").strip().lower()
        if row_assay != assay:
            issues.append({"line": line_number, "record_id": record_id, "type": "assay_mismatch", "value": row_assay})
        qc_status = (row.get("qc_status") or "").strip().lower()
        if qc_status not in QC_STATUS:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_qc_status", "value": qc_status})
        if qc_status in {"fail", "excluded"} and not _present(row.get("exclusion_reason")):
            issues.append({"line": line_number, "record_id": record_id, "type": "exclusion_reason_required"})
        blinding = (row.get("blinding_status") or "").strip().lower()
        if blinding not in BLINDING:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_blinding_status", "value": blinding})
        if blinding == "unblinded":
            warnings.append({"line": line_number, "record_id": record_id, "type": "analysis_unblinded"})
        if assay == "ephys":
            for field in ASSAY_FIELDS[assay]:
                if qc_status == "pass" and not _finite(row.get(field)):
                    issues.append({"line": line_number, "record_id": record_id, "type": "pass_qc_requires_finite_metric", "field": field})
                elif qc_status != "pass" and not _finite(row.get(field)):
                    warnings.append({"line": line_number, "record_id": record_id, "type": "missing_or_nonfinite_metric", "field": field})
            if _finite(row.get("seal_MOhm")) and float(row["seal_MOhm"]) <= 0:
                issues.append({"line": line_number, "record_id": record_id, "type": "nonpositive_seal"})
            if _finite(row.get("access_resistance_MOhm")) and float(row["access_resistance_MOhm"]) <= 0:
                issues.append({"line": line_number, "record_id": record_id, "type": "nonpositive_access_resistance"})
            if _finite(row.get("sampling_rate_Hz")) and float(row["sampling_rate_Hz"]) <= 0:
                issues.append({"line": line_number, "record_id": record_id, "type": "nonpositive_sampling_rate"})
        else:
            for field in ASSAY_FIELDS[assay]:
                if qc_status == "pass" and not _finite(row.get(field)) and field != "roi_count":
                    issues.append({"line": line_number, "record_id": record_id, "type": "pass_qc_requires_finite_metric", "field": field})
            try:
                if qc_status == "pass" and int((row.get("roi_count") or "").strip()) <= 0:
                    raise ValueError
            except ValueError:
                issues.append({"line": line_number, "record_id": record_id, "type": "pass_qc_requires_positive_roi_count"})
    status = "verified_raw_qc_provenance" if rows and not issues else "blocked_raw_qc_provenance"
    return {"status": status, "assay": assay, "n_rows": len(rows), "n_records": len(seen), "issues": issues, "warnings": warnings, "input_file_metadata": _file_metadata(path, provenance_root), "inference_warning": "Raw-file provenance/QC verification does not establish cell identity, channel selectivity, rhythm, causality or biological validity."}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--assay", choices=sorted(ASSAY_FIELDS), default="ephys")
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--check-files", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance-root", type=Path, help="Root used to record portable relative provenance paths.")
    args = parser.parse_args(argv[1:])
    result = validate(args.input, args.assay, args.check_files, args.metadata, args.provenance_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_raw_qc_provenance" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


