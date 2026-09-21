#!/usr/bin/env python3
"""Audit transcript-to-sample key multiplicity in GEO ESAT expression matrices.

This is a structural audit only. It does not normalize, aggregate, fit rhythms,
or interpret missing candidate rows as biological absence.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import TextIO


def _open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_candidates(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or column not in rows[0]:
        raise ValueError(f"candidate list must contain a non-empty {column!r} column")
    seen: set[str] = set()
    candidates: list[str] = []
    for row in rows:
        symbol = (row.get(column) or "").strip()
        key = symbol.casefold()
        if not symbol:
            raise ValueError(f"candidate list contains a blank value in {column!r}")
        if key in seen:
            raise ValueError(f"candidate list contains a duplicate or case-ambiguous symbol: {symbol!r}")
        candidates.append(symbol)
        seen.add(key)
    if not candidates:
        raise ValueError(f"candidate list contains no usable values in {column!r}")
    return candidates


def audit_matrix(
    cell_type: str,
    path: Path,
    candidates: list[str],
    aliases: dict[str, str] | None = None,
) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"matrix does not exist: {path}")
    candidate_by_key = {symbol.casefold(): symbol for symbol in candidates}
    transcript_ids: dict[str, list[str]] = {symbol: [] for symbol in candidates}
    duplicate_transcript_rows: dict[str, int] = {symbol: 0 for symbol in candidates}
    blank_transcript_rows: dict[str, int] = {symbol: 0 for symbol in candidates}
    missing_expression_cells: dict[str, int] = {symbol: 0 for symbol in candidates}
    invalid_expression_cells: dict[str, int] = {symbol: 0 for symbol in candidates}
    matched_symbols: dict[str, set[str]] = {symbol: set() for symbol in candidates}
    match_modes: dict[str, Counter[str]] = {symbol: Counter() for symbol in candidates}
    total_rows = 0

    with _open_text(path) as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, None)
        if not header or len(header) < 3 or header[0].strip().casefold() != "symbol":
            raise ValueError("ESAT matrix must begin with transcript ID, Symbol, then sample columns")
        sample_columns = [item.strip() for item in header[2:]]
        if any(not item for item in sample_columns):
            raise ValueError("ESAT matrix contains a blank sample-column label")
        if len(set(sample_columns)) != len(sample_columns):
            raise ValueError("ESAT matrix contains duplicate sample-column labels")

        for line_number, row in enumerate(reader, start=2):
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            if len(row) != len(header):
                raise ValueError(
                    f"row {line_number} has {len(row)} fields; expected {len(header)}"
                )
            total_rows += 1
            transcript_id = row[0].strip()
            matrix_symbol = row[1].strip()
            symbol_key = matrix_symbol.casefold()
            candidate = candidate_by_key.get(symbol_key)
            match_mode = "casefold_symbol_match"
            if candidate is None and symbol_key in (aliases or {}):
                candidate = aliases[symbol_key]
                match_mode = "explicit_alias_map"
            if candidate is None:
                continue
            if matrix_symbol == candidate:
                match_mode = "exact_symbol_match"
            matched_symbols[candidate].add(matrix_symbol)
            match_modes[candidate][match_mode] += 1
            if transcript_id:
                transcript_ids[candidate].append(transcript_id)
            else:
                blank_transcript_rows[candidate] += 1
            for value in row[2:]:
                token = value.strip()
                if not token:
                    missing_expression_cells[candidate] += 1
                    continue
                try:
                    parsed = float(token)
                except ValueError:
                    invalid_expression_cells[candidate] += 1
                    continue
                if not math.isfinite(parsed):
                    invalid_expression_cells[candidate] += 1

    candidate_audits: list[dict[str, object]] = []
    duplicate_key_pairs = 0
    extra_feature_sample_rows = 0
    for candidate in candidates:
        ids = transcript_ids[candidate]
        id_counts = Counter(ids)
        transcript_rows = len(ids) + blank_transcript_rows[candidate]
        repeated_ids = sum(count - 1 for count in id_counts.values() if count > 1)
        has_rows = transcript_rows > 0
        multiple_rows = transcript_rows > 1
        if multiple_rows:
            duplicate_key_pairs += len(sample_columns)
            extra_feature_sample_rows += (transcript_rows - 1) * len(sample_columns)
        candidate_audits.append({
            "candidate_symbol": candidate,
            "matrix_symbols": sorted(matched_symbols[candidate]),
            "symbol_match_modes": dict(sorted(match_modes[candidate].items())),
            "status": (
                "multiple_transcript_rows_per_sample" if multiple_rows
                else "single_transcript_row_per_sample" if has_rows
                else "candidate_symbol_not_found_in_matrix"
            ),
            "n_transcript_rows": transcript_rows,
            "n_unique_transcript_ids": len(id_counts),
            "n_repeated_transcript_id_rows": repeated_ids,
            "n_blank_transcript_id_rows": blank_transcript_rows[candidate],
            "n_candidate_gene_sample_pairs_with_multiple_feature_rows": (
                len(sample_columns) if multiple_rows else 0
            ),
            "n_extra_feature_sample_rows_beyond_one_per_gene_sample": (
                (transcript_rows - 1) * len(sample_columns) if multiple_rows else 0
            ),
            "n_missing_expression_cells": missing_expression_cells[candidate],
            "n_invalid_or_nonfinite_expression_cells": invalid_expression_cells[candidate],
        })

    found = [row for row in candidate_audits if row["n_transcript_rows"]]
    return {
        "cell_type_label": cell_type,
        "input_file": path.as_posix(),
        "input_sha256": _sha256(path),
        "matrix_row_count": total_rows,
        "n_sample_columns": len(sample_columns),
        "sample_column_labels": sample_columns,
        "candidate_matching": "case-folded direct candidate matches plus only aliases supplied through the explicit alias map",
        "n_candidates_requested": len(candidates),
        "n_candidates_with_symbol_rows": len(found),
        "candidate_symbols_not_found": [
            row["candidate_symbol"] for row in candidate_audits if not row["n_transcript_rows"]
        ],
        "n_candidates_with_multiple_transcript_rows": sum(
            row["n_transcript_rows"] > 1 for row in candidate_audits
        ),
        "n_candidate_gene_sample_pairs_with_multiple_feature_rows": duplicate_key_pairs,
        "n_extra_feature_sample_rows_beyond_one_per_gene_sample": extra_feature_sample_rows,
        "max_transcript_rows_for_one_candidate": max(
            (int(row["n_transcript_rows"]) for row in candidate_audits), default=0
        ),
        "candidate_audits": candidate_audits,
    }


def _read_aliases(path: Path | None, candidates: list[str]) -> dict[str, str]:
    if path is None:
        return {}
    required = {"matrix_symbol", "canonical_gene_symbol", "source_url", "checked_at_utc", "evidence_note"}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"alias map is missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    candidates_by_key = {candidate.casefold(): candidate for candidate in candidates}
    aliases: dict[str, str] = {}
    for row_number, row in enumerate(rows, start=2):
        matrix_symbol = (row.get("matrix_symbol") or "").strip()
        canonical = (row.get("canonical_gene_symbol") or "").strip()
        source_url = (row.get("source_url") or "").strip()
        checked_at = (row.get("checked_at_utc") or "").strip()
        evidence_note = (row.get("evidence_note") or "").strip()
        if not matrix_symbol or not canonical or not source_url.startswith("https://") or not checked_at or not evidence_note:
            raise ValueError(f"alias map row {row_number} requires symbol, canonical symbol, HTTPS source, check date, and evidence note")
        target = candidates_by_key.get(canonical.casefold())
        if target is None or target != canonical:
            raise ValueError(f"alias map row {row_number} target is not an exact symbol in the candidate list: {canonical!r}")
        key = matrix_symbol.casefold()
        direct_target = candidates_by_key.get(key)
        if direct_target is not None and direct_target != target:
            raise ValueError(f"alias map row {row_number} conflicts with direct candidate symbol {direct_target!r}")
        if key in aliases:
            raise ValueError(f"alias map has duplicate or case-ambiguous matrix symbol: {matrix_symbol!r}")
        aliases[key] = target
    return aliases


def _parse_matrix_spec(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    label = label.strip()
    raw_path = raw_path.strip()
    if not separator or not label or not raw_path:
        raise ValueError("--matrix must use CELLTYPE=PATH")
    return label, Path(raw_path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-list", type=Path, required=True)
    parser.add_argument("--candidate-column", default="gene_symbol")
    parser.add_argument("--alias-map", type=Path, help="optional CSV containing explicit, source-documented matrix-symbol aliases")
    parser.add_argument(
        "--matrix", action="append", required=True, metavar="CELLTYPE=PATH",
        help="ESAT transcript-level TSV or TSV.GZ; repeat once per cell group",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        candidates = _read_candidates(args.candidate_list, args.candidate_column)
        aliases = _read_aliases(args.alias_map, candidates)
        specs = [_parse_matrix_spec(value) for value in args.matrix]
        labels = [label.casefold() for label, _ in specs]
        if len(set(labels)) != len(labels):
            raise ValueError("each --matrix cell-type label must be unique")
        matrices = [audit_matrix(label, path, candidates, aliases) for label, path in specs]
    except (OSError, ValueError, csv.Error, gzip.BadGzipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = {
        "status": "transcript_level_sample_key_audit_completed",
        "scientific_status": "structural_audit_only_no_expression_or_rhythm_inference",
        "candidate_list": args.candidate_list.as_posix(),
        "candidate_list_sha256": _sha256(args.candidate_list),
        "candidate_column": args.candidate_column,
        "alias_map": args.alias_map.as_posix() if args.alias_map else None,
        "alias_map_sha256": _sha256(args.alias_map) if args.alias_map else None,
        "n_explicit_aliases": len(aliases),
        "n_candidates": len(candidates),
        "matrices": matrices,
        "inference_warning": (
            "This report counts exact gene-symbol transcript rows and repeated gene-sample keys. "
            "It does not establish expression absence, normalize data, choose a gene-level "
            "aggregation rule, test rhythmicity, or support channel function/causality. "
            "Sample column labels have not been mapped to GEO timepoints in this audit."
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
