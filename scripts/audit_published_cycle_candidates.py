#!/usr/bin/env python3
"""Cross-check candidate gene symbols against Abruzzi et al. (2017) S3.

This is a read-only audit of the authors' published cycling-transcript lists.
It does not re-normalize expression, re-fit rhythms, or infer that a gene is
non-cycling when it is absent from the supplementary cycler tables.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import hashlib
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterator
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
Q = lambda name: f"{{{MAIN_NS}}}{name}"
TARGET_SHEETS = {
    "LNv_cyclers": {
        "cell_group": "LNv_PDF_positive_small_and_large_mixed",
        "scope_note": "The paper profiles PDF-positive LNvs as a mixed s-LNv/l-LNv group; this table cannot resolve those subtypes.",
    },
    "LNd_cyclers": {
        "cell_group": "LNd_plus_fifth_PDF_negative_s_LNv",
        "scope_note": "The paper's LNd group includes the fifth PDF-negative s-LNv; this table is not LNd-only.",
    },
    "DN1_cyclers": {
        "cell_group": "DN1_subset",
        "scope_note": "The paper profiles a subset of DN1 neurons, not all dorsal clock neurons.",
    },
}
PAPER_REPORTED_HC_COUNTS = {"LNv_cyclers": 249, "LNd_cyclers": 303, "DN1_cyclers": 185}
CSV_FIELDS = [
    "candidate_symbol",
    "cell_group",
    "source_sheet",
    "source_row",
    "source_list_status",
    "published_cycle_class",
    "author_F24_flag",
    "author_JTK_flag",
    "max_min_or_max_if_min_zero",
    "average_expression_source_value",
    "F24_score",
    "F24_phase_ZT",
    "JTK_p_value",
    "JTK_phase_ZT",
    "cell_group_scope_note",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _column_number(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref.upper())
    if not match:
        raise ValueError(f"invalid XLSX cell reference: {cell_ref!r}")
    number = 0
    for char in match.group(1):
        number = number * 26 + ord(char) - ord("A") + 1
    return number


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    result: list[str] = []
    for item in root.findall(Q("si")):
        result.append("".join(node.text or "" for node in item.iter(Q("t"))))
    return result


def _workbook_sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
        if rel.attrib.get("TargetMode") != "External"
    }
    result: dict[str, str] = {}
    for sheet in workbook.findall(f".//{Q('sheet')}"):
        rel_id = sheet.attrib.get(f"{{{DOC_REL_NS}}}id", "")
        if rel_id not in targets:
            raise ValueError(f"XLSX worksheet relationship missing for {sheet.attrib.get('name')!r}")
        target = targets[rel_id].lstrip("/")
        if not target.startswith("xl/"):
            target = posixpath.normpath(posixpath.join("xl", target))
        result[sheet.attrib["name"]] = target
    return result


def _cell_value(cell: ET.Element, strings: list[str]) -> Any:
    kind = cell.attrib.get("t", "")
    if kind == "inlineStr":
        inline = cell.find(Q("is"))
        return "" if inline is None else "".join(node.text or "" for node in inline.iter(Q("t")))
    value = cell.find(Q("v"))
    if value is None or value.text is None:
        return None
    raw = value.text
    if kind == "s":
        index = int(raw)
        if index < 0 or index >= len(strings):
            raise ValueError(f"shared-string index out of range: {index}")
        return strings[index]
    if kind == "b":
        return raw == "1"
    if kind in {"str", "e"}:
        return raw
    if re.fullmatch(r"[-+]?\d+", raw):
        return int(raw)
    try:
        return float(raw)
    except ValueError:
        return raw


def _iter_sheet_rows(
    archive: zipfile.ZipFile, sheet_path: str, strings: list[str],
) -> Iterator[tuple[int, dict[int, Any]]]:
    """Yield populated worksheet rows while pruning parsed XML nodes."""
    with archive.open(sheet_path) as handle:
        stack: list[ET.Element] = []
        for event, element in ET.iterparse(handle, events=("start", "end")):
            if event == "start":
                stack.append(element)
                continue
            if element.tag == Q("row"):
                row_values: dict[int, Any] = {}
                for cell in element.findall(Q("c")):
                    value = _cell_value(cell, strings)
                    if value is not None:
                        row_values[_column_number(cell.attrib["r"])] = value
                if row_values:
                    yield int(element.attrib.get("r", "0")), row_values
                if len(stack) > 1:
                    stack[-2].remove(element)
                element.clear()
            stack.pop()


def _header_indexes(header_values: dict[int, Any]) -> dict[str, int]:
    normalized = {column: _normalize_header(value) for column, value in header_values.items()}

    def find(label: str, predicate) -> int:
        matches = [column for column, value in normalized.items() if predicate(value)]
        if len(matches) != 1:
            raise ValueError(f"expected one {label} column, found {matches}")
        return matches[0]

    indexes = {
        "symbol": find("symbol", lambda value: value.startswith("symbol")),
        "f24_score": find("F24 score", lambda value: value == "f24score"),
        "f24_phase": find("F24 phase", lambda value: value == "f24phase"),
        "jtk_p": find("JTK p-value", lambda value: value == "jtkpvalue"),
        "jtk_phase": find("JTK phase", lambda value: value == "jtkphase"),
        "f24_flag": find("F24 cycler flag", lambda value: value == "f24cycler"),
        "jtk_flag": find("JTK cycler flag", lambda value: value == "jtkcycler"),
        "cycle_class": find("cycling class", lambda value: value == "cycling"),
        "max_min": find("max/min", lambda value: value.startswith("maxmin")),
        "average_expression": find("average expression", lambda value: value.startswith("average")),
    }
    return indexes


def _as_bool(value: Any, criterion: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().casefold()
    if text in {"", "false", "0", "no", "n"}:
        return False
    if text in {"true", "1", "yes", "y"} or _normalize_header(criterion) in _normalize_header(text):
        return True
    raise ValueError(f"unrecognized {criterion} flag value: {value!r}")


def _cycle_class(value: Any) -> str:
    normalized = _normalize_header(value)
    if normalized in {"hccycler", "highconfidencecycler"}:
        return "HC"
    if normalized in {"lccycler", "lowconfidencecycler"}:
        return "LC"
    raise ValueError(f"unrecognized published cycling class: {value!r}")


def _at(row: dict[int, Any], column: int) -> Any:
    return row.get(column)


def read_published_cyclers(
    workbook_path: Path, candidate_symbols: set[str],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    if not workbook_path.is_file() or not zipfile.is_zipfile(workbook_path):
        raise ValueError(f"not a readable XLSX file: {workbook_path}")
    candidates_by_sheet: dict[str, list[dict[str, Any]]] = {name: [] for name in TARGET_SHEETS}
    sheet_qc: list[dict[str, Any]] = []
    with zipfile.ZipFile(workbook_path) as archive:
        strings = _shared_strings(archive)
        sheet_paths = _workbook_sheet_paths(archive)
        missing = sorted(set(TARGET_SHEETS) - set(sheet_paths))
        if missing:
            raise ValueError(f"published workbook is missing target sheets: {missing}")
        for sheet_name, group in TARGET_SHEETS.items():
            row_iter = _iter_sheet_rows(archive, sheet_paths[sheet_name], strings)
            try:
                header_row_number, header_values = next(row_iter)
            except StopIteration as exc:
                raise ValueError(f"worksheet has no populated header row: {sheet_name}") from exc
            try:
                indexes = _header_indexes(header_values)
            except Exception:
                row_iter.close()
                raise
            n_records = n_hc = n_lc = n_flag_disagreements = 0
            symbol_counts: Counter[str] = Counter()
            symbol_class_counts: dict[str, Counter[str]] = {}
            hc_symbols: set[str] = set()
            lc_symbols: set[str] = set()
            try:
                for row_number, row in row_iter:
                    symbol_value = _at(row, indexes["symbol"])
                    if symbol_value is None or not str(symbol_value).strip():
                        continue
                    symbol = str(symbol_value).strip()
                    symbol_counts[symbol] += 1
                    cycle_class = _cycle_class(_at(row, indexes["cycle_class"]))
                    symbol_class_counts.setdefault(symbol, Counter())[cycle_class] += 1
                    f24_pass = _as_bool(_at(row, indexes["f24_flag"]), "f24cycler")
                    jtk_pass = _as_bool(_at(row, indexes["jtk_flag"]), "jtkcycler")
                    n_records += 1
                    n_hc += cycle_class == "HC"
                    n_lc += cycle_class == "LC"
                    (hc_symbols if cycle_class == "HC" else lc_symbols).add(symbol)
                    if (cycle_class == "HC" and not (f24_pass and jtk_pass)) or (
                        cycle_class == "LC" and f24_pass == jtk_pass
                    ):
                        n_flag_disagreements += 1
                    if symbol in candidate_symbols:
                        candidates_by_sheet[sheet_name].append({
                            "candidate_symbol": symbol,
                            "source_row": row_number,
                            "published_cycle_class": cycle_class,
                            "author_F24_flag": f24_pass,
                            "author_JTK_flag": jtk_pass,
                            "max_min_or_max_if_min_zero": _at(row, indexes["max_min"]),
                            "average_expression_source_value": _at(row, indexes["average_expression"]),
                            "F24_score": _at(row, indexes["f24_score"]),
                            "F24_phase_ZT": _at(row, indexes["f24_phase"]),
                            "JTK_p_value": _at(row, indexes["jtk_p"]),
                            "JTK_phase_ZT": _at(row, indexes["jtk_phase"]),
                        })
            except Exception:
                row_iter.close()
                raise
            sheet_qc.append({
                "sheet": sheet_name,
                "cell_group": group["cell_group"],
                "header_row": header_row_number,
                "n_published_cycler_rows": n_records,
                "n_HC_rows": n_hc,
                "n_LC_rows": n_lc,
                "n_unique_HC_symbols": len(hc_symbols),
                "n_unique_LC_symbols": len(lc_symbols),
                "n_unique_symbols": len(symbol_counts),
                "duplicate_symbols": [
                    {
                        "symbol": symbol,
                        "n_rows": count,
                        "n_HC_rows": symbol_class_counts[symbol]["HC"],
                        "n_LC_rows": symbol_class_counts[symbol]["LC"],
                    }
                    for symbol, count in sorted(symbol_counts.items()) if count > 1
                ],
                "n_class_flag_disagreements": n_flag_disagreements,
                "flag_columns_resolved_by_header": True,
                "paper_reported_HC_n": PAPER_REPORTED_HC_COUNTS.get(sheet_name),
                "supplement_HC_count_matches_paper_text": len(hc_symbols) == PAPER_REPORTED_HC_COUNTS.get(sheet_name),
            })
    return candidates_by_sheet, sheet_qc


def read_candidates(path: Path) -> list[str]:
    if not path.is_file():
        raise ValueError(f"candidate CSV does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "candidate" not in reader.fieldnames:
            raise ValueError("candidate CSV must include a 'candidate' column")
        symbols = [str(row.get("candidate") or "").strip() for row in reader]
    if any(not value for value in symbols):
        raise ValueError("candidate CSV contains a blank candidate symbol")
    duplicates = sorted(symbol for symbol in set(symbols) if symbols.count(symbol) > 1)
    if duplicates:
        raise ValueError(f"candidate CSV contains duplicate exact symbols: {duplicates}")
    return symbols


def build_output_rows(
    candidates: list[str], matches_by_sheet: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for symbol in candidates:
        for sheet_name, group in TARGET_SHEETS.items():
            matches = [record for record in matches_by_sheet[sheet_name] if record["candidate_symbol"] == symbol]
            if not matches:
                matches = [{
                    "candidate_symbol": symbol,
                    "source_row": "",
                    "published_cycle_class": "not_listed",
                    "author_F24_flag": "",
                    "author_JTK_flag": "",
                    "max_min_or_max_if_min_zero": "",
                    "average_expression_source_value": "",
                    "F24_score": "",
                    "F24_phase_ZT": "",
                    "JTK_p_value": "",
                    "JTK_phase_ZT": "",
                }]
            for record in matches:
                result.append({
                    "candidate_symbol": symbol,
                    "cell_group": group["cell_group"],
                    "source_sheet": sheet_name,
                    "source_row": record["source_row"],
                    "source_list_status": "listed_as_published_cycler" if record["published_cycle_class"] != "not_listed" else "not_listed_in_published_cycler_supplement",
                    "published_cycle_class": record["published_cycle_class"],
                    "author_F24_flag": record["author_F24_flag"],
                    "author_JTK_flag": record["author_JTK_flag"],
                    "max_min_or_max_if_min_zero": record["max_min_or_max_if_min_zero"],
                    "average_expression_source_value": record["average_expression_source_value"],
                    "F24_score": record["F24_score"],
                    "F24_phase_ZT": record["F24_phase_ZT"],
                    "JTK_p_value": record["JTK_p_value"],
                    "JTK_phase_ZT": record["JTK_phase_ZT"],
                    "cell_group_scope_note": group["scope_note"],
                })
    return result


def audit_published_cycle_candidates(
    workbook_path: Path, candidate_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates = read_candidates(candidate_path)
    matches, sheet_qc = read_published_cyclers(workbook_path, set(candidates))
    rows = build_output_rows(candidates, matches)
    summaries = []
    for symbol in candidates:
        by_group = {}
        for sheet_name, group in TARGET_SHEETS.items():
            found = [r for r in matches[sheet_name] if r["candidate_symbol"] == symbol]
            by_group[group["cell_group"]] = [
                {"cycle_class": r["published_cycle_class"], "source_row": r["source_row"]}
                for r in found
            ]
        summaries.append({
            "candidate_symbol": symbol,
            "listed_in_any_target_group": any(by_group.values()),
            "by_group": by_group,
        })
    count_discrepancies = [
        {
            "sheet": item["sheet"],
            "paper_reported_HC_n": item["paper_reported_HC_n"],
            "supplement_HC_row_count": item["n_HC_rows"],
            "supplement_unique_symbol_HC_count": item["n_unique_HC_symbols"],
            "note": "The manuscript narrative and unique S3 HC symbol count do not agree; both values are preserved without an inferred reconciliation.",
        }
        for item in sheet_qc if not item["supplement_HC_count_matches_paper_text"]
    ]
    report = {
        "status": "executed_with_source_count_discrepancy" if count_discrepancies else "executed_published_cycle_table_audit",
        "source": {
            "article_title": "RNA-seq analysis of Drosophila clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides",
            "citation": "Abruzzi KC, Zadina A, Luo W, Wiyanto E, Rahman R, Guo F, et al. PLoS Genet. 13, e1006613 (2017).",
            "article_url": "https://doi.org/10.1371/journal.pgen.1006613",
            "supplementary_file": "S3 File",
            "supplementary_doi": "https://doi.org/10.1371/journal.pgen.1006613.s003",
            "workbook_sha256": _sha256(workbook_path),
            "candidate_list_sha256": _sha256(candidate_path),
        },
        "matching": {
            "input_key": "candidate CSV 'candidate' field",
            "source_key": "S3 worksheet symbol column",
            "rule": "case-sensitive exact full-symbol match after trimming surrounding whitespace; no fuzzy matching, capitalization changes or inferred synonyms",
            "candidate_count": len(candidates),
            "target_group_count": len(TARGET_SHEETS),
            "candidate_group_rows": len(rows),
        },
        "published_method_as_reported": {
            "sampling": "Two independent six-timepoint time courses at four-hour intervals; LNvs and LNds sampled at ZT2, 6, 10, 14, 18, 22; DN1s sampled at ZT3, 7, 11, 15, 19, 23, under light:dark conditions.",
            "HC_definition": "The paper defines high-confidence cyclers as passing both JTK_cycle and F24; reported cutoffs include JTK p<0.05, F24 score>0.5, amplitude>2-fold and average reads>5.",
            "LC_definition": "The paper defines low-confidence cyclers as passing only one of JTK_cycle or F24.",
            "this_audit_recomputed_rhythm_statistics": False,
            "phase_units": "ZT hours as reported by the authors",
        },
        "sheet_qc": sheet_qc,
        "manuscript_vs_supplement_count_discrepancies": count_discrepancies,
        "candidate_summary": summaries,
        "interpretation_limits": [
            "These are author-reported transcript-cycling calls, not evidence for rhythmic channel protein abundance, membrane current, membrane potential or causal behavioral function.",
            "No row in S3 means only that no exact-symbol entry was found in the selected published cycler table; it does not establish absent expression or biological arrhythmicity.",
            "The source groups do not resolve s-LNv from l-LNv, LNd from the fifth PDF-negative s-LNv, or all DN subgroups from the profiled DN1 subset.",
            "The supplementary workbook lists gene symbols rather than transcript accessions; exact symbol matching does not resolve transcript isoforms.",
            "The published libraries represent pooled isolated neurons; the candidate cross-check does not recover individual-fly metadata or biological replicate identity.",
        ],
    }
    return report, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report, rows = audit_published_cycle_candidates(args.workbook, args.candidates)
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "candidate_count": report["matching"]["candidate_count"], "candidate_group_rows": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
