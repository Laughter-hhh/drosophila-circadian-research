#!/usr/bin/env python3
"""Prepare explicit transcript and gene-sample tables from ESAT-style GEO matrices.

The adapter expects matrices with transcript ID in column 1, gene symbol in
column 2, and expression samples in the remaining columns. It does not
normalize values or infer aliases. Optional symbol aliases must be supplied in
a source-documented CSV. Transcript rows are preserved, and gene-level
aggregation is emitted as separate, explicitly labelled sensitivity tables.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_esat_candidate_sample_keys import _read_aliases


AGGREGATIONS = ("sum", "median", "max")
TIME_RE = re.compile(r"^\s*(ZT|CT)\s*(-?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
_MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NOT_AVAILABLE", "NOT AVAILABLE", "NONE REPORTED", "."}


def _path_key(value: str | Path) -> str:
    raw = str(value).strip().replace("\\", "/")
    return str(PurePosixPath(raw))


def _open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_candidates(path: Path, candidate_column: str, priority_column: str | None) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        if candidate_column not in fields:
            raise ValueError(f"candidate list is missing column {candidate_column!r}")
        if priority_column and priority_column not in fields:
            raise ValueError(f"candidate list is missing priority column {priority_column!r}")
        rows = list(reader)
    if not rows:
        raise ValueError("candidate list contains no data rows")
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        symbol = (row.get(candidate_column) or "").strip()
        key = symbol.casefold()
        if not symbol:
            raise ValueError(f"blank candidate symbol at row {row_number}")
        if key in seen:
            raise ValueError(f"duplicate or case-ambiguous candidate symbol at row {row_number}: {symbol!r}")
        seen.add(key)
        candidates.append({
            "gene_symbol": symbol,
            "priority_class": (row.get(priority_column) or "").strip() if priority_column else "",
        })
    return candidates


def _read_metadata(path: Path) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, list[str]]]:
    required = {
        "matrix_path", "sample_id", "geo_accession", "cell_type",
        "ZT_or_CT", "time_hours", "time_system", "timecourse_id",
    }
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"sample metadata is missing required columns: {', '.join(sorted(missing))}")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError("sample metadata contains no rows")

    by_key: dict[tuple[str, str], dict[str, str]] = {}
    samples_by_matrix: dict[str, list[str]] = defaultdict(list)
    for row_number, row in enumerate(rows, start=2):
        matrix = _path_key(row["matrix_path"])
        sample = row["sample_id"]
        if not matrix or not sample:
            raise ValueError(f"blank matrix_path or sample_id in metadata row {row_number}")
        key = (matrix, sample)
        if key in by_key:
            raise ValueError(f"duplicate sample metadata key at row {row_number}: {key}")
        match = TIME_RE.fullmatch(row["ZT_or_CT"])
        if not match:
            raise ValueError(f"invalid ZT_or_CT token in metadata row {row_number}: {row['ZT_or_CT']!r}")
        observed_system = match.group(1).upper()
        declared_system = row["time_system"].upper()
        if declared_system not in {"ZT", "CT"} or observed_system != declared_system:
            raise ValueError(f"time-system mismatch in metadata row {row_number}: token={observed_system}, declared={declared_system}")
        try:
            token_hours = float(match.group(2)) % 24.0
            mapped_hours = float(row["time_hours"]) % 24.0
        except ValueError as exc:
            raise ValueError(f"non-numeric time_hours in metadata row {row_number}") from exc
        if not math.isfinite(token_hours) or not math.isfinite(mapped_hours) or not math.isclose(token_hours, mapped_hours, abs_tol=1e-6):
            raise ValueError(f"time_hours does not agree with ZT_or_CT in metadata row {row_number}")
        if not row["geo_accession"] or not row["cell_type"] or not row["timecourse_id"]:
            raise ValueError(f"metadata row {row_number} lacks GEO accession, cell_type, or timecourse_id")
        by_key[key] = row
        samples_by_matrix[matrix].append(sample)
    return by_key, dict(samples_by_matrix)


def _matrix_spec(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    label, path = label.strip(), path.strip()
    if not separator or not label or not path:
        raise ValueError("--matrix must use CELLTYPE=PATH")
    return label, Path(path)


def _map_symbol(matrix_symbol: str, candidate_by_key: dict[str, str], aliases: dict[str, str]) -> tuple[str | None, str]:
    key = matrix_symbol.strip().casefold()
    direct = candidate_by_key.get(key)
    if direct is not None:
        return direct, "exact_symbol_match" if matrix_symbol.strip() == direct else "casefold_symbol_match"
    if key in aliases:
        return aliases[key], "explicit_alias_map"
    return None, "unmatched"


def _validate_matrix_metadata(
    label: str,
    matrix_path: Path,
    sample_columns: list[str],
    metadata: dict[tuple[str, str], dict[str, str]],
    samples_by_matrix: dict[str, list[str]],
) -> list[dict[str, str]]:
    path_key = _path_key(matrix_path)
    expected_samples = samples_by_matrix.get(path_key, [])
    if not expected_samples:
        raise ValueError(f"no audited sample metadata rows for matrix path {path_key!r}")
    if len(sample_columns) != len(set(sample_columns)):
        raise ValueError(f"duplicate sample-column labels in {path_key}")
    if set(sample_columns) != set(expected_samples):
        missing = [sample for sample in sample_columns if sample not in expected_samples]
        extra = [sample for sample in expected_samples if sample not in sample_columns]
        raise ValueError(f"matrix/metadata sample mismatch for {path_key}; unmapped={missing}, unused_metadata={extra}")
    rows: list[dict[str, str]] = []
    for sample in sample_columns:
        row = metadata[(path_key, sample)]
        if row["cell_type"].casefold() != label.casefold():
            raise ValueError(f"matrix label {label!r} conflicts with mapped cell_type {row['cell_type']!r} for sample {sample}")
        rows.append(row)
    return rows


def prepare_esat_candidate_expression(
    matrix_specs: list[tuple[str, Path]],
    metadata_path: Path,
    candidates_path: Path,
    candidate_column: str = "gene_symbol",
    priority_column: str | None = None,
    alias_path: Path | None = None,
) -> dict[str, Any]:
    if not matrix_specs:
        raise ValueError("at least one --matrix CELLTYPE=PATH is required")
    labels = [label.casefold() for label, _ in matrix_specs]
    paths = [_path_key(path) for _, path in matrix_specs]
    if len(labels) != len(set(labels)):
        raise ValueError("matrix labels must be unique")
    if len(paths) != len(set(paths)):
        raise ValueError("matrix paths must be unique")

    candidates = _read_candidates(candidates_path, candidate_column, priority_column)
    candidate_by_key = {row["gene_symbol"].casefold(): row["gene_symbol"] for row in candidates}
    aliases = _read_aliases(alias_path, [row["gene_symbol"] for row in candidates])
    metadata, samples_by_matrix = _read_metadata(metadata_path)

    transcript_rows: list[dict[str, Any]] = []
    values: dict[tuple[str, str, str], list[tuple[str, str, float, str]]] = defaultdict(list)
    candidate_features: dict[tuple[str, str], dict[str, Any]] = {}
    matrix_audits: list[dict[str, Any]] = []
    matrix_keys = {_path_key(path) for _, path in matrix_specs}
    orphan_metadata = sorted(set(samples_by_matrix) - matrix_keys)
    if orphan_metadata:
        raise ValueError(f"metadata contains matrices not declared on the command line: {orphan_metadata}")

    for label, matrix_path in matrix_specs:
        if not matrix_path.is_file():
            raise ValueError(f"ESAT matrix does not exist: {matrix_path}")
        path_key = _path_key(matrix_path)
        with _open_text(matrix_path) as stream:
            reader = csv.reader(stream, delimiter="\t")
            header = next(reader, None)
            if not header or len(header) < 3 or header[0].strip().casefold() != "symbol":
                raise ValueError(f"ESAT matrix header must start with transcript ID in a 'Symbol' column: {matrix_path}")
            sample_columns = [column.strip() for column in header[2:]]
            if any(not sample for sample in sample_columns):
                raise ValueError(f"blank sample-column label in {matrix_path}")
            mapped_metadata = _validate_matrix_metadata(label, matrix_path, sample_columns, metadata, samples_by_matrix)
            rows_seen = 0
            transcript_ids_seen: set[tuple[str, str]] = set()
            matched_rows = 0
            for line_number, row in enumerate(reader, start=2):
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue
                if len(row) != len(header):
                    raise ValueError(f"row {line_number} has {len(row)} fields in {matrix_path}; expected {len(header)}")
                rows_seen += 1
                transcript_id = row[0].strip()
                matrix_symbol = row[1].strip()
                canonical, match_mode = _map_symbol(matrix_symbol, candidate_by_key, aliases)
                if canonical is None:
                    continue
                if not transcript_id:
                    raise ValueError(f"blank transcript ID for candidate {canonical!r} at {matrix_path}:{line_number}")
                transcript_key = (canonical, transcript_id)
                if transcript_key in transcript_ids_seen:
                    raise ValueError(f"duplicate candidate transcript ID {transcript_id!r} for {canonical!r} in {matrix_path}")
                transcript_ids_seen.add(transcript_key)
                try:
                    expression_values = [float(token) for token in row[2:]]
                except ValueError as exc:
                    raise ValueError(f"non-numeric candidate expression for {canonical!r}/{transcript_id} at {matrix_path}:{line_number}") from exc
                if any(not math.isfinite(value) for value in expression_values):
                    raise ValueError(f"non-finite candidate expression for {canonical!r}/{transcript_id} at {matrix_path}:{line_number}")
                matched_rows += 1
                feature = candidate_features.setdefault((label, canonical), {
                    "matrix_symbols": set(),
                    "transcript_ids": set(),
                    "match_modes": defaultdict(int),
                })
                feature["matrix_symbols"].add(matrix_symbol)
                feature["transcript_ids"].add(transcript_id)
                feature["match_modes"][match_mode] += 1
                for sample, meta, value in zip(sample_columns, mapped_metadata, expression_values):
                    values[(label, canonical, sample)].append((transcript_id, matrix_symbol, value, match_mode))
                    transcript_rows.append({
                        "gene_symbol": canonical,
                        "matrix_symbol": matrix_symbol,
                        "symbol_match_mode": match_mode,
                        "transcript_id": transcript_id,
                        "sample_id": sample,
                        "geo_accession": meta["geo_accession"],
                        "cell_type": meta["cell_type"],
                        "timecourse_id": meta["timecourse_id"],
                        "time": meta["ZT_or_CT"],
                        "time_hours": meta["time_hours"],
                        "time_system": meta["time_system"],
                        "expression": format(value, ".12g"),
                        "expression_unit": "processed_value_unit_unspecified",
                    })
            matrix_audits.append({
                "cell_type_label": label,
                "path": path_key,
                "sha256": _sha256(matrix_path),
                "size_bytes": matrix_path.stat().st_size,
                "n_matrix_rows": rows_seen,
                "n_sample_columns": len(sample_columns),
                "sample_columns": sample_columns,
                "n_candidate_transcript_rows": matched_rows,
                "status": "parsed_no_normalization",
            })

    sample_rows: dict[str, list[dict[str, Any]]] = {method: [] for method in AGGREGATIONS}
    candidate_audit_rows: list[dict[str, Any]] = []
    for label, matrix_path in matrix_specs:
        path_key = _path_key(matrix_path)
        sample_columns = samples_by_matrix[path_key]
        for candidate in candidates:
            symbol = candidate["gene_symbol"]
            feature = candidate_features.get((label, symbol), {
                "matrix_symbols": set(), "transcript_ids": set(), "match_modes": {},
            })
            candidate_audit_rows.append({
                "gene_symbol": symbol,
                "priority_class": candidate["priority_class"],
                "cell_type": label,
                "matrix_symbols": sorted(feature["matrix_symbols"]),
                "transcript_ids": sorted(feature["transcript_ids"]),
                "n_transcripts": len(feature["transcript_ids"]),
                "symbol_match_modes": dict(sorted(feature["match_modes"].items())),
                "status": "mapped" if feature["transcript_ids"] else "not_represented_in_processed_matrix",
            })
            for sample in sample_columns:
                meta = metadata[(path_key, sample)]
                features = values.get((label, symbol, sample), [])
                numbers = [entry[2] for entry in features]
                aggregated = {
                    "sum": math.fsum(numbers) if numbers else None,
                    "median": statistics.median(numbers) if numbers else None,
                    "max": max(numbers) if numbers else None,
                }
                for method, expression in aggregated.items():
                    sample_rows[method].append({
                        "gene_symbol": symbol,
                        "priority_class": candidate["priority_class"],
                        "sample_id": sample,
                        "geo_accession": meta["geo_accession"],
                        "cell_type": meta["cell_type"],
                        "timecourse_id": meta["timecourse_id"],
                        "background": meta.get("background", "unknown") or "unknown",
                        "developmental_stage": meta.get("developmental_stage", "unknown") or "unknown",
                        "sex": meta.get("sex", "unknown") or "unknown",
                        "genotype": meta.get("genotype", "unknown") or "unknown",
                        "lighting": meta.get("lighting", "unknown") or "unknown",
                        "temperature_C": meta.get("temperature_C", "unknown") or "unknown",
                        "experimental_unit": meta.get("experimental_unit", "unknown") or "unknown",
                        "biological_replicate_id": meta.get("biological_replicate_id", "unknown") or "unknown",
                        "batch_id": meta.get("batch_id", "unknown") or "unknown",
                        "time": meta["ZT_or_CT"],
                        "time_hours": meta["time_hours"],
                        "time_system": meta["time_system"],
                        "expression": "" if expression is None else format(expression, ".12g"),
                        "expression_unit": "processed_value_unit_unspecified",
                        "aggregation_rule": method,
                        "n_transcripts": len(features),
                        "transcript_ids": ";".join(sorted(entry[0] for entry in features)),
                        "status": "mapped" if features else "not_represented_in_processed_matrix",
                    })

    return {
        "transcript_rows": transcript_rows,
        "sample_rows": sample_rows,
        "audit": {
            "status": "executed_esat_candidate_expression_preparation",
            "candidate_list": candidates_path.as_posix(),
            "candidate_list_sha256": _sha256(candidates_path),
            "candidate_column": candidate_column,
            "priority_column": priority_column,
            "metadata_path": metadata_path.as_posix(),
            "metadata_sha256": _sha256(metadata_path),
            "alias_map": alias_path.as_posix() if alias_path else None,
            "alias_map_sha256": _sha256(alias_path) if alias_path else None,
            "n_candidates": len(candidates),
            "n_matrices": len(matrix_audits),
            "n_transcript_sample_rows": len(transcript_rows),
            "n_candidate_sample_rows_per_aggregation": len(next(iter(sample_rows.values()), [])),
            "aggregation_rules": list(AGGREGATIONS),
            "aggregation_note": "Gene-level sum, median, and maximum are explicit exploratory sensitivities, not source-defined biological expression units.",
            "normalization_status": "none_added_processed_numeric_scale_preserved",
            "matrix_audits": matrix_audits,
            "candidate_audits": candidate_audit_rows,
            "limitations": [
                "Transcript rows are preserved and are not treated as biological replicates.",
                "A candidate with no matching row is not proved biologically absent.",
                "Processed numeric units and normalization are not inferred by this adapter.",
                "Sampled cell-group pools and timecourse labels do not identify individual-fly replication.",
            ],
        },
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    if not fields:
        raise ValueError(f"refusing to write a CSV without columns: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="append", required=True, metavar="CELLTYPE=PATH")
    parser.add_argument("--metadata", type=Path, required=True, help="output of the GEO sample-map audit")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--candidate-column", default="gene_symbol")
    parser.add_argument("--priority-column")
    parser.add_argument("--alias-map", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True, help="relative prefix for transcript, sum, median, max, and audit outputs")
    args = parser.parse_args(argv[1:])
    try:
        specs = [_matrix_spec(value) for value in args.matrix]
        result = prepare_esat_candidate_expression(
            specs, args.metadata, args.candidates, args.candidate_column,
            args.priority_column, args.alias_map,
        )
        prefix = args.output_prefix
        _write_csv(prefix.with_name(prefix.name + "-transcripts.csv"), result["transcript_rows"])
        for method, rows in result["sample_rows"].items():
            _write_csv(prefix.with_name(prefix.name + f"-{method}.csv"), rows)
        audit_path = prefix.with_name(prefix.name + "-audit.json")
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(result["audit"], ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, csv.Error, gzip.BadGzipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
