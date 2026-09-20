#!/usr/bin/env python3
"""Run exploratory cluster-permutation/bootstrap cosinor on a verified bundle.

This wrapper adds metadata/raw-QC/measurement provenance to the dependency-
light nested cosinor implementation. It rejects unspecified mixtures of
metrics, value units, condition labels or time systems and delegates the
inferential calculation only after technical/subunit observations have been
linked to a biological replicate and time point.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_nested_cosinor import _analyze_group, _bh_adjust
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


def _number(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite: {value!r}")
    return number


def _condition_fields(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> list[str]:
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
        "status": "blocked_preanalysis_nested_cosinor",
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
    time_system: str = "unknown",
    group_by: Sequence[str] = DEFAULT_GROUP_BY,
    metric_name: str | None = None,
    n_permutations: int = 1000,
    n_bootstrap: int = 1000,
    seed: int = 20260906,
) -> dict[str, object]:
    """Validate a bundle and calculate cluster-aware exploratory summaries."""

    if n_permutations <= 0 or n_bootstrap <= 0:
        raise ValueError("n_permutations and n_bootstrap must be positive")
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
    )
    if bundle.get("status") != "verified_preanalysis_bundle":
        return _blocked(assay, stage, bundle, [{"type": "preanalysis_bundle_gate_failed"}], "No cluster calculation was attempted because the metadata/raw-QC/measurement provenance gate failed.")
    if stage == "formal":
        return {
            "status": "blocked_formal_nested_cosinor_requires_mixed_model",
            "assay": assay,
            "stage": stage,
            "bundle_gate": bundle,
            "issues": [{"type": "formal_inference_backend_unavailable"}],
            "inference_warning": "The bundle is valid, but this cluster permutation/bootstrap path is exploratory and cannot replace a pre-specified formal mixed-effects model.",
        }
    normalized_time_system = time_system.strip().upper()
    if normalized_time_system in {"", "UNKNOWN", "UNSPECIFIED"}:
        return _blocked(assay, stage, bundle, [{"type": "time_system_unspecified", "message": "Pass --time-system (for example ZT or CT) before fitting or interpreting phase."}], "No cluster calculation was attempted because the circadian time system was not specified.")

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
    required_measurement_columns = [field for field in ("record_id", "metadata_row_id", "biological_replicate_id", "time_hours", "value") if field not in measurement_fields]
    if required_measurement_columns:
        issues.append({"type": "measurement_missing_columns", "columns": required_measurement_columns})
    condition_fields = _condition_fields(
        metadata_rows + raw_rows + measurement_rows,
        list(metadata_fields) + list(raw_fields) + list(measurement_fields),
    )
    ungrouped_conditions = [field for field in condition_fields if field not in group_by]
    if ungrouped_conditions:
        issues.append({"type": "condition_fields_not_grouped", "columns": ungrouped_conditions, "group_by": list(group_by)})
    if issues:
        return _blocked(assay, stage, bundle, issues, "No cluster calculation was attempted because required grouping, condition or measurement columns were incomplete.")

    missing_metric_rows = sum(1 for row in measurement_rows if not _present(row.get("metric_name")))
    observed_metrics = sorted({(row.get("metric_name") or "").strip() for row in measurement_rows if _present(row.get("metric_name"))})
    selected_metric = (metric_name or "").strip()
    if selected_metric:
        if missing_metric_rows:
            return _blocked(assay, stage, bundle, [{"type": "metric_name_missing_rows", "n_rows": missing_metric_rows, "requested_metric": selected_metric}], "Rows without a readout label cannot be silently assigned to the requested metric; label or remove them explicitly.")
        if selected_metric not in observed_metrics:
            return _blocked(assay, stage, bundle, [{"type": "requested_metric_not_found", "metric_name": selected_metric, "available_metrics": observed_metrics}], "No cluster calculation was attempted because the requested readout is absent.")
    elif len(observed_metrics) > 1:
        return _blocked(assay, stage, bundle, [{"type": "multiple_metrics_unspecified", "metric_names": observed_metrics}], "Different readouts cannot be pooled silently; select one with --metric-name or provide separate bundles.")
    elif observed_metrics and missing_metric_rows:
        return _blocked(assay, stage, bundle, [{"type": "metric_name_missing_rows", "n_rows": missing_metric_rows, "available_metrics": observed_metrics}], "Rows without a readout label cannot be silently dropped or assigned to the named metric.")
    else:
        selected_metric = observed_metrics[0] if observed_metrics else "unspecified"
        if selected_metric == "unspecified":
            warnings.append({"type": "metric_name_unspecified", "message": "Add metric_name before interpreting a biological effect."})

    selected_rows: list[dict[str, object]] = []
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
        try:
            time_hours = _number(row.get("time_hours"), "time_hours") % 24.0
            value = _number(row.get("value"), "value")
        except ValueError as exc:
            issues.append({"line": line_number, "type": "invalid_measurement", "message": str(exc)})
            continue
        if not biological_id:
            issues.append({"line": line_number, "type": "missing_biological_replicate_id"})
            continue
        value_unit = (row.get("value_unit") or "").strip() or "unspecified"
        subunit_id = (row.get("subunit_id") or row.get("roi_id") or row.get("cell_id") or row.get("technical_replicate_id") or record_id).strip()
        selected_rows.append({
            "biological_replicate_id": biological_id,
            "time_hours": time_hours,
            "value": value,
            "subunit_id": subunit_id,
            "experimental_unit": (metadata.get("experimental_unit") or "").strip(),
            "value_unit": value_unit,
            "record_id": record_id,
            "group_key": tuple((metadata.get(field) or row.get(field) or "").strip() for field in group_by),
        })
    if issues:
        return _blocked(assay, stage, bundle, issues, "No cluster calculation was attempted because a selected measurement could not be joined or parsed.")

    units = sorted({str(row["value_unit"]) for row in selected_rows})
    if len(units) > 1:
        return _blocked(assay, stage, bundle, [{"type": "multiple_value_units_unspecified", "metric_name": selected_metric, "value_units": units}], "Different physical units cannot be pooled; split the readout or convert it with an auditable rule.")
    value_unit = units[0] if units else "unspecified"
    if value_unit == "unspecified":
        warnings.append({"type": "value_unit_unspecified", "metric_name": selected_metric})

    grouped: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in selected_rows:
        grouped[tuple(row["group_key"])].append(row)

    results: list[dict[str, object]] = []
    inferential_indices: list[int] = []
    p_values: list[float] = []
    for index, key in enumerate(sorted(grouped)):
        group_result = _analyze_group(grouped[key], random.Random(seed + index), n_permutations, n_bootstrap)
        group_result.update({"group": {field: value for field, value in zip(group_by, key)}, "metric_name": selected_metric, "value_unit": value_unit})
        results.append(group_result)
        if group_result.get("status") == "exploratory_nested_cosinor":
            inferential_indices.append(len(results) - 1)
            p_values.append(float(group_result["p_amplitude_permutation"]))
    q_values = _bh_adjust(p_values)
    for index, q_value in zip(inferential_indices, q_values):
        results[index]["q_amplitude_bh"] = q_value

    return {
        "status": "verified_exploratory_bundle_nested_cosinor",
        "analysis_status": "executed_exploratory",
        "input_gate": "verified_preanalysis_bundle",
        "scientific_status": "exploratory_not_verified",
        "formal_status": "blocked_requires_mixed_model",
        "assay": assay,
        "stage": stage,
        "time_system": normalized_time_system,
        "method": "fixed 24-hour cosinor on biological-unit × time means + within-unit time permutation + biological-unit cluster bootstrap",
        "seed": seed,
        "n_permutations": n_permutations,
        "n_bootstrap": n_bootstrap,
        "group_by": list(group_by),
        "metric_name": selected_metric,
        "value_unit": value_unit,
        "n_selected_measurements": len(selected_rows),
        "n_groups": len(results),
        "groups": results,
        "warnings": warnings,
        "bundle_gate": bundle,
        "inference_warning": "Exploratory cluster permutation/bootstrap only; technical/subunit rows are aggregated within biological replicate × time. This does not replace a pre-specified mixed-effects model or establish causality.",
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
    parser.add_argument("--time-system", default="unknown")
    parser.add_argument("--group-by", default=",".join(DEFAULT_GROUP_BY))
    parser.add_argument("--metric-name")
    parser.add_argument("--n-permutations", type=int, default=1000)
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        result = analyze_bundle(
            args.metadata,
            args.raw_qc,
            args.measurements,
            assay=args.assay,
            stage=args.stage,
            check_files=args.check_files,
            time_system=args.time_system,
            group_by=args.group_by.split(","),
            metric_name=args.metric_name,
            n_permutations=args.n_permutations,
            n_bootstrap=args.n_bootstrap,
            seed=args.seed,
        )
    except (OSError, UnicodeDecodeError, ValueError, StopIteration) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_exploratory_bundle_nested_cosinor" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
