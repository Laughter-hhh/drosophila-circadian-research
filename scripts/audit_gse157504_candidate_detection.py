#!/usr/bin/env python3
"""Join GSE157504 raw single-cell counts to clock-neuron labels for descriptive detection.

Outputs cell-level detection aggregates only. It does not estimate expression
rhythms, compare conditions statistically, or treat cells as biological replicates.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


GROUP_ORDER = ("s-LNv", "l-LNv", "LNd", "DN", "LN_ITP_ambiguous", "other_clock_neuron")
SAMPLE_COLUMNS = (
    "candidate", "priority_class", "cell_group", "cluster_id", "cluster_label",
    "condition", "time_system", "phase_hours", "replicate", "n_annotated_cells",
    "n_cells_detected", "detection_fraction", "sum_raw_counts", "mean_raw_counts_per_cell",
)
GROUP_COLUMNS = (
    "candidate", "priority_class", "cell_group", "condition", "time_system",
    "n_annotated_cells", "n_cells_detected", "detection_fraction", "sum_raw_counts",
    "mean_raw_counts_per_cell",
)
FEATURE_COLUMNS = (
    "candidate", "priority_class", "raw_feature_status", "n_raw_members_with_feature",
    "n_annotated_cells_with_feature_counts", "n_cells_detected", "detection_fraction_all_annotated_cells",
    "interpretation_limit",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path must be inside provenance root: {path}") from exc


def _metadata(path: Path, root: Path, expected: str | None) -> dict[str, Any]:
    observed = sha256_file(path)
    expected_hash = (expected or "").strip().lower()
    if expected_hash and observed != expected_hash:
        raise ValueError(f"SHA-256 mismatch for {path}: expected {expected_hash}, observed {observed}")
    return {
        "path": _relative(path, root),
        "size_bytes": path.stat().st_size,
        "sha256": observed,
        "integrity": "verified_sha256" if expected_hash else "hash_recorded_not_verified",
    }


def _load_candidates(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"gene_symbol", "priority_class"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"candidate CSV missing columns: {sorted(missing)}")
        rows = [
            {"gene_symbol": (row.get("gene_symbol") or "").strip(),
             "priority_class": (row.get("priority_class") or "").strip()}
            for row in reader
        ]
    rows = [row for row in rows if row["gene_symbol"]]
    if not rows:
        raise ValueError("candidate CSV contains no candidate genes")
    if any(not row["priority_class"] for row in rows):
        raise ValueError("candidate CSV contains a candidate with blank priority_class")
    genes = [row["gene_symbol"] for row in rows]
    if len(genes) != len(set(genes)):
        raise ValueError("candidate CSV contains duplicate gene_symbol values")
    return rows


def _condition_and_replicate(value: str) -> tuple[str, str]:
    match = re.fullmatch(r"(LD|DD)_([0-9]+)", value.strip().upper())
    if not match:
        raise ValueError(f"unrecognized Repeats value: {value!r}")
    return match.group(1), f"{match.group(1)}_{match.group(2)}"


def _timepoint(value: str, condition: str) -> tuple[str, int]:
    match = re.fullmatch(r"(?:ZT|CT)_?([0-9]{1,2})", value.strip().upper())
    if not match:
        raise ValueError(f"unrecognized time value: {value!r}")
    phase = int(match.group(1))
    if phase not in {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22}:
        raise ValueError(f"invalid circadian phase hour: {value!r}")
    return ("ZT" if condition == "LD" else "CT"), phase


def _group_label(ident: str) -> tuple[str, str, str]:
    cluster, separator, label = ident.partition(":")
    cluster = cluster.strip()
    label = label.strip()
    if not separator or not cluster or not label:
        raise ValueError(f"unrecognized Idents cell label: {ident!r}")
    if label == "s_LNv":
        group = "s-LNv"
    elif label == "l_LNv":
        group = "l-LNv"
    elif label.startswith("LNd"):
        group = "LNd"
    elif label.startswith("DN"):
        group = "DN"
    elif label == "LN_ITP":
        group = "LN_ITP_ambiguous"
    else:
        group = "other_clock_neuron"
    return cluster, label, group


def _canonical_barcode(value: str, condition: str) -> str:
    barcode = value.strip()
    if barcode.startswith("X") and len(barcode) > 1 and barcode[1].isdigit():
        barcode = barcode[1:]
    if condition == "DD":
        barcode = re.sub(r"_ZT(?=\d{2}(?:_|$))", "_CT", barcode, flags=re.IGNORECASE)
    return barcode.casefold()


def _load_annotation(path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    aliases: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"experiment", "time", "Repeats", "Idents"}
        missing = required - set(reader.fieldnames or [])
        if missing or not (reader.fieldnames and reader.fieldnames[0] == ""):
            raise ValueError(f"annotation CSV must have a barcode column plus {sorted(required)}")
        for line, row in enumerate(reader, start=2):
            barcode = (row.get("") or "").strip()
            if not barcode:
                raise ValueError(f"blank barcode in annotation row {line}")
            canonical_id = barcode.casefold()
            if canonical_id in seen_ids:
                raise ValueError(f"duplicate annotation barcode: {barcode}")
            seen_ids.add(canonical_id)
            condition, replicate = _condition_and_replicate(row["Repeats"])
            experiment = row["experiment"].strip().upper()
            if not re.search(rf"(?:^|_){condition}(?:_|$)", experiment):
                raise ValueError(f"experiment/replicate condition mismatch in annotation row {line}")
            time_system, phase = _timepoint(row["time"], condition)
            cluster_id, cluster_label, group = _group_label(row["Idents"])
            record = {
                "barcode": barcode,
                "condition": condition,
                "replicate": replicate,
                "time_system": time_system,
                "phase_hours": phase,
                "cluster_id": cluster_id,
                "cluster_label": cluster_label,
                "cell_group": group,
            }
            records.append(record)
            alias = _canonical_barcode(barcode, condition)
            if alias in aliases:
                raise ValueError(f"barcode normalization collision in annotations: {barcode}")
            aliases[alias] = record
    if not records:
        raise ValueError("annotation file contains no cells")
    return records, aliases


def _count(value: str, gene: str, member: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric count for {gene} in {member}: {value!r}") from exc
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError(f"raw count must be a finite non-negative integer for {gene} in {member}: {value!r}")
    return int(number)


def _resolve_header_barcode(raw_barcode: str, aliases: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    matches = {
        id(aliases[key]): aliases[key]
        for condition in ("LD", "DD")
        if (key := _canonical_barcode(raw_barcode, condition)) in aliases
    }
    if len(matches) > 1:
        raise ValueError(f"raw barcode maps to more than one annotation record: {raw_barcode}")
    return next(iter(matches.values())) if matches else None


def _summarize(
    raw_tar: Path,
    annotation_records: list[dict[str, Any]],
    annotation_aliases: dict[str, dict[str, Any]],
    candidates: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    candidate_by_gene = {row["gene_symbol"]: row for row in candidates}
    aggregate: dict[tuple[str, str, str, str, str, str, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    feature_members = Counter()
    feature_cells = Counter()
    feature_positive = Counter()
    matched_counts: Counter[str] = Counter()
    raw_cells_total = 0
    raw_members = 0
    nonmatrix_members = 0

    with tarfile.open(raw_tar, mode="r:*") as archive:
        for member in archive:
            if not member.isfile():
                continue
            if not member.name.lower().endswith(".csv.gz"):
                nonmatrix_members += 1
                continue
            raw_members += 1
            compressed = archive.extractfile(member)
            if compressed is None:
                raise ValueError(f"could not read tar member: {member.name}")
            with compressed, gzip.GzipFile(fileobj=compressed) as gz, io.TextIOWrapper(gz, encoding="utf-8-sig", newline="") as text:
                reader = csv.reader(text)
                try:
                    header = next(reader)
                except StopIteration as exc:
                    raise ValueError(f"empty count matrix: {member.name}") from exc
                if len(header) < 2 or header[0].strip() not in {"", "gene", "Gene"}:
                    raise ValueError(f"unexpected matrix header in {member.name}")
                raw_cells_total += len(header) - 1
                matched_columns: list[tuple[int, dict[str, Any]]] = []
                raw_header_ids: set[str] = set()
                for column_index, raw_id in enumerate(header[1:], start=1):
                    canonical_raw = raw_id.strip().casefold()
                    if not canonical_raw or canonical_raw in raw_header_ids:
                        raise ValueError(f"blank or duplicate cell barcode in {member.name}: {raw_id!r}")
                    raw_header_ids.add(canonical_raw)
                    record = _resolve_header_barcode(raw_id, annotation_aliases)
                    if record is None:
                        continue
                    matched_counts[record["barcode"]] += 1
                    if matched_counts[record["barcode"]] > 1:
                        raise ValueError(f"annotated barcode appears in multiple raw columns: {record['barcode']}")
                    matched_columns.append((column_index, record))

                seen_candidate_rows: set[str] = set()
                for line, row in enumerate(reader, start=2):
                    if len(row) != len(header):
                        raise ValueError(f"ragged count row in {member.name} line {line}: {len(row)} != {len(header)}")
                    gene = row[0].strip()
                    if gene not in candidate_by_gene:
                        continue
                    if gene in seen_candidate_rows:
                        raise ValueError(f"duplicate raw feature row for {gene} in {member.name}")
                    seen_candidate_rows.add(gene)
                    feature_members[gene] += 1
                    for column_index, record in matched_columns:
                        count = _count(row[column_index], gene, member.name)
                        feature_cells[gene] += 1
                        feature_positive[gene] += int(count > 0)
                        key = (
                            gene, record["cell_group"], record["cluster_id"], record["cluster_label"],
                            record["condition"], record["replicate"], record["phase_hours"],
                        )
                        values = aggregate[key]
                        values[0] += 1
                        values[1] += int(count > 0)
                        values[2] += count

    annotation_ids = {record["barcode"] for record in annotation_records}
    unmatched = sorted(annotation_ids - set(matched_counts))
    multi_matched = sorted(barcode for barcode, count in matched_counts.items() if count != 1)
    join_complete = not unmatched and not multi_matched and len(annotation_ids) == len(matched_counts)

    sample_rows: list[dict[str, str]] = []
    for key, values in sorted(aggregate.items(), key=lambda item: (
        item[0][0], GROUP_ORDER.index(item[0][1]), item[0][2], item[0][4], item[0][5], item[0][6]
    )):
        gene, group, cluster, label, condition, replicate, phase = key
        n_cells, n_positive, sum_counts = values
        sample_rows.append({
            "candidate": gene,
            "priority_class": candidate_by_gene[gene]["priority_class"],
            "cell_group": group,
            "cluster_id": cluster,
            "cluster_label": label,
            "condition": condition,
            "time_system": "ZT" if condition == "LD" else "CT",
            "phase_hours": str(phase),
            "replicate": replicate,
            "n_annotated_cells": str(n_cells),
            "n_cells_detected": str(n_positive),
            "detection_fraction": format(n_positive / n_cells, ".10g") if n_cells else "",
            "sum_raw_counts": str(sum_counts),
            "mean_raw_counts_per_cell": format(sum_counts / n_cells, ".10g") if n_cells else "",
        })

    group_aggregate: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for row in sample_rows:
        key = (row["candidate"], row["cell_group"], row["condition"])
        values = group_aggregate[key]
        values[0] += int(row["n_annotated_cells"])
        values[1] += int(row["n_cells_detected"])
        values[2] += int(row["sum_raw_counts"])
    group_rows: list[dict[str, str]] = []
    for (gene, group, condition), values in sorted(group_aggregate.items(), key=lambda item: (
        item[0][0], GROUP_ORDER.index(item[0][1]), item[0][2]
    )):
        n_cells, n_positive, sum_counts = values
        group_rows.append({
            "candidate": gene,
            "priority_class": candidate_by_gene[gene]["priority_class"],
            "cell_group": group,
            "condition": condition,
            "time_system": "ZT" if condition == "LD" else "CT",
            "n_annotated_cells": str(n_cells),
            "n_cells_detected": str(n_positive),
            "detection_fraction": format(n_positive / n_cells, ".10g") if n_cells else "",
            "sum_raw_counts": str(sum_counts),
            "mean_raw_counts_per_cell": format(sum_counts / n_cells, ".10g") if n_cells else "",
        })

    feature_rows: list[dict[str, str]] = []
    for item in candidates:
        gene = item["gene_symbol"]
        present = feature_members[gene] > 0
        n_cells = feature_cells[gene]
        n_positive = feature_positive[gene]
        feature_rows.append({
            "candidate": gene,
            "priority_class": item["priority_class"],
            "raw_feature_status": "exact_feature_present" if present else "not_represented_in_raw_features_not_evaluable",
            "n_raw_members_with_feature": str(feature_members[gene]),
            "n_annotated_cells_with_feature_counts": str(n_cells),
            "n_cells_detected": str(n_positive),
            "detection_fraction_all_annotated_cells": format(n_positive / n_cells, ".10g") if n_cells else "",
            "interpretation_limit": (
                "raw UMI cell detection only; not normalized abundance, rhythm, protein, current, or causality"
                if present else
                "feature symbol not represented exactly in this matrix; unevaluable here, not evidence of biological absence"
            ),
        })

    observed_grid = {
        (record["condition"], record["replicate"], record["phase_hours"])
        for record in annotation_records
    }
    expected_hours = {2, 6, 10, 14, 18, 22}
    grid_gaps = []
    for condition in ("LD", "DD"):
        for replicate_number in (1, 2):
            replicate = f"{condition}_{replicate_number}"
            absent = sorted(expected_hours - {
                phase for cond, rep, phase in observed_grid if cond == condition and rep == replicate
            })
            if absent:
                grid_gaps.append({"condition": condition, "replicate": replicate, "missing_hours": absent})

    report = {
        "status": "verified_raw_count_cell_detection_join" if join_complete else "partial_raw_count_cell_join",
        "dataset_id": "GSE157504",
        "join": {
            "n_annotation_cells": len(annotation_records),
            "n_unique_annotated_cells_matched_once": len(matched_counts),
            "n_unmatched_annotation_cells": len(unmatched),
            "unmatched_annotation_examples": unmatched[:10],
            "n_raw_matrix_cell_columns": raw_cells_total,
            "n_unannotated_raw_columns": raw_cells_total - len(matched_counts),
            "n_raw_matrix_members": raw_members,
            "join_complete": join_complete,
            "alias_rule": "strip one R-generated leading X; compare case-insensitively; for DD only, normalize annotation _ztNN_ to raw _CTNN_",
        },
        "annotation_time_grid": {
            "expected_hours_per_replicate": sorted(expected_hours),
            "missing_replicate_timepoints": grid_gaps,
            "time_system_rule": "LD is reported as ZT; DD is reported as CT even where the author annotation ID token contains ztNN",
        },
        "candidate_feature_status": feature_rows,
        "methodology_caution": (
            "Detection is the fraction of annotated single cells with raw count > 0. Cells are nested within sample collections/experiments and are not independent fly-level replicates. "
            "This workflow does not normalize counts, test rhythmicity, compare LD with DD, or infer cell-level expression differences."
        ),
        "inference_warning": (
            "Raw UMI detection is descriptive transcript evidence only. A zero may reflect dropout; an unrepresented symbol is unevaluable in this matrix. "
            "Neither supports claims about channel protein, current, membrane potential, or causal behavior control."
        ),
    }
    return sample_rows, group_rows, feature_rows, report


def _write_csv(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def run(
    raw_tar: Path,
    annotation_csv: Path,
    candidate_csv: Path,
    provenance_root: Path,
    expected_hashes: dict[str, str | None] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    expected_hashes = expected_hashes or {}
    input_metadata = {
        "raw_counts": _metadata(raw_tar, provenance_root, expected_hashes.get("raw_counts")),
        "annotation": _metadata(annotation_csv, provenance_root, expected_hashes.get("annotation")),
        "candidate_list": _metadata(candidate_csv, provenance_root, expected_hashes.get("candidate_list")),
    }
    annotation_records, aliases = _load_annotation(annotation_csv)
    candidates = _load_candidates(candidate_csv)
    sample_rows, group_rows, feature_rows, report = _summarize(raw_tar, annotation_records, aliases, candidates)
    report["source_url"] = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504"
    report["inputs"] = input_metadata
    report["software"] = {"python": sys.version.split()[0]}
    return sample_rows, group_rows, feature_rows, report


def _validate_outputs(outputs: dict[str, Path], inputs: tuple[Path, ...], root: Path) -> dict[str, str]:
    paths: dict[str, str] = {}
    resolved_inputs = {path.resolve() for path in inputs}
    resolved_outputs: set[Path] = set()
    for label, path in outputs.items():
        paths[label] = _relative(path, root)
        resolved = path.resolve()
        if resolved in resolved_inputs:
            raise ValueError(f"output path would overwrite an input: {path}")
        if resolved in resolved_outputs:
            raise ValueError(f"output paths must be distinct: {path}")
        resolved_outputs.add(resolved)
    return paths


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_tar", type=Path)
    parser.add_argument("annotation_csv", type=Path)
    parser.add_argument("candidate_csv", type=Path)
    parser.add_argument("--provenance-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-raw-sha256")
    parser.add_argument("--expected-annotation-sha256")
    parser.add_argument("--expected-candidate-sha256")
    parser.add_argument("--sample-output", type=Path, required=True)
    parser.add_argument("--group-output", type=Path, required=True)
    parser.add_argument("--feature-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        outputs = {
            "sample": args.sample_output,
            "group": args.group_output,
            "feature": args.feature_output,
            "report": args.report_output,
        }
        portable_outputs = _validate_outputs(
            outputs, (args.raw_tar, args.annotation_csv, args.candidate_csv), args.provenance_root
        )
        sample_rows, group_rows, feature_rows, report = run(
            args.raw_tar,
            args.annotation_csv,
            args.candidate_csv,
            args.provenance_root,
            {
                "raw_counts": args.expected_raw_sha256,
                "annotation": args.expected_annotation_sha256,
                "candidate_list": args.expected_candidate_sha256,
            },
        )
        _write_csv(args.sample_output, sample_rows, SAMPLE_COLUMNS)
        _write_csv(args.group_output, group_rows, GROUP_COLUMNS)
        _write_csv(args.feature_output, feature_rows, FEATURE_COLUMNS)
        report["outputs"] = {
            label: {"path": portable_outputs[label], "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for label, path in (("sample", args.sample_output), ("group", args.group_output), ("feature", args.feature_output))
        }
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError, csv.Error, tarfile.TarError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": report["status"],
        "n_annotation_cells": report["join"]["n_annotation_cells"],
        "n_unique_annotated_cells_matched_once": report["join"]["n_unique_annotated_cells_matched_once"],
        "n_candidates_with_exact_feature": sum(row["raw_feature_status"] == "exact_feature_present" for row in feature_rows),
    }, ensure_ascii=False))
    return 0 if report["join"]["join_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
