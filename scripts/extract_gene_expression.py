#!/usr/bin/env python3
"""Map GEO probe values to candidate genes and produce descriptive group summaries.

This helper deliberately stops at probe-mapped, descriptive summaries. It does not
perform normalization, differential expression, rhythmicity significance testing, or
causal inference.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, TextIO


def _open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _fields(line: str) -> list[str]:
    return [item.strip().strip('"') for item in next(csv.reader([line], delimiter="\t"))]


def parse_annotation(path: Path) -> dict[str, list[str]]:
    """Return a case-insensitive gene-symbol -> probe IDs map from GEO annotation."""
    with _open_text(path) as handle:
        header: list[str] | None = None
        for raw in handle:
            line = raw.rstrip("\r\n")
            if line.startswith("ID\t"):
                header = _fields(line)
                break
        if header is None:
            raise ValueError("annotation header beginning with ID\\t was not found")
        try:
            id_idx = header.index("ID")
            symbol_idx = header.index("Gene symbol")
        except ValueError as exc:
            raise ValueError("annotation must contain ID and Gene symbol columns") from exc
        mapping: dict[str, list[str]] = defaultdict(list)
        for raw in handle:
            line = raw.rstrip("\r\n")
            if not line or line.startswith(("!", "#", "^")):
                continue
            row = _fields(line)
            if max(id_idx, symbol_idx) >= len(row):
                continue
            probe = row[id_idx]
            symbol = row[symbol_idx].strip()
            if not probe or not symbol or symbol in {"---", "NA", "N/A"}:
                continue
            # GEO annotations occasionally contain several aliases separated by ///.
            for token in symbol.split("///"):
                token = token.strip()
                if token and token not in {"---", "NA", "N/A"}:
                    mapping[token.upper()].append(probe)
    return dict(mapping)


def read_candidates(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "gene_symbol" not in rows[0]:
        raise ValueError("candidate CSV must contain a gene_symbol column")
    values = []
    for row in rows:
        symbol = (row.get("gene_symbol") or "").strip()
        if symbol and symbol.upper() not in {item.upper() for item in values}:
            values.append(symbol)
    if not values:
        raise ValueError("candidate CSV contains no non-empty gene_symbol values")
    return values


def read_metadata(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("metadata CSV is empty")
    required = {"sample_id", "characteristics_json"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"metadata missing columns: {', '.join(sorted(missing))}")
    out: list[dict[str, str]] = []
    for row in rows:
        chars = json.loads(row.get("characteristics_json") or "{}")
        developmental_stage = chars.get(
            "developmental stage",
            chars.get("developmental_stage", chars.get("stage", "unknown")),
        )
        out.append({
            "sample_id": (row.get("sample_id") or "").strip(),
            "cell_type": str(chars.get("cell type", chars.get("cell_type", "unknown"))),
            "developmental_stage": str(developmental_stage or "unknown"),
            "time": str(chars.get("time", "unknown")),
            "background": str(chars.get("background", "unknown")),
        })
    return out


def _mean_sd(values: Iterable[float]) -> tuple[float | None, float | None]:
    vals = list(values)
    if not vals:
        return None, None
    mean = statistics.fmean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else None
    return mean, sd


def summarize(matrix: Path, annotation: Path, metadata: Path, candidates: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metadata_rows = read_metadata(metadata)
    metadata_by_sample = {row["sample_id"]: row for row in metadata_rows if row["sample_id"]}
    candidate_symbols = read_candidates(candidates)
    annotation_map = parse_annotation(annotation)
    probes_by_gene = {symbol: annotation_map.get(symbol.upper(), []) for symbol in candidate_symbols}
    wanted_probes = {probe for probes in probes_by_gene.values() for probe in probes}
    sample_order: list[str] = []
    values_by_probe: dict[str, list[float | None]] = {}
    in_table = False
    with _open_text(matrix) as handle:
        for raw in handle:
            line = raw.rstrip("\r\n")
            if line.startswith("!series_matrix_table_begin"):
                in_table = True
                continue
            if line.startswith("!series_matrix_table_end"):
                break
            if not in_table:
                continue
            row = _fields(line)
            if not sample_order:
                if not row or row[0] not in {"ID_REF", "ID"}:
                    raise ValueError("expression table header must begin with ID_REF")
                sample_order = row[1:]
                continue
            if not row or row[0] not in wanted_probes:
                continue
            parsed: list[float | None] = []
            for token in row[1:]:
                try:
                    value = float(token)
                    parsed.append(value if math.isfinite(value) else None)
                except ValueError:
                    parsed.append(None)
            values_by_probe[row[0]] = parsed
    if not sample_order:
        raise ValueError("expression table header was not found")
    if sample_order != [row["sample_id"] for row in metadata_rows]:
        raise ValueError("sample order in expression table does not match metadata CSV")

    sample_values: list[dict[str, object]] = []
    for symbol in candidate_symbols:
        probes = probes_by_gene[symbol]
        for idx, sample_id in enumerate(sample_order):
            probe_values = [values_by_probe[probe][idx] for probe in probes if probe in values_by_probe and idx < len(values_by_probe[probe]) and values_by_probe[probe][idx] is not None]
            sample_values.append({
                "gene_symbol": symbol,
                "sample_id": sample_id,
                "cell_type": metadata_by_sample[sample_id]["cell_type"],
                "developmental_stage": metadata_by_sample[sample_id]["developmental_stage"],
                "time": metadata_by_sample[sample_id]["time"],
                "background": metadata_by_sample[sample_id]["background"],
                "probe_count": len(probe_values),
                "expression": statistics.median(probe_values) if probe_values else None,
                "probe_ids": ";".join(probes),
            })

    grouped: dict[tuple[str, str, str, str, str], list[float]] = defaultdict(list)
    probes_seen: dict[str, set[str]] = defaultdict(set)
    for row in sample_values:
        if row["expression"] is not None:
            key = (
                str(row["gene_symbol"]),
                str(row["cell_type"]),
                str(row["developmental_stage"]),
                str(row["time"]),
                str(row["background"]),
            )
            grouped[key].append(float(row["expression"]))
            probes_seen[str(row["gene_symbol"])].update(filter(None, str(row["probe_ids"]).split(";")))
    summary: list[dict[str, object]] = []
    for symbol in candidate_symbols:
        keys = [key for key in grouped if key[0] == symbol]
        if not keys:
            summary.append({"gene_symbol": symbol, "status": "not_found_or_no_numeric_values", "n_samples": 0, "probe_ids": ";".join(probes_by_gene[symbol])})
            continue
        for key in sorted(keys):
            vals = grouped[key]
            mean, sd = _mean_sd(vals)
            summary.append({
                "gene_symbol": key[0],
                "cell_type": key[1],
                "developmental_stage": key[2],
                "time": key[3],
                "background": key[4],
                "n_samples": len(vals),
                "mean_expression": mean,
                "sd_expression": sd,
                "probe_count": len(probes_seen[key[0]]),
                "probe_ids": ";".join(sorted(probes_seen[key[0]])),
                "status": "descriptive_probe_mapped_summary",
            })
    return summary, sample_values


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("annotation", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--sample-output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        summary, samples = summarize(args.matrix, args.annotation, args.metadata, args.candidates)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    summary_fields = ["gene_symbol", "cell_type", "developmental_stage", "time", "background", "n_samples", "mean_expression", "sd_expression", "probe_count", "probe_ids", "status"]
    with args.summary_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary)
    if args.sample_output:
        with args.sample_output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["gene_symbol", "sample_id", "cell_type", "developmental_stage", "time", "background", "probe_count", "expression", "probe_ids"], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
