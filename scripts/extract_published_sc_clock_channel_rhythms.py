#!/usr/bin/env python3
"""Extract candidate-channel rhythm calls from the published GSE157504 supplement.

This transcribes author-reported high-confidence single-cell transcript rhythm
rows. It does not refit rhythmicity models or infer channel activity. Requires
openpyxl to read the official eLife supplementary workbook.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DETAIL_COLUMNS = (
    "candidate", "priority_class", "condition", "cluster", "author_rhythm_class",
    "F24_score", "phase_F24_reported", "F24_p_value", "JTK_p_value",
    "JTK_BH_q_value", "max_TP10K", "min_TP10K", "max_min_ratio", "source_sheet",
)
SUMMARY_COLUMNS = (
    "candidate", "priority_class", "published_rhythm_status", "n_author_reported_rows",
    "conditions", "clusters", "interpretation_limit",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path must be inside provenance root: {path}") from exc


def _file_metadata(path: Path, root: Path, expected_sha256: str | None) -> dict[str, Any]:
    observed = sha256_file(path)
    expected = (expected_sha256 or "").strip().lower()
    if expected and observed != expected:
        raise ValueError(f"SHA-256 mismatch for {path}: expected {expected}, observed {observed}")
    return {
        "path": _portable_path(path, root),
        "size_bytes": path.stat().st_size,
        "sha256": observed,
        "integrity": "verified_sha256" if expected else "hash_recorded_not_verified",
    }


def _load_candidates(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = {"gene_symbol", "priority_class"} - fields
        if missing:
            raise ValueError(f"candidate CSV missing columns: {sorted(missing)}")
        candidates = [
            {"gene_symbol": (row.get("gene_symbol") or "").strip(),
             "priority_class": (row.get("priority_class") or "").strip()}
            for row in reader
        ]
    candidates = [row for row in candidates if row["gene_symbol"]]
    missing_priority = [row["gene_symbol"] for row in candidates if not row["priority_class"]]
    if missing_priority:
        raise ValueError(f"candidate CSV has blank priority_class for: {missing_priority}")
    symbols = [row["gene_symbol"] for row in candidates]
    if len(symbols) != len(set(symbols)):
        raise ValueError("candidate CSV contains duplicate gene_symbol values")
    if not candidates:
        raise ValueError("candidate CSV contains no candidate genes")
    return candidates


def _format_number(value: Any, field: str, row_number: int) -> str:
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric {field} in supplement row {row_number}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite {field} in supplement row {row_number}: {value!r}")
    return format(number, ".10g")


def _validate_output_paths(
    outputs: dict[str, Path], inputs: tuple[Path, ...], provenance_root: Path
) -> dict[str, str]:
    portable: dict[str, str] = {}
    resolved_outputs: set[Path] = set()
    resolved_inputs = {path.resolve() for path in inputs}
    for label, path in outputs.items():
        portable[label] = _portable_path(path, provenance_root)
        resolved = path.resolve()
        if resolved in resolved_outputs:
            raise ValueError(f"output paths must be distinct: {path}")
        if resolved in resolved_inputs:
            raise ValueError(f"output path would overwrite an input: {path}")
        resolved_outputs.add(resolved)
    return portable


def _extract_workbook(
    workbook: Any,
    candidates: list[dict[str, str]],
    candidate_meta: dict[str, Any],
    supplement_meta: dict[str, Any],
    source_url: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    required_sheets = {"LD condition", "DD condition", "Info"}
    if not required_sheets.issubset(set(workbook.sheetnames)):
        raise ValueError(f"supplement workbook missing sheets: {sorted(required_sheets - set(workbook.sheetnames))}")

    candidate_by_symbol = {row["gene_symbol"]: row for row in candidates}
    detail_rows: list[dict[str, str]] = []
    scanned_rows: dict[str, int] = {}
    rhythmic_class_by_candidate: dict[str, set[str]] = defaultdict(set)
    conditions_by_candidate: dict[str, set[str]] = defaultdict(set)
    clusters_by_candidate: dict[str, set[str]] = defaultdict(set)
    seen_keys: set[tuple[str, str, str]] = set()
    for condition, sheet_name in (("LD", "LD condition"), ("DD", "DD condition")):
        sheet = workbook[sheet_name]
        iterator = sheet.iter_rows(values_only=True)
        try:
            header = [str(value or "").strip() for value in next(iterator)]
        except StopIteration as exc:
            raise ValueError(f"empty supplement sheet: {sheet_name}") from exc
        indexes = {name: index for index, name in enumerate(header)}
        if len(indexes) != len(header):
            raise ValueError(f"duplicate column headers in supplement sheet: {sheet_name}")
        required_fields = (
            "Gene", "cluster", "phase.F24", "F24.p.value", "JTK_pvalue", "JTK_BH.Q",
            "MAX", "MIN", "Max.Min", "cycling.", "Condition",
        )
        missing = [field for field in required_fields if field not in indexes]
        score_field = "F24" if "F24" in indexes else "F24.score" if "F24.score" in indexes else None
        if missing or score_field is None:
            raise ValueError(f"supplement sheet {sheet_name} missing fields: {missing or ['F24/F24.score']}")
        scanned = 0
        for row_number, values in enumerate(iterator, start=2):
            if not values or not values[indexes["Gene"]]:
                continue
            scanned += 1
            gene = str(values[indexes["Gene"]]).strip()
            if gene not in candidate_by_symbol:
                continue
            row_condition = str(values[indexes["Condition"]] or "").strip()
            if row_condition != condition:
                raise ValueError(f"sheet/condition mismatch in {sheet_name} row {row_number}: {row_condition!r}")
            cluster = str(values[indexes["cluster"]] or "").strip()
            if not cluster:
                raise ValueError(f"blank cluster in {sheet_name} row {row_number} for {gene}")
            author_class = str(values[indexes["cycling."]] or "").strip()
            key = (gene, condition, cluster)
            if key in seen_keys:
                raise ValueError(f"duplicate candidate rhythm row: {key}")
            seen_keys.add(key)
            item = candidate_by_symbol[gene]
            detail_rows.append({
                "candidate": gene,
                "priority_class": item["priority_class"],
                "condition": condition,
                "cluster": cluster,
                "author_rhythm_class": author_class,
                "F24_score": _format_number(values[indexes[score_field]], score_field, row_number),
                "phase_F24_reported": _format_number(values[indexes["phase.F24"]], "phase.F24", row_number),
                "F24_p_value": _format_number(values[indexes["F24.p.value"]], "F24.p.value", row_number),
                "JTK_p_value": _format_number(values[indexes["JTK_pvalue"]], "JTK_pvalue", row_number),
                "JTK_BH_q_value": _format_number(values[indexes["JTK_BH.Q"]], "JTK_BH.Q", row_number),
                "max_TP10K": _format_number(values[indexes["MAX"]], "MAX", row_number),
                "min_TP10K": _format_number(values[indexes["MIN"]], "MIN", row_number),
                "max_min_ratio": _format_number(values[indexes["Max.Min"]], "Max.Min", row_number),
                "source_sheet": sheet_name,
            })
            rhythmic_class_by_candidate[gene].add(author_class)
            conditions_by_candidate[gene].add(condition)
            clusters_by_candidate[gene].add(cluster)
        scanned_rows[condition] = scanned

    info_sheet = workbook["Info"]
    criteria_values = [
        str(row[0] or "").strip()
        for row in info_sheet.iter_rows(values_only=True)
        if row and row[0]
    ]
    if not criteria_values:
        raise ValueError("supplement Info sheet has no stated rhythm criteria")

    summary_rows: list[dict[str, str]] = []
    for item in candidates:
        gene = item["gene_symbol"]
        classes = rhythmic_class_by_candidate.get(gene, set())
        has_hc = "HC_cycler" in classes
        summary_rows.append({
            "candidate": gene,
            "priority_class": item["priority_class"],
            "published_rhythm_status": "author_reported_HC_cycler" if has_hc else "not_listed_in_author_HC_cycler_table",
            "n_author_reported_rows": str(sum(row["candidate"] == gene for row in detail_rows)),
            "conditions": ";".join(sorted(conditions_by_candidate.get(gene, set()))),
            "clusters": ";".join(sorted(clusters_by_candidate.get(gene, set()))),
            "interpretation_limit": (
                "author-reported transcript rhythm only; not channel protein, current, membrane-potential or causal evidence"
                if has_hc else
                "not listed among author high-confidence cyclers; does not imply absent expression or no rhythm"
            ),
        })

    try:
        openpyxl_version = version("openpyxl")
    except PackageNotFoundError:
        openpyxl_version = "unknown"
    report: dict[str, Any] = {
        "status": "verified_published_sc_clock_channel_rhythm_extraction",
        "analysis_stage": "published_evidence_extraction",
        "source_url": source_url,
        "inputs": {"candidate_list": candidate_meta, "published_supplement": supplement_meta},
        "software": {"python": sys.version.split()[0], "openpyxl": openpyxl_version},
        "n_candidates": len(candidates),
        "n_supplement_rows_scanned": scanned_rows,
        "n_candidate_cluster_condition_rows": len(detail_rows),
        "n_candidates_with_author_HC_rhythm_rows": sum(
            row["published_rhythm_status"] == "author_reported_HC_cycler" for row in summary_rows
        ),
        "candidate_rows_without_HC_call": [
            row["candidate"] for row in summary_rows
            if row["published_rhythm_status"] != "author_reported_HC_cycler"
        ],
        "author_reported_rhythm_criteria": criteria_values,
        "methodology_caution": (
            "The source paper reports two experiments per condition. Its rhythmicity analysis treated individual cells as replicates for JTK and randomly split cells into two pseudo-replicates for Fourier analysis. "
            "This extraction transcribes published calls; it does not independently re-estimate uncertainty at the biological-experiment level."
        ),
        "inference_warning": (
            "A listed HC_cycler is evidence for author-reported rhythmic mRNA abundance in the named cluster/condition only. "
            "It does not establish channel protein abundance, channel current, membrane-potential rhythm, or causal control of behavior. "
            "An unlisted candidate is not evidence of absent expression or arrhythmicity."
        ),
    }
    return summary_rows, detail_rows, report


def extract(
    candidate_csv: Path,
    supplement_xlsx: Path,
    source_url: str,
    provenance_root: Path,
    expected_candidate_sha256: str | None = None,
    expected_supplement_sha256: str | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    parsed_source_url = urlparse(source_url)
    if parsed_source_url.scheme != "https" or not parsed_source_url.netloc:
        raise ValueError("source_url must be an HTTPS URL")
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to read the published supplementary workbook") from exc
    candidate_meta = _file_metadata(candidate_csv, provenance_root, expected_candidate_sha256)
    supplement_meta = _file_metadata(supplement_xlsx, provenance_root, expected_supplement_sha256)
    candidates = _load_candidates(candidate_csv)
    try:
        workbook = openpyxl.load_workbook(supplement_xlsx, data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError(f"cannot read supplementary XLSX workbook: {supplement_xlsx}") from exc
    try:
        return _extract_workbook(workbook, candidates, candidate_meta, supplement_meta, source_url)
    finally:
        workbook.close()


def _write_csv(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_csv", type=Path)
    parser.add_argument("supplement_xlsx", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--provenance-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-candidate-sha256")
    parser.add_argument("--expected-supplement-sha256")
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        outputs = {"summary": args.summary_output, "details": args.detail_output, "report": args.report_output}
        portable_outputs = _validate_output_paths(
            outputs, (args.candidate_csv, args.supplement_xlsx), args.provenance_root
        )
        summary, details, report = extract(
            args.candidate_csv, args.supplement_xlsx, args.source_url, args.provenance_root,
            args.expected_candidate_sha256, args.expected_supplement_sha256,
        )
        _write_csv(args.summary_output, summary, SUMMARY_COLUMNS)
        _write_csv(args.detail_output, details, DETAIL_COLUMNS)
        report["outputs"] = {
            label: {"path": portable_outputs[label], "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for label, path in (("summary", args.summary_output), ("details", args.detail_output))
        }
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError, RuntimeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": report["status"],
        "n_candidates": report["n_candidates"],
        "n_candidate_cluster_condition_rows": report["n_candidate_cluster_condition_rows"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
