#!/usr/bin/env python3
"""Prepare a biological-unit × time table and mixed-model specification."""

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

TIME_RE = re.compile(r"(?:ZT|CT)\s*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
MISSING = {
    "", "NA", "N/A", "NAN", "NULL", "NONE", "UNKNOWN", "NOT_REPORTED",
    "NOT SPECIFIED", "NOT_AVAILABLE", "NOT APPLICABLE", ".",
}
REQUIRED_COLUMNS = ["biological_replicate_id", "value"]
FORMAL_COVARIATES = ["batch_id", "sex", "age_days", "genotype", "temperature_C", "lighting"]
NUMERIC_COVARIATES = {"age_days", "temperature_C"}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _numeric_covariate_is_valid(column: str, value: str | None) -> bool:
    if column not in NUMERIC_COVARIATES or not _present(value):
        return _present(value)
    try:
        return math.isfinite(float(str(value).strip()))
    except (TypeError, ValueError):
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_metadata(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size_bytes": int(stat.st_size), "sha256": _sha256(path)}


def _parse_time(row: dict[str, str]) -> float:
    if _present(row.get("time_hours")):
        parsed = float(row["time_hours"])
    else:
        token = (row.get("time") or row.get("ZT_or_CT") or "").strip()
        match = TIME_RE.search(token)
        if not match:
            raise ValueError(f"row needs numeric time_hours or ZT/CT token: {row}")
        parsed = float(match.group(1))
    if not math.isfinite(parsed):
        raise ValueError(f"time_hours must be finite: {row}")
    return parsed % 24.0


def _load(path: Path, declared_unit: str | None) -> tuple[list[dict[str, object]], list[str], dict[str, int], dict[str, int]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in fields]
        if not ({"time_hours", "time", "ZT_or_CT"} & fields):
            missing_columns.append("time_hours/time/ZT_or_CT")
        if missing_columns:
            raise ValueError("missing required columns: " + ", ".join(missing_columns))
        rows: list[dict[str, object]] = []
        missing_covariates = defaultdict(int)
        invalid_covariates = defaultdict(int)
        for row_index, row in enumerate(reader):
            biological_id = (row.get("biological_replicate_id") or "").strip()
            if not biological_id:
                raise ValueError(f"biological_replicate_id is missing at row {row_index + 2}")
            try:
                time_hours = _parse_time(row)
                value = float(row["value"])
                if not math.isfinite(value):
                    raise ValueError("value must be finite")
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid row at {row_index + 2}: {row}") from exc
            unit = (row.get("experimental_unit") or "").strip() or (declared_unit or "").strip()
            for column in FORMAL_COVARIATES:
                raw = (row.get(column) or "").strip()
                if not _present(raw):
                    missing_covariates[column] += 1
                elif not _numeric_covariate_is_valid(column, raw):
                    invalid_covariates[column] += 1
            rows.append({
                "gene_symbol": (row.get("gene_symbol") or "").strip(),
                "cell_type": (row.get("cell_type") or "").strip(),
                "background": (row.get("background") or "").strip(),
                "biological_replicate_id": biological_id,
                "time_hours": time_hours,
                "value": value,
                "subunit_id": (row.get("subunit_id") or row.get("cell_id") or row.get("roi_id") or "").strip(),
                "experimental_unit": unit,
                **{column: (row.get(column) or "").strip() for column in FORMAL_COVARIATES},
            })
    return rows, list(reader.fieldnames or []), dict(sorted(missing_covariates.items())), dict(sorted(invalid_covariates.items()))


def prepare(path: Path, output_csv: Path, output_json: Path, declared_unit: str | None = None) -> dict[str, object]:
    rows, input_columns, missing_covariates, invalid_covariates = _load(path, declared_unit)
    input_metadata = _file_metadata(path)
    units = {str(row["experimental_unit"]) for row in rows}
    strata = sorted({(str(row["gene_symbol"]), str(row["cell_type"]), str(row["background"])) for row in rows})
    grouped: dict[tuple[str, str, str, str, float], list[dict[str, object]]] = defaultdict(list)
    metadata_values: dict[tuple[str, str, str, str, float], dict[str, str]] = {}
    metadata_conflicts: list[dict[str, object]] = []
    for row in rows:
        key = (str(row["gene_symbol"]), str(row["cell_type"]), str(row["background"]), str(row["biological_replicate_id"]), float(row["time_hours"]))
        grouped[key].append(row)
        values = {column: str(row[column]) for column in FORMAL_COVARIATES + ["experimental_unit"]}
        if key in metadata_values and metadata_values[key] != values:
            metadata_conflicts.append({"key": list(key), "first": metadata_values[key], "conflicting": values})
        metadata_values.setdefault(key, values)

    aggregated: list[dict[str, object]] = []
    for key, members in sorted(grouped.items()):
        gene_symbol, cell_type, background, biological_id, time_hours = key
        values = metadata_values[key]
        aggregated.append({
            "gene_symbol": gene_symbol,
            "cell_type": cell_type,
            "background": background,
            "biological_replicate_id": biological_id,
            "time_hours": time_hours,
            "value": sum(float(member["value"]) for member in members) / len(members),
            "n_subunits": len(members),
            **values,
        })

    biological_ids = sorted({str(row["biological_replicate_id"]) for row in aggregated})
    time_points = sorted({float(row["time_hours"]) for row in aggregated})
    biological_time_counts = defaultdict(int)
    for row in aggregated:
        stratum_key = (str(row["gene_symbol"]), str(row["cell_type"]), str(row["background"]), str(row["biological_replicate_id"]))
        biological_time_counts[stratum_key] += 1
    n_repeated_biological_replicates = sum(count > 1 for count in biological_time_counts.values())

    blocking_reasons: list[str] = []
    if len(units) != 1 or not units or not _present(next(iter(units), "")):
        blocking_reasons.append("experimental_unit_missing_or_mixed")
    if next(iter(units), "").lower().replace(" ", "_") in {"technical_replicate", "technical_replicate_id"}:
        blocking_reasons.append("technical_replicate_is_not_biological_unit")
    if len(strata) != 1:
        blocking_reasons.append("multiple_analysis_strata_split_input_before_modeling")
    if metadata_conflicts:
        blocking_reasons.append("metadata_conflict_within_biological_unit_time")
    missing_formal = sorted(column for column, count in missing_covariates.items() if count)
    if missing_formal:
        blocking_reasons.append("missing_formal_covariates")
    invalid_formal = sorted(column for column, count in invalid_covariates.items() if count)
    if invalid_formal:
        blocking_reasons.append("invalid_formal_covariates")
    if len(biological_ids) < 4:
        blocking_reasons.append("fewer_than_four_biological_replicates")
    if len(time_points) < 3:
        blocking_reasons.append("fewer_than_three_time_points")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_fields = ["gene_symbol", "cell_type", "background", "biological_replicate_id", "time_hours", "value", "n_subunits", "experimental_unit", *FORMAL_COVARIATES]
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(aggregated)
    output_metadata = _file_metadata(output_csv)

    result = {
        "status": "blocked_mixed_model_input" if blocking_reasons else "ready_for_mixed_model",
        "input_file": str(path),
        "input_file_metadata": input_metadata,
        "input_columns": input_columns,
        "output_table": str(output_csv),
        "output_table_metadata": output_metadata,
        "experimental_unit": next(iter(units), "unspecified") if len(units) == 1 else "mixed",
        "n_analysis_strata": len(strata),
        "analysis_strata": [{"gene_symbol": gene, "cell_type": cell, "background": background} for gene, cell, background in strata],
        "n_raw_observations": len(rows),
        "n_aggregated_unit_time_means": len(aggregated),
        "n_biological_replicates": len(biological_ids),
        "n_repeated_biological_replicates": n_repeated_biological_replicates,
        "n_unique_time_points": len(time_points),
        "missing_covariate_counts": missing_covariates,
        "invalid_covariate_counts": invalid_covariates,
        "metadata_conflicts": metadata_conflicts,
        "blocking_reasons": blocking_reasons,
        "model_specification": {
            "analysis_stratum": "one gene_symbol × cell_type × background per model input",
            "fixed_effects": ["intercept", "cos(2*pi*time_hours/24)", "sin(2*pi*time_hours/24)", *FORMAL_COVARIATES],
            "random_effects": ["1 | biological_replicate_id"] if n_repeated_biological_replicates else [],
            "random_effect_note": "Random intercept is estimable only when biological replicates contribute repeated aggregated observations within one analysis stratum; otherwise use biological replicate as the independent unit without a random intercept.",
            "aggregation": "mean within gene_symbol × cell_type × background × biological_replicate_id × time_hours",
            "period_hours": 24.0,
            "note": "Specification only; fit in a supported mixed-effects runtime and pre-register contrasts/QC before formal claims.",
        },
    }
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--experimental-unit")
    parser.add_argument("--output-table", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        result = prepare(args.input, args.output_table, args.output_json, args.experimental_unit)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ["status", "n_raw_observations", "n_aggregated_unit_time_means", "n_biological_replicates", "n_unique_time_points", "blocking_reasons"]}, ensure_ascii=False))
    return 0 if result["status"] == "ready_for_mixed_model" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
