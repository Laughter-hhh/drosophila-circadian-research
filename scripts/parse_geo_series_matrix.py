#!/usr/bin/env python3
"""Parse GEO series-matrix annotations and expression-table invariants.

The parser records input provenance and blocks sample-column misalignment. It
does not map probes to genes or perform expression/rhythm inference.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import TextIO


def _open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_values(line: str) -> list[str]:
    return next(csv.reader([line], delimiter="\t"))


def parse(path: Path, expected_sha256: str | None = None, provenance_path: str | None = None) -> tuple[dict[str, object], list[dict[str, str]]]:
    observed_sha256 = _sha256(path)
    normalized_expected = (expected_sha256 or "").strip().lower()
    if normalized_expected:
        if len(normalized_expected) != 64 or any(character not in "0123456789abcdef" for character in normalized_expected):
            raise ValueError("expected_sha256 must be a 64-character hexadecimal SHA-256 digest")
        if observed_sha256 != normalized_expected:
            raise ValueError(f"input SHA-256 mismatch: expected {normalized_expected}, observed {observed_sha256}")
    series: dict[str, list[list[str]]] = {}
    samples: dict[str, list[list[str]]] = {}
    table_header: list[str] = []
    probe_count = 0
    duplicate_ids: list[str] = []
    seen_ids: set[str] = set()
    non_numeric_values = 0
    in_table = False
    with _open_text(path) as handle:
        for raw in handle:
            line = raw.rstrip("\r\n")
            if line.startswith("!series_matrix_table_begin"):
                in_table = True
                continue
            if line.startswith("!series_matrix_table_end"):
                in_table = False
                continue
            if not in_table and line.startswith("!"):
                fields = _split_values(line)
                key = fields[0]
                values = fields[1:]
                target = samples if key.startswith("!Sample_") else series
                target.setdefault(key, []).append(values)
                continue
            if not in_table:
                continue
            fields = _split_values(line)
            if not table_header:
                table_header = fields
                continue
            if not fields:
                continue
            probe_id = fields[0].strip().strip('"')
            probe_count += 1
            if probe_id in seen_ids:
                duplicate_ids.append(probe_id)
            seen_ids.add(probe_id)
            for value in fields[1:]:
                token = value.strip().strip('"')
                if token.lower() in {"", "null", "na", "nan", "n/a"}:
                    continue
                try:
                    if not math.isfinite(float(token)):
                        non_numeric_values += 1
                except ValueError:
                    non_numeric_values += 1

    accessions = samples.get("!Sample_geo_accession", [[]])[0]
    sample_titles = samples.get("!Sample_title", [[]])[0]
    source_names = samples.get("!Sample_source_name_ch1", [[]])[0]
    organisms = samples.get("!Sample_organism_ch1", [[]])[0]
    platforms = samples.get("!Sample_platform_id", [[]])[0]
    characteristics_rows = samples.get("!Sample_characteristics_ch1", [])
    metadata: list[dict[str, str]] = []
    for idx, accession in enumerate(accessions):
        characteristics: dict[str, str] = {}
        for row in characteristics_rows:
            if idx >= len(row):
                continue
            item = row[idx].strip().strip('"')
            if ":" in item:
                key, value = item.split(":", 1)
                characteristics[key.strip()] = value.strip()
        metadata.append({
            "sample_id": accession.strip().strip('"'),
            "title": sample_titles[idx].strip().strip('"') if idx < len(sample_titles) else "",
            "source_name": source_names[idx].strip().strip('"') if idx < len(source_names) else "",
            "organism": organisms[idx].strip().strip('"') if idx < len(organisms) else "",
            "platform": platforms[idx].strip().strip('"') if idx < len(platforms) else "",
            "characteristics_json": json.dumps(characteristics, ensure_ascii=False, sort_keys=True),
        })

    table_samples = [item.strip().strip('"') for item in table_header[1:]] if table_header else []
    alignment_ok = accessions == table_samples and bool(accessions)
    status = "exploratory_geo_parse" if alignment_ok else "blocked_geo_parse"
    recorded_path = str(provenance_path).strip() if provenance_path is not None and str(provenance_path).strip() else str(path)
    summary: dict[str, object] = {
        "status": status,
        "source_file": recorded_path,
        "input_file_metadata": {"path": recorded_path, "size_bytes": path.stat().st_size, "sha256": observed_sha256},
        "source_integrity": "verified_sha256" if normalized_expected else "hash_recorded_not_verified",
        "series_accession": series.get("!Series_geo_accession", [[""]])[0][0] if series.get("!Series_geo_accession") else "",
        "n_samples_annotation": len(accessions),
        "n_samples_expression": len(table_samples),
        "n_probes_or_features": probe_count,
        "n_duplicate_probe_ids": len(duplicate_ids),
        "duplicate_probe_examples": duplicate_ids[:10],
        "n_non_numeric_values": non_numeric_values,
        "sample_alignment_ok": alignment_ok,
        "sample_accessions": [item.strip().strip('"') for item in accessions],
        "expression_table_samples": table_samples,
        "platforms": sorted({item.strip().strip('"') for item in platforms if item.strip()}),
        "annotation_keys": sorted({key for row in characteristics_rows for item in row for key in ([item.split(":", 1)[0].strip()] if ":" in item else [])}),
        "expression_table_header": table_header,
        "issues": [] if alignment_ok else [{"type": "sample_alignment_mismatch", "metadata_samples": len(accessions), "expression_samples": len(table_samples)}],
        "inference_warning": "Structural parsing only; probe IDs require platform annotation before gene-level claims. A blocked sample alignment must be corrected before expression extraction.",
    }
    return summary, metadata


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--metadata-output", type=Path)
    parser.add_argument("--expected-sha256", help="Optional expected SHA-256 digest for the exact downloaded input file.")
    parser.add_argument("--provenance-path", help="Optional portable path recorded in JSON instead of the local execution path.")
    args = parser.parse_args(argv[1:])
    try:
        summary, metadata = parse(args.input, args.expected_sha256, args.provenance_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if args.metadata_output:
        args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
        with args.metadata_output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["sample_id", "title", "source_name", "organism", "platform", "characteristics_json"])
            writer.writeheader()
            writer.writerows(metadata)
    return 0 if summary["status"] == "exploratory_geo_parse" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


