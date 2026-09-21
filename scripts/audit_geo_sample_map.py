#!/usr/bin/env python3
"""Verify a processed GEO matrix column map against its SOFT sample records.

The explicit mapping CSV is the curator's record of how matrix columns relate
to GEO samples. This helper checks that mapping against the actual matrix
headers, official SOFT titles, cell-type characteristics and timepoint fields;
it does not infer missing sample identities or animal-level replication.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import TextIO


SOFT_SAMPLE_RE = re.compile(r"^\^SAMPLE\s*=\s*(GSM\d+)\s*$")
TIME_RE = re.compile(r"\b(ZT|CT)\s*([+-]?\d+(?:\.\d+)?)\b", re.IGNORECASE)
MAP_COLUMNS = {"matrix_path", "matrix_column", "matrix_alias", "gsm_accession", "timecourse_id"}


def _open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _soft_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse_geo_family_soft(path: Path) -> dict[str, dict[str, object]]:
    """Read sample-level title, source, and characteristics from GEO SOFT."""
    if not path.is_file():
        raise ValueError(f"GEO SOFT file does not exist: {path}")
    samples: dict[str, dict[str, object]] = {}
    current_id = ""
    current: dict[str, object] = {}
    with _open_text(path) as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\r\n")
            match = SOFT_SAMPLE_RE.match(line)
            if match:
                if current_id:
                    if current_id in samples:
                        raise ValueError(f"duplicate GEO sample accession in SOFT file: {current_id}")
                    samples[current_id] = current
                current_id = match.group(1)
                current = {"geo_accession": current_id, "characteristics": {}}
                continue
            if not current_id or " = " not in line:
                continue
            key, value = line.split(" = ", 1)
            value = _soft_value(value)
            if key == "!Sample_title":
                if current.get("title"):
                    raise ValueError(f"duplicate GEO title for {current_id} at SOFT line {line_number}")
                current["title"] = value
            elif key == "!Sample_source_name_ch1":
                if current.get("source_name"):
                    raise ValueError(f"duplicate source name for {current_id} at SOFT line {line_number}")
                current["source_name"] = value
            elif key == "!Sample_characteristics_ch1":
                field, separator, field_value = value.partition(":")
                if not separator or not field.strip():
                    continue
                characteristics = current["characteristics"]
                normalized_field = field.strip().casefold()
                if normalized_field in characteristics:
                    raise ValueError(f"duplicate characteristic {field!r} for {current_id}")
                characteristics[normalized_field] = field_value.strip()
    if current_id:
        if current_id in samples:
            raise ValueError(f"duplicate GEO sample accession in SOFT file: {current_id}")
        samples[current_id] = current
    if not samples:
        raise ValueError("no GEO sample records found in SOFT file")
    return samples


def _matrix_columns(path: Path) -> list[str]:
    if not path.is_file():
        raise ValueError(f"matrix does not exist: {path}")
    with _open_text(path) as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, None)
    if not header or len(header) < 3 or header[0].strip().casefold() != "symbol":
        raise ValueError("matrix header must begin with Symbol, transcript ID, then sample columns")
    columns = [column.strip() for column in header[2:]]
    if any(not column for column in columns):
        raise ValueError(f"blank sample column label in {path}")
    if len(columns) != len(set(columns)):
        raise ValueError(f"duplicate sample column label in {path}")
    return columns


def _alias_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _read_map(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = sorted(MAP_COLUMNS - fields)
        if missing:
            raise ValueError(f"mapping CSV is missing columns: {', '.join(missing)}")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError("mapping CSV contains no mapping rows")
    for row_number, row in enumerate(rows, start=2):
        for field in MAP_COLUMNS:
            if not row.get(field):
                raise ValueError(f"blank {field} in mapping CSV row {row_number}")
    return rows


def audit_geo_sample_map(
    soft_path: Path,
    mapping_path: Path,
    matrix_specs: list[tuple[str, Path]],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    """Return an audit report and output-ready sample metadata rows."""
    if not matrix_specs:
        raise ValueError("at least one --matrix CELLTYPE=PATH is required")
    samples = parse_geo_family_soft(soft_path)
    map_rows = _read_map(mapping_path)
    spec_by_path: dict[str, tuple[str, Path]] = {}
    columns_by_path: dict[str, list[str]] = {}
    for label, path in matrix_specs:
        normalized_path = path.as_posix()
        if normalized_path in spec_by_path:
            raise ValueError(f"matrix path is supplied more than once: {normalized_path}")
        spec_by_path[normalized_path] = (label, path)
        columns_by_path[normalized_path] = _matrix_columns(path)

    seen_matrix_keys: set[tuple[str, str]] = set()
    seen_accessions: set[str] = set()
    covered_by_path: dict[str, list[dict[str, str]]] = {path: [] for path in spec_by_path}
    metadata_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(map_rows, start=2):
        matrix_path = row["matrix_path"].replace("\\", "/")
        if matrix_path not in spec_by_path:
            raise ValueError(f"mapping row {row_number} uses undeclared matrix path: {matrix_path}")
        label, _ = spec_by_path[matrix_path]
        matrix_column = row["matrix_column"]
        key = (matrix_path, matrix_column)
        if key in seen_matrix_keys:
            raise ValueError(f"duplicate matrix_path/matrix_column mapping: {key}")
        seen_matrix_keys.add(key)
        if matrix_column not in columns_by_path[matrix_path]:
            raise ValueError(f"matrix column not present in declared matrix: {matrix_column} ({matrix_path})")
        gsm = row["gsm_accession"].upper()
        if gsm in seen_accessions:
            raise ValueError(f"GEO sample is mapped more than once: {gsm}")
        seen_accessions.add(gsm)
        record = samples.get(gsm)
        if record is None:
            raise ValueError(f"GEO sample not found in family SOFT: {gsm}")
        title = str(record.get("title") or "")
        if not title:
            raise ValueError(f"GEO sample has no title: {gsm}")
        if _alias_key(row["matrix_alias"]) != _alias_key(title):
            raise ValueError(
                f"matrix alias does not match GEO title for {matrix_column}: "
                f"{row['matrix_alias']!r} vs {title!r} ({gsm})"
            )
        characteristics = record.get("characteristics")
        if not isinstance(characteristics, dict):
            raise ValueError(f"GEO sample has no characteristics dictionary: {gsm}")
        official_cell_type = str(characteristics.get("type") or "").strip()
        source_name = str(record.get("source_name") or "").strip()
        if official_cell_type.casefold() != label.casefold() or source_name.casefold() != label.casefold():
            raise ValueError(
                f"cell-type mismatch for {gsm}: matrix={label!r}, "
                f"GEO type={official_cell_type!r}, source={source_name!r}"
            )
        timepoint = str(characteristics.get("timepoint") or "").strip()
        time_match = TIME_RE.search(timepoint)
        if not time_match:
            raise ValueError(f"missing or unparseable timepoint for {gsm}: {timepoint!r}")
        time_system = time_match.group(1).upper()
        time_hour = float(time_match.group(2)) % 24.0
        if not math.isfinite(time_hour):
            raise ValueError(f"nonfinite timepoint for {gsm}: {timepoint!r}")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", row["timecourse_id"]):
            raise ValueError(f"invalid timecourse_id for {gsm}: {row['timecourse_id']!r}")
        mapped = {
            "matrix_path": matrix_path,
            "sample_id": matrix_column,
            "matrix_alias": row["matrix_alias"],
            "geo_accession": gsm,
            "geo_title": title,
            "cell_type": official_cell_type,
            "ZT_or_CT": f"{time_system}{time_hour:g}",
            "time_hours": f"{time_hour:g}",
            "time_system": time_system,
            "timecourse_id": row["timecourse_id"],
            "experimental_unit": "pooled_neuron_library",
            "biological_replicate_id": gsm,
            "batch_id": "unknown",
            "genotype": "not_reported_in_GEO_sample_record",
            "sex": "not_reported",
            "age_days": "not_reported",
            "temperature_C": "not_reported",
            "lighting": "LD_12:12_per_primary_paper",
            "preparation": "manually_sorted_neuron_pool; approximately 50-100 neurons per sample per primary paper",
            "source_url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gsm}",
        }
        metadata_rows.append(mapped)
        covered_by_path[matrix_path].append(mapped)

    expected_keys = {
        (path, column)
        for path, columns in columns_by_path.items()
        for column in columns
    }
    uncovered = sorted(expected_keys - seen_matrix_keys)
    if uncovered:
        preview = ", ".join(f"{path}:{column}" for path, column in uncovered[:8])
        raise ValueError(f"matrix columns missing from mapping CSV ({len(uncovered)}): {preview}")

    matrix_reports: list[dict[str, object]] = []
    for matrix_path, (label, path) in spec_by_path.items():
        group_rows = covered_by_path[matrix_path]
        courses: dict[str, list[dict[str, str]]] = {}
        for row in group_rows:
            courses.setdefault(row["timecourse_id"], []).append(row)
        if len(courses) != 2:
            raise ValueError(f"{label} must map to two independent timecourse groups; found {len(courses)}")
        course_time_sets: dict[str, list[float]] = {}
        for course_id, course_rows in courses.items():
            times = [float(row["time_hours"]) for row in course_rows]
            if len(times) != 6 or len(set(times)) != 6:
                raise ValueError(
                    f"{label}/{course_id} must contain six unique timepoints; "
                    f"found n={len(times)}, unique={len(set(times))}"
                )
            ordered = sorted(times)
            intervals = [ordered[index + 1] - ordered[index] for index in range(len(ordered) - 1)]
            intervals.append((ordered[0] + 24.0) - ordered[-1])
            if any(abs(interval - 4.0) > 1e-9 for interval in intervals):
                raise ValueError(f"{label}/{course_id} is not a complete 4-hourly circadian course: {ordered}")
            time_systems = {row["time_system"] for row in course_rows}
            if len(time_systems) != 1:
                raise ValueError(f"mixed ZT/CT systems in {label}/{course_id}")
            course_time_sets[course_id] = ordered
        unique_time_sets = {tuple(times) for times in course_time_sets.values()}
        if len(unique_time_sets) != 1:
            raise ValueError(f"the two {label} timecourses do not cover matching timepoints")
        time_systems = {
            row["time_system"]
            for course_rows in courses.values()
            for row in course_rows
        }
        if len(time_systems) != 1:
            raise ValueError(f"the two {label} timecourses use different time systems")
        matrix_reports.append({
            "matrix_path": matrix_path,
            "cell_type": label,
            "n_matrix_columns": len(columns_by_path[matrix_path]),
            "n_mapped_samples": len(group_rows),
            "timecourses": {
                course_id: {"n_samples": len(rows), "timepoints": course_time_sets[course_id]}
                for course_id, rows in sorted(courses.items())
            },
        })

    report: dict[str, object] = {
        "status": "verified_geo_sample_mapping",
        "scientific_status": "metadata_alignment_verified_not_expression_or_rhythm_analysis",
        "n_geo_sample_records_in_family_soft": len(samples),
        "n_matrix_files": len(matrix_reports),
        "n_sample_columns": sum(len(columns) for columns in columns_by_path.values()),
        "n_unique_geo_samples": len(seen_accessions),
        "matrix_audits": matrix_reports,
        "inputs": {
            "family_soft": {"path": soft_path.as_posix(), "sha256": _sha256(soft_path)},
            "mapping_csv": {"path": mapping_path.as_posix(), "sha256": _sha256(mapping_path)},
            "matrices": [
                {"path": path.as_posix(), "sha256": _sha256(path)}
                for _, path in matrix_specs
            ],
        },
        "limitations": [
            "timecourse_id labels are curator-assigned groupings based on the two time-course design and GEO sample-title blocks; they are not native GEO fields",
            "the experimental unit represented in the metadata output is a pooled neuron library, not an identified individual fly",
            "sex, age, genotype, temperature and individual-fly identifiers are not reported in the sample-level records used here",
            "the source LNv pool combines PDF-positive small and large LNvs; the LNd group includes the fifth PDF-negative s-LNv; DN1 is a subset",
            "this audit verifies metadata alignment only; it does not validate expression normalization or infer rhythmicity",
        ],
        "issues": [],
    }
    return report, metadata_rows


def _parse_matrix_spec(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    label = label.strip()
    raw_path = raw_path.strip()
    if not separator or not label or not raw_path:
        raise ValueError("--matrix must use CELLTYPE=PATH")
    return label, Path(raw_path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-soft", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--matrix", action="append", required=True, metavar="CELLTYPE=PATH")
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--output-metadata", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        specs = [_parse_matrix_spec(value) for value in args.matrix]
        report, metadata_rows = audit_geo_sample_map(args.family_soft, args.mapping, specs)
    except (OSError, ValueError, csv.Error, gzip.BadGzipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if metadata_rows:
        with args.output_metadata.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(metadata_rows[0]))
            writer.writeheader()
            writer.writerows(metadata_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
