#!/usr/bin/env python3
"""Derive provenance-linked measurements from a normalized trace CSV.

The input is a normalized CSV export, not a vendor binary. It must contain
``record_id,time_seconds,value`` and, for imaging, ``roi_id``. A raw-QC
manifest and metadata sheet are required; only records with ``qc_status=pass``
are converted. Vendor-specific decoding is intentionally not guessed.

``time_mode=metadata`` emits one whole-trace summary (the backwards-compatible
default). ``elapsed`` or ``metadata_plus_elapsed`` emits one row per explicit
time bin, preserving long-trace structure; the latter anchors elapsed time to
the metadata ZT/CT token and is the appropriate choice only when the trace
origin is documented.
"""

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
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_experiment_metadata import validate as validate_metadata
from scripts.validate_raw_qc_provenance import validate as validate_raw_qc


TIME_RE = re.compile(r"(?:ZT|CT)\s*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
OUTPUT_FIELDS = (
    "record_id", "metadata_row_id", "biological_replicate_id", "time_hours", "value",
    "metric_name", "value_unit", "subunit_id", "n_trace_samples", "trace_duration_seconds",
    "time_basis", "time_bin_start_seconds",
)
TIME_MODES = {"metadata", "elapsed", "metadata_plus_elapsed"}


def _recorded_path(path: Path, provenance_root: Path | None = None) -> str:
    resolved = path.resolve()
    if provenance_root is not None:
        try:
            return resolved.relative_to(provenance_root.resolve()).as_posix()
        except ValueError:
            pass
    return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_metadata(path: Path, provenance_root: Path | None = None) -> dict[str, object]:
    return {"path": _recorded_path(path, provenance_root), "size_bytes": int(path.stat().st_size), "sha256": _sha256(path)}


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _finite(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite: {value!r}")
    return number


def _circadian_hours(token: str) -> float:
    match = TIME_RE.fullmatch(token.strip())
    if not match:
        raise ValueError(f"invalid ZT/CT token: {token!r}")
    return _finite(match.group(1), "ZT_or_CT") % 24.0


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("cannot average an empty trace")
    return sum(values) / len(values)


def derive(
    traces_path: Path,
    metadata_path: Path,
    raw_qc_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    assay: str = "ephys",
    stage: str = "exploratory",
    check_files: bool = True,
    value_column: str = "value",
    metric_name: str | None = None,
    value_unit: str | None = None,
    min_samples: int = 4,
    time_mode: str = "metadata",
    time_bin_seconds: float = 3600.0,
    provenance_root: Path | None = None,
) -> dict[str, object]:
    """Validate inputs and derive a normalized measurement CSV."""

    if min_samples <= 0:
        raise ValueError("min_samples must be positive")
    if assay not in {"ephys", "imaging"}:
        raise ValueError("assay must be ephys or imaging")
    if time_mode not in TIME_MODES:
        raise ValueError(f"time_mode must be one of {sorted(TIME_MODES)}")
    if time_mode != "metadata" and (not math.isfinite(time_bin_seconds) or time_bin_seconds <= 0):
        raise ValueError("time_bin_seconds must be positive for binned time modes")
    metric_name = (metric_name or ("resting_membrane_potential" if assay == "ephys" else "mean_fluorescence")).strip()
    value_unit = (value_unit or ("mV" if assay == "ephys" else "AU")).strip()
    if not metric_name or not value_unit:
        raise ValueError("metric_name and value_unit must be nonempty")

    metadata_result = validate_metadata(metadata_path, assay=assay, stage=stage, provenance_root=provenance_root)
    raw_result = validate_raw_qc(raw_qc_path, assay=assay, check_files=check_files, metadata_path=metadata_path, provenance_root=provenance_root)
    base: dict[str, object] = {
        "assay": assay, "stage": stage, "metric_name": metric_name, "value_unit": value_unit,
        "min_samples": min_samples, "time_mode": time_mode,
        "time_bin_seconds": time_bin_seconds if time_mode != "metadata" else None,
        "metadata_gate": metadata_result, "raw_qc_gate": raw_result,
        "input_file_metadata": {"traces": _file_metadata(traces_path, provenance_root), "metadata": _file_metadata(metadata_path, provenance_root), "raw_qc": _file_metadata(raw_qc_path, provenance_root)},
        "issues": [], "warnings": [],
        "inference_warning": "Trace derivation is a deterministic measurement/QC step; it does not establish rhythmicity, channel identity, causality or statistical significance.",
    }
    if not check_files:
        base["warnings"].append({"type": "raw_hash_check_disabled", "message": "Raw-file existence/hash verification was explicitly disabled; derived output is provisional."})
    if metadata_result.get("status") != "verified_metadata":
        base["issues"].append({"type": "metadata_gate_failed", "status": metadata_result.get("status")})
    if raw_result.get("status") != "verified_raw_qc_provenance":
        base["issues"].append({"type": "raw_qc_gate_failed", "status": raw_result.get("status")})
    if base["issues"]:
        base["status"] = "blocked_trace_derivation"
        return base

    metadata_rows, metadata_fields = _read_rows(metadata_path)
    raw_rows, _ = _read_rows(raw_qc_path)
    trace_rows, trace_fields = _read_rows(traces_path)
    metadata_key = "metadata_row_id" if "metadata_row_id" in metadata_fields else "sample_id"
    metadata_by_id = {(row.get(metadata_key) or "").strip(): row for row in metadata_rows}
    raw_by_id = {(row.get("record_id") or "").strip(): row for row in raw_rows}
    pass_not_attached = [
        (row.get("record_id") or "").strip() for row in raw_rows
        if (row.get("qc_status") or "").strip().lower() == "pass"
        and (row.get("file_status") or "").strip().lower() != "present"
    ]
    if pass_not_attached:
        if check_files:
            base["issues"].append({"type": "pass_raw_file_not_present", "record_ids": sorted(pass_not_attached)})
        else:
            base["warnings"].append({"type": "pass_raw_file_not_present", "record_ids": sorted(pass_not_attached), "message": "Explicitly provisional because raw files are not attached."})
    required = {"record_id", "time_seconds", value_column}
    if assay == "imaging":
        required.add("roi_id")
    missing_columns = sorted(required - set(trace_fields))
    if missing_columns:
        base["issues"].append({"type": "trace_missing_columns", "columns": missing_columns})
        base["status"] = "blocked_trace_derivation"
        return base

    pass_records = {record_id for record_id, row in raw_by_id.items() if (row.get("qc_status") or "").strip().lower() == "pass"}
    values: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    seen_nonpass: set[str] = set()
    for line_number, row in enumerate(trace_rows, start=2):
        record_id = (row.get("record_id") or "").strip()
        if record_id not in pass_records:
            if record_id:
                seen_nonpass.add(record_id)
            base["warnings"].append({"line": line_number, "type": "nonpass_trace_ignored", "record_id": record_id})
            continue
        try:
            time_seconds = _finite(row.get("time_seconds"), "time_seconds")
            value = _finite(row.get(value_column), value_column)
        except ValueError as exc:
            base["issues"].append({"line": line_number, "type": "invalid_trace_value", "message": str(exc), "record_id": record_id})
            continue
        subunit = (row.get("roi_id") if assay == "imaging" else record_id) or ""
        subunit = subunit.strip()
        if assay == "imaging" and not subunit:
            base["issues"].append({"line": line_number, "type": "missing_roi_id", "record_id": record_id})
            continue
        values[(record_id, subunit)].append((time_seconds, value))

    output_rows: list[dict[str, str]] = []
    for record_id in sorted(pass_records):
        raw = raw_by_id[record_id]
        metadata_id = (raw.get("metadata_row_id") or "").strip()
        metadata = metadata_by_id.get(metadata_id)
        if metadata is None:
            base["issues"].append({"type": "metadata_row_not_found", "record_id": record_id, "metadata_row_id": metadata_id})
            continue
        try:
            metadata_time_hours = _circadian_hours((metadata.get("ZT_or_CT") or "").strip())
        except ValueError as exc:
            base["issues"].append({"type": "invalid_metadata_circadian_time", "record_id": record_id, "message": str(exc)})
            continue
        record_keys = sorted(key for key in values if key[0] == record_id)
        if not record_keys:
            base["issues"].append({"type": "pass_record_without_trace", "record_id": record_id})
            continue
        if assay == "imaging":
            expected_token = (raw.get("roi_count") or "").strip()
            try:
                expected_roi_count = int(expected_token)
            except ValueError:
                expected_roi_count = None
            if expected_roi_count is not None and expected_roi_count != len(record_keys):
                base["issues"].append({"type": "roi_count_mismatch", "record_id": record_id, "manifest_roi_count": expected_roi_count, "trace_roi_count": len(record_keys)})
        for key in record_keys:
            samples = values[key]
            times = [sample[0] for sample in samples]
            if time_mode == "metadata":
                bins = [(0.0, samples)]
            else:
                origin = min(times)
                binned: dict[int, list[tuple[float, float]]] = defaultdict(list)
                for time_seconds, value in samples:
                    index = int(math.floor((time_seconds - origin) / time_bin_seconds))
                    binned[index].append((time_seconds, value))
                bins = [(index * time_bin_seconds, binned[index]) for index in sorted(binned)]
            for bin_start, bin_samples in bins:
                if len(bin_samples) < min_samples:
                    base["issues"].append({"type": "trace_too_short", "record_id": record_id, "subunit_id": key[1], "time_bin_start_seconds": bin_start, "n_samples": len(bin_samples), "minimum": min_samples})
                    continue
                bin_times = [sample[0] for sample in bin_samples]
                elapsed_hours = bin_start / 3600.0
                if time_mode == "metadata":
                    output_time = metadata_time_hours
                    time_basis = "metadata_ZT_or_CT"
                    bin_label = ""
                elif time_mode == "elapsed":
                    output_time = elapsed_hours % 24.0
                    time_basis = "within_record_elapsed"
                    bin_label = f"{bin_start:g}"
                else:
                    output_time = (metadata_time_hours + elapsed_hours) % 24.0
                    time_basis = "metadata_ZT_or_CT_plus_elapsed"
                    bin_label = f"{bin_start:g}"
                output_rows.append({
                    "record_id": record_id,
                    "metadata_row_id": metadata_id,
                    "biological_replicate_id": (raw.get("biological_replicate_id") or "").strip(),
                    "time_hours": f"{output_time:g}",
                    "value": f"{_mean(sample[1] for sample in bin_samples):.12g}",
                    "metric_name": metric_name,
                    "value_unit": value_unit,
                    "subunit_id": key[1],
                    "n_trace_samples": str(len(bin_samples)),
                    "trace_duration_seconds": f"{max(bin_times) - min(bin_times):.12g}",
                    "time_basis": time_basis,
                    "time_bin_start_seconds": bin_label,
                })

    if base["issues"]:
        base["status"] = "blocked_trace_derivation"
        base["n_trace_rows"] = len(trace_rows)
        base["n_output_rows"] = 0
        return base

    if time_mode == "elapsed":
        base["warnings"].append({"type": "elapsed_time_not_circadian_anchored", "message": "Elapsed bins are not aligned to ZT/CT; do not compare phase across records without an explicit anchor."})
    elif time_mode == "metadata_plus_elapsed":
        base["warnings"].append({"type": "elapsed_time_anchored_to_metadata", "message": "Elapsed bins were added to metadata ZT/CT; verify trace start timing and lighting schedule before interpreting phase."})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_FIELDS))
        writer.writeheader()
        writer.writerows(output_rows)
    base.update({
        "status": "verified_trace_derivation", "n_trace_rows": len(trace_rows),
        "n_pass_records": len(pass_records), "n_output_rows": len(output_rows),
        "ignored_nonpass_record_ids": sorted(seen_nonpass), "output_file_metadata": _file_metadata(output_path, provenance_root),
    })
    return base


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--raw-qc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--provenance-root", type=Path, help="Root used to record portable relative provenance paths.")
    parser.add_argument("--assay", choices=("ephys", "imaging"), default="ephys")
    parser.add_argument("--stage", choices=("exploratory", "formal"), default="exploratory")
    parser.set_defaults(check_files=True)
    parser.add_argument("--check-files", dest="check_files", action="store_true", help="Verify raw-file existence and SHA-256 (default).")
    parser.add_argument("--no-check-files", dest="check_files", action="store_false", help="Explicitly allow provisional derivation without raw-file checks.")
    parser.add_argument("--value-column", default="value")
    parser.add_argument("--metric-name")
    parser.add_argument("--value-unit")
    parser.add_argument("--min-samples", type=int, default=4)
    parser.add_argument("--time-mode", choices=sorted(TIME_MODES), default="metadata")
    parser.add_argument("--time-bin-seconds", type=float, default=3600.0)
    args = parser.parse_args(argv[1:])
    try:
        result = derive(
            args.traces, args.metadata, args.raw_qc, args.output, args.report,
            assay=args.assay, stage=args.stage, check_files=args.check_files,
            value_column=args.value_column, metric_name=args.metric_name, value_unit=args.value_unit,
            min_samples=args.min_samples, time_mode=args.time_mode, time_bin_seconds=args.time_bin_seconds,
            provenance_root=args.provenance_root,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result.get("status") == "verified_trace_derivation" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


