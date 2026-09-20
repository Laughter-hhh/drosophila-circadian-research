#!/usr/bin/env python3
"""Run a provenance-aware, descriptive cosinor fit on a verified data bundle.

The input bundle must contain experiment metadata, a raw-QC manifest and a
derived measurement table. Measurements are averaged within biological
replicate and time point before fitting, so repeated technical measurements do
not silently receive extra weight. This is an exploratory summary only; it
does not provide animal-level inference or a causal claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_circadian_timeseries import analyze_rows
from scripts.validate_preanalysis_bundle import validate_bundle


DEFAULT_GROUP_BY = ("cell_type", "genotype")
MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_AVAILABLE", "NOT_APPLICABLE", "NOT_REPORTED", "."}
CONDITION_FIELD_ALIASES = {
    "treatment", "condition", "drug", "compound", "blocker", "concentration",
    "dose", "vehicle", "rnai", "effector", "activation", "stimulation",
    "light_stimulation", "temperature_shift", "genetic_background", "background",
}


def _present(value: object) -> bool:
    return str(value or "").strip().upper() not in MISSING


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("cannot average an empty value list")
    return sum(values) / len(values)


def _group_label(group_by: Sequence[str], key: tuple[str, ...]) -> dict[str, str]:
    return {field: value for field, value in zip(group_by, key)}


def _as_number(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite: {value!r}")
    return number


def _condition_fields(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> list[str]:
    """Find condition columns with labels, without silently pooling them."""
    seen: set[str] = set()
    found: list[str] = []
    aliases = {value.lower() for value in CONDITION_FIELD_ALIASES}
    for field in fields:
        if field.lower() in aliases and field not in seen and any(_present(row.get(field)) for row in rows):
            seen.add(field)
            found.append(field)
    return found


def _blocked(assay: str, stage: str, bundle: dict[str, object], issues: list[dict[str, object]], message: str) -> dict[str, object]:
    return {
        "status": "blocked_preanalysis_cosinor",
        "assay": assay,
        "stage": stage,
        "bundle_gate": bundle,
        "issues": issues,
        "inference_warning": message,
    }


def analyze_bundle(
    metadata_path: Path,
    raw_qc_path: Path,
    measurements_path: Path,
    *,
    assay: str = "ephys",
    stage: str = "exploratory",
    check_files: bool = True,
    period_hours: float = 24.0,
    time_system: str = "unknown",
    group_by: Sequence[str] = DEFAULT_GROUP_BY,
    metric_name: str | None = None,
    min_observations: int = 4,
    min_unique_times: int = 3,
    provenance_root: Path | None = None,
) -> dict[str, object]:
    """Validate a bundle and return group-level descriptive cosinor results."""

    if period_hours <= 0:
        raise ValueError("period_hours must be positive")
    if min_observations < 4:
        raise ValueError("min_observations must be at least four")
    if min_unique_times < 3:
        raise ValueError("min_unique_times must be at least three")
    group_by = tuple(field.strip() for field in group_by if field.strip())
    if not group_by:
        raise ValueError("group_by must contain at least one metadata column")

    bundle = validate_bundle(
        metadata_path,
        raw_qc_path,
        measurements_path,
        assay=assay,
        stage=stage,
        check_files=check_files,
        provenance_root=provenance_root,
    )
    if bundle.get("status") != "verified_preanalysis_bundle":
        return _blocked(assay, stage, bundle, [{"type": "preanalysis_bundle_gate_failed"}], "No fit was attempted because the metadata/raw-QC/measurement provenance gate failed.")
    if stage == "formal":
        return {
            "status": "blocked_formal_cosinor_requires_mixed_model",
            "assay": assay,
            "stage": stage,
            "bundle_gate": bundle,
            "issues": [{"type": "formal_inference_backend_unavailable"}],
            "inference_warning": "The bundle is valid, but this script is descriptive only. Use a biological-unit-aware mixed-effects backend for formal inference.",
        }
    normalized_time_system = time_system.strip().upper()
    if normalized_time_system in {"", "UNKNOWN", "UNSPECIFIED"}:
        return _blocked(assay, stage, bundle, [{"type": "time_system_unspecified", "message": "Pass --time-system (for example ZT or CT) before fitting or interpreting phase."}], "No fit was attempted because the circadian time system was not specified.")

    metadata_rows, metadata_fields = _read_rows(metadata_path)
    raw_rows, raw_fields = _read_rows(raw_qc_path)
    measurement_rows, measurement_fields = _read_rows(measurements_path)
    metadata_key = "metadata_row_id" if "metadata_row_id" in metadata_fields else "sample_id"
    metadata_by_id: dict[str, dict[str, str]] = {}
    raw_by_id: dict[str, dict[str, str]] = {}
    issues: list[dict[str, object]] = []
    for line_number, row in enumerate(metadata_rows, start=2):
        key = (row.get(metadata_key) or "").strip()
        if not key:
            issues.append({"line": line_number, "type": "metadata_missing_join_key", "field": metadata_key})
        elif key in metadata_by_id:
            issues.append({"line": line_number, "type": "duplicate_metadata_join_key", "field": metadata_key, "value": key})
        else:
            metadata_by_id[key] = row
    for line_number, row in enumerate(raw_rows, start=2):
        key = (row.get("record_id") or "").strip()
        if not key:
            issues.append({"line": line_number, "type": "raw_qc_missing_record_id"})
        elif key in raw_by_id:
            issues.append({"line": line_number, "type": "duplicate_raw_qc_record_id", "record_id": key})
        else:
            raw_by_id[key] = row
    warnings: list[dict[str, object]] = []
    if not check_files:
        warnings.append({"type": "raw_hash_check_disabled", "message": "Raw-file existence/hash verification was explicitly disabled; downstream results are provisional."})
    pass_raw_not_present = [
        (row.get("record_id") or "").strip() for row in raw_rows
        if (row.get("qc_status") or "").strip().lower() == "pass"
        and (row.get("file_status") or "").strip().lower() != "present"
    ]
    if pass_raw_not_present:
        issues.append({"type": "pass_raw_file_not_present", "record_ids": sorted(pass_raw_not_present)})
    missing_group_columns = [field for field in group_by if field not in metadata_fields]
    if missing_group_columns:
        issues.append({"type": "metadata_missing_group_columns", "columns": missing_group_columns})
    missing_analysis_columns = [field for field in ("time_hours", "value") if field not in measurement_fields]
    if missing_analysis_columns:
        issues.append({"type": "measurement_missing_analysis_columns", "columns": missing_analysis_columns})
    condition_fields = _condition_fields(
        metadata_rows + raw_rows + measurement_rows,
        list(metadata_fields) + list(raw_fields) + list(measurement_fields),
    )
    ungrouped_conditions = [field for field in condition_fields if field not in group_by]
    if ungrouped_conditions:
        issues.append({"type": "condition_fields_not_grouped", "columns": ungrouped_conditions, "group_by": list(group_by)})

    missing_metric_rows = sum(1 for row in measurement_rows if not _present(row.get("metric_name")))
    observed_metrics = sorted({(row.get("metric_name") or "").strip() for row in measurement_rows if _present(row.get("metric_name"))})
    selected_metric = (metric_name or "").strip()
    if selected_metric:
        if missing_metric_rows:
            issues.append({"type": "metric_name_missing_rows", "n_rows": missing_metric_rows, "requested_metric": selected_metric})
        elif selected_metric not in observed_metrics:
            issues.append({"type": "requested_metric_not_found", "metric_name": selected_metric, "available_metrics": observed_metrics})
    elif len(observed_metrics) > 1:
        issues.append({"type": "multiple_metrics_unspecified", "metric_names": observed_metrics})
    elif observed_metrics and missing_metric_rows:
        issues.append({"type": "metric_name_missing_rows", "n_rows": missing_metric_rows, "available_metrics": observed_metrics})
    else:
        selected_metric = observed_metrics[0] if observed_metrics else "unspecified"
        if selected_metric == "unspecified":
            warnings.append({"type": "metric_name_unspecified", "message": "Add metric_name before interpreting a biological effect."})

    observed_units = sorted({(row.get("value_unit") or "").strip() for row in measurement_rows if _present(row.get("value_unit"))})
    missing_unit_rows = sum(1 for row in measurement_rows if not _present(row.get("value_unit")))
    value_unit = observed_units[0] if len(observed_units) == 1 else "unspecified"
    if len(observed_units) > 1:
        issues.append({"type": "multiple_value_units_unspecified", "value_units": observed_units})
    elif observed_units and missing_unit_rows:
        issues.append({"type": "value_unit_missing_rows", "n_rows": missing_unit_rows, "available_units": observed_units})
    elif not observed_units:
        warnings.append({"type": "value_unit_unspecified", "metric_name": selected_metric})

    if issues:
        return _blocked(assay, stage, bundle, issues, "No fit was attempted because analysis fields or condition labels were incomplete or ambiguous.")

    # Anti-pseudoreplication boundary: technical repeats are averaged within
    # biological replicate × time before the fixed-period fit.
    grouped: dict[tuple[str, ...], dict[tuple[str, float], list[float]]] = defaultdict(lambda: defaultdict(list))
    for line_number, row in enumerate(measurement_rows, start=2):
        row_metric = (row.get("metric_name") or "").strip() or "unspecified"
        if row_metric != selected_metric:
            continue
        record_id = (row.get("record_id") or "").strip()
        metadata_id = (row.get("metadata_row_id") or "").strip()
        raw = raw_by_id.get(record_id)
        metadata = metadata_by_id.get(metadata_id)
        if raw is None or metadata is None:
            issues.append({"line": line_number, "type": "analysis_join_failed", "record_id": record_id, "metadata_row_id": metadata_id})
            continue
        biological_id = (row.get("biological_replicate_id") or "").strip()
        if not biological_id:
            issues.append({"line": line_number, "type": "missing_biological_replicate_id", "record_id": record_id})
            continue
        try:
            time_hours = _as_number(row.get("time_hours"), "time_hours")
            value = _as_number(row.get("value"), "value")
        except ValueError as exc:
            issues.append({"line": line_number, "type": "nonfinite_or_non_numeric_measurement", "message": str(exc)})
            continue
        key = tuple((metadata.get(field) or row.get(field) or "").strip() for field in group_by)
        grouped[key][(biological_id, time_hours)].append(value)

    if issues:
        return _blocked(assay, stage, bundle, issues, "No fit was attempted because a selected measurement was malformed or could not be joined.")

    results: list[dict[str, object]] = []
    n_fit_groups = 0
    n_insufficient_groups = 0
    for key in sorted(grouped):
        cell_means = grouped[key]
        averaged_rows = [
            {"subject_id": biological_id, "time_hours": str(time_hours), "value": str(_mean(values))}
            for (biological_id, time_hours), values in sorted(cell_means.items())
        ]
        n_subjects = len({row["subject_id"] for row in averaged_rows})
        n_unique_times = len({float(row["time_hours"]) for row in averaged_rows})
        span_by_subject: dict[str, set[float]] = defaultdict(set)
        for row in averaged_rows:
            span_by_subject[row["subject_id"]].add(float(row["time_hours"]))
        design = "longitudinal" if any(len(times) >= min_unique_times for times in span_by_subject.values()) else "cross_sectional"
        technical_measurements = sum(len(values) for values in cell_means.values())
        group_result: dict[str, object] = {
            "group": _group_label(group_by, key),
            "metric_name": selected_metric,
            "value_unit": value_unit,
            "status": "insufficient_time_coverage",
            "design": design,
            "n_biological_replicates": n_subjects,
            "n_aggregated_observations": len(averaged_rows),
            "n_unique_time_points": n_unique_times,
            "n_technical_measurements": technical_measurements,
            "minimum_required_observations": min_observations,
            "minimum_required_unique_time_points": min_unique_times,
        }
        if len(averaged_rows) >= min_observations and n_unique_times >= min_unique_times:
            fit = analyze_rows(averaged_rows, period_hours=period_hours, time_system=time_system)
            group_result.update(fit)
            group_result["status"] = "exploratory_descriptive_fit"
            n_fit_groups += 1
            if design == "cross_sectional":
                group_result["design_warning"] = "Each biological replicate contributes fewer than the minimum time points; this is a cross-sectional descriptive fit, not within-animal rhythm evidence."
                warnings.append({"type": "cross_sectional_group", "group": _group_label(group_by, key)})
        else:
            n_insufficient_groups += 1
            group_result["insufficient_reason"] = "Need at least the configured number of aggregated observations and unique time points."
            warnings.append({"type": "insufficient_group_time_coverage", "group": _group_label(group_by, key)})
        results.append(group_result)

    return {
        "status": "verified_exploratory_bundle_cosinor",
        "analysis_status": "executed_exploratory",
        "input_gate": "verified_preanalysis_bundle",
        "scientific_status": "exploratory_not_verified",
        "formal_status": "blocked_requires_mixed_model",
        "assay": assay,
        "stage": stage,
        "period_hours": period_hours,
        "time_system": normalized_time_system,
        "group_by": list(group_by),
        "metric_name": selected_metric,
        "value_unit": value_unit,
        "n_groups": len(results),
        "n_fit_groups": n_fit_groups,
        "n_insufficient_groups": n_insufficient_groups,
        "groups": results,
        "warnings": warnings,
        "bundle_gate": bundle,
        "inference_warning": "Descriptive fixed-period fits only. Technical repeats were averaged within biological replicate and time; no p-values, multiple-testing correction, causal inference or biological-unit-aware mixed-effects result is produced.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--raw-qc", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--assay", choices=("ephys", "imaging"), default="ephys")
    parser.add_argument("--stage", choices=("exploratory", "formal"), default="exploratory")
    parser.set_defaults(check_files=True)
    parser.add_argument("--check-files", dest="check_files", action="store_true", help="Verify raw-file existence and SHA-256 (default).")
    parser.add_argument("--no-check-files", dest="check_files", action="store_false", help="Explicitly disable raw-file checks; output carries a provisional warning.")
    parser.add_argument("--period-hours", type=float, default=24.0)
    parser.add_argument("--time-system", default="unknown")
    parser.add_argument("--group-by", default=",".join(DEFAULT_GROUP_BY), help="Comma-separated metadata fields, default: cell_type,genotype")
    parser.add_argument("--metric-name")
    parser.add_argument("--min-observations", type=int, default=4)
    parser.add_argument("--min-unique-times", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance-root", type=Path, help="Root used to record portable relative provenance paths.")
    args = parser.parse_args(argv[1:])
    try:
        result = analyze_bundle(
            args.metadata,
            args.raw_qc,
            args.measurements,
            assay=args.assay,
            stage=args.stage,
            check_files=args.check_files,
            period_hours=args.period_hours,
            time_system=args.time_system,
            group_by=args.group_by.split(","),
            metric_name=args.metric_name,
            min_observations=args.min_observations,
            min_unique_times=args.min_unique_times,
            provenance_root=args.provenance_root,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_exploratory_bundle_cosinor" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


