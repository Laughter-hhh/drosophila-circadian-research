#!/usr/bin/env python3
"""Join metadata, raw-QC and derived measurements before pre-analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_experiment_metadata import validate as validate_metadata
from scripts.validate_raw_qc_provenance import validate as validate_raw_qc


MEASUREMENT_FIELDS = ("record_id", "metadata_row_id", "biological_replicate_id", "time_hours", "value")


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


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def validate_bundle(metadata_path: Path, raw_qc_path: Path, measurements_path: Path, assay: str = "ephys", stage: str = "exploratory", check_files: bool = False, provenance_root: Path | None = None) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    metadata_result = validate_metadata(metadata_path, assay=assay, stage=stage, provenance_root=provenance_root)
    raw_result = validate_raw_qc(raw_qc_path, assay=assay, check_files=check_files, metadata_path=metadata_path, provenance_root=provenance_root)
    if metadata_result.get("status") != "verified_metadata":
        issues.append({"type": "metadata_gate_failed", "status": metadata_result.get("status")})
    if raw_result.get("status") != "verified_raw_qc_provenance":
        issues.append({"type": "raw_qc_gate_failed", "status": raw_result.get("status")})
    try:
        raw_rows, _ = _read_rows(raw_qc_path)
        metadata_rows, metadata_fields = _read_rows(metadata_path)
        measurement_rows, measurement_fields = _read_rows(measurements_path)
    except (OSError, UnicodeDecodeError) as exc:
        return {"status": "blocked_preanalysis_bundle", "issues": issues + [{"type": "input_read_error", "message": str(exc)}], "metadata_gate": metadata_result, "raw_qc_gate": raw_result}
    missing_measurement_fields = [field for field in MEASUREMENT_FIELDS if field not in measurement_fields]
    if missing_measurement_fields:
        issues.append({"type": "measurement_missing_columns", "columns": missing_measurement_fields})
    raw_by_id = {(row.get("record_id") or "").strip(): row for row in raw_rows}
    meta_key = "metadata_row_id" if "metadata_row_id" in metadata_fields else ("sample_id" if "sample_id" in metadata_fields else None)
    metadata_by_id = {(row.get(meta_key) or "").strip(): row for row in metadata_rows} if meta_key else {}
    derived_counts: dict[str, int] = {}
    for line_number, row in enumerate(measurement_rows, start=2):
        record_id = (row.get("record_id") or "").strip()
        derived_counts[record_id] = derived_counts.get(record_id, 0) + 1
        if record_id not in raw_by_id:
            issues.append({"line": line_number, "type": "orphan_measurement_record", "record_id": record_id})
            continue
        raw = raw_by_id[record_id]
        if (raw.get("qc_status") or "").strip().lower() != "pass":
            issues.append({"line": line_number, "type": "measurement_from_nonpass_raw_record", "record_id": record_id, "qc_status": raw.get("qc_status", "")})
        metadata_id = (row.get("metadata_row_id") or "").strip()
        if metadata_id not in metadata_by_id:
            issues.append({"line": line_number, "type": "orphan_measurement_metadata", "metadata_row_id": metadata_id})
        elif metadata_id != (raw.get("metadata_row_id") or "").strip():
            issues.append({"line": line_number, "type": "measurement_raw_metadata_mismatch", "record_id": record_id})
        for field in ("biological_replicate_id", "time_hours", "value"):
            if not (row.get(field) or "").strip():
                issues.append({"line": line_number, "type": "measurement_missing_field", "field": field})
        try:
            if not math.isfinite(float(row.get("time_hours", ""))) or not math.isfinite(float(row.get("value", ""))):
                raise ValueError
        except ValueError:
            issues.append({"line": line_number, "type": "measurement_nonfinite_numeric", "record_id": record_id})
        if (row.get("biological_replicate_id") or "").strip() != (raw.get("biological_replicate_id") or "").strip():
            issues.append({"line": line_number, "type": "measurement_biological_replicate_mismatch", "record_id": record_id})
    pass_records = {record_id for record_id, row in raw_by_id.items() if (row.get("qc_status") or "").strip().lower() == "pass"}
    for record_id in sorted(pass_records):
        if derived_counts.get(record_id, 0) == 0:
            issues.append({"type": "pass_raw_record_without_measurement", "record_id": record_id})
    status = "verified_preanalysis_bundle" if not issues else "blocked_preanalysis_bundle"
    return {"status": status, "assay": assay, "stage": stage, "n_metadata_rows": len(metadata_rows), "n_raw_records": len(raw_rows), "n_pass_raw_records": len(pass_records), "n_measurement_rows": len(measurement_rows), "n_measurement_record_ids": len({key for key in derived_counts if key}), "orphan_measurement_record_ids": sorted(key for key in derived_counts if key not in raw_by_id), "metadata_gate": metadata_result, "raw_qc_gate": raw_result, "issues": issues, "input_file_metadata": {"metadata": _file_metadata(metadata_path, provenance_root), "raw_qc": _file_metadata(raw_qc_path, provenance_root), "measurements": _file_metadata(measurements_path, provenance_root)}, "inference_warning": "Bundle verification establishes input linkage and provenance only; it does not establish rhythm, cell identity, channel selectivity, causality or statistical power."}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--raw-qc", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--assay", choices=("ephys", "imaging"), default="ephys")
    parser.add_argument("--stage", choices=("exploratory", "formal"), default="exploratory")
    parser.add_argument("--check-files", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance-root", type=Path, help="Root used to record portable relative provenance paths.")
    args = parser.parse_args(argv[1:])
    result = validate_bundle(args.metadata, args.raw_qc, args.measurements, args.assay, args.stage, args.check_files, args.provenance_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_preanalysis_bundle" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


