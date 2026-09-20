#!/usr/bin/env python3
"""Build an auditable, non-scoring evidence handoff from GSE157504 outputs.

The script preserves raw UMI detection and author-reported rhythm calls as
separate evidence records. It never converts cell fractions or rhythm-list
membership into a 0-3 candidate score.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_GROUPS = ("s-LNv", "l-LNv", "LNd", "DN")
AMBIGUOUS_GROUPS = {"LN_ITP_ambiguous", "LN_ITP"}
SOURCE_GEO = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504"
SOURCE_PAPER = "https://elifesciences.org/articles/63056"
PAPER_DOI = "DOI:10.7554/eLife.63056"

CANDIDATE_FIELDS = ("gene_symbol", "priority_class")
FEATURE_FIELDS = ("candidate", "priority_class", "raw_feature_status", "n_cells_detected")
GROUP_FIELDS = (
    "candidate", "priority_class", "cell_group", "condition", "time_system",
    "n_annotated_cells", "n_cells_detected", "detection_fraction",
)
RHYTHM_FIELDS = ("candidate", "priority_class", "condition", "cluster", "author_rhythm_class", "F24_score", "phase_F24_reported", "JTK_BH_q_value")
EVIDENCE_FIELDS = (
    "candidate", "class", "organism", "target_cell_scope", "assay", "readout_match", "evidence_label",
    "expression", "electrophysiology", "genetic_tools", "class_match", "rhythmic_evidence", "fly_causal", "cross_species",
    "keep_drop_reason", "sources", "confidence", "evidence_notes",
)
SEARCH_LOG_FIELDS = (
    "record_id", "candidate", "query", "database", "search_date", "source_id", "source_url_or_identifier",
    "source_type", "organism", "target_cell_scope", "assay", "readout_match", "evidence_label", "claim_type",
    "source_support_status", "result_summary", "decision", "decision_reason",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in required if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(missing)}")
        return list(reader)


def _cluster_group(cluster: str) -> str:
    label = cluster.strip().split(":", 1)[-1]
    if label == "s_LNv":
        return "s-LNv"
    if label == "l_LNv":
        return "l-LNv"
    if label.startswith("LNd"):
        return "LNd"
    if label.startswith("DN"):
        return "DN"
    if label.startswith("LN_ITP"):
        return "LN_ITP_ambiguous"
    return "other_or_unmapped"


def _format_detection(rows: list[dict[str, str]]) -> str:
    formatted: list[str] = []
    for row in sorted(rows, key=lambda r: (r["cell_group"], r["condition"])):
        if row["cell_group"] not in (*TARGET_GROUPS, *AMBIGUOUS_GROUPS):
            continue
        formatted.append(
            f"{row['cell_group']} {row['condition']} {row['n_cells_detected']}/{row['n_annotated_cells']} "
            f"(fraction={float(row['detection_fraction']):.6g})"
        )
    return "; ".join(formatted) if formatted else "No eligible annotated cell-group detection rows were present."


def _format_rhythms(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No candidate row was found in the extracted author high-confidence rhythm table; this means not listed under those criteria, not proven arrhythmic."
    parts: list[str] = []
    for row in sorted(rows, key=lambda r: (r["condition"], r["cluster"])):
        group = _cluster_group(row["cluster"])
        parts.append(
            f"{row['condition']} {row['cluster']} [{group}] F24={row['F24_score']}, "
            f"phase={row['phase_F24_reported']}, JTK_BH_q={row['JTK_BH_q_value']}"
        )
    return "; ".join(parts)


def _validate_and_index(
    candidate_rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    rhythm_rows: list[dict[str, str]],
) -> tuple[list[str], dict[str, dict[str, str]], dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    candidates: dict[str, dict[str, str]] = {}
    for row in candidate_rows:
        candidate = row["gene_symbol"].strip()
        priority_class = row["priority_class"].strip()
        if not candidate or not priority_class:
            raise ValueError("candidate list contains an empty gene symbol or priority class")
        if candidate in candidates:
            raise ValueError(f"duplicate candidate symbol: {candidate}")
        candidates[candidate] = {"candidate": candidate, "priority_class": priority_class}

    features: dict[str, dict[str, str]] = {}
    for row in feature_rows:
        candidate = row["candidate"].strip()
        if candidate in features:
            raise ValueError(f"duplicate raw feature-status row for {candidate}")
        if candidate not in candidates or row["priority_class"].strip() != candidates[candidate]["priority_class"]:
            raise ValueError(f"feature-status candidate/class does not match candidate list: {candidate}")
        try:
            int(row["n_cells_detected"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid all-cell detected count for {candidate}") from exc
        features[candidate] = row
    if set(features) != set(candidates):
        raise ValueError("feature-status candidate set must exactly match the candidate list")

    grouped: dict[str, list[dict[str, str]]] = {candidate: [] for candidate in candidates}
    seen_group_keys: set[tuple[str, str, str]] = set()
    for row in group_rows:
        candidate = row["candidate"].strip()
        if candidate not in candidates or row["priority_class"].strip() != candidates[candidate]["priority_class"]:
            raise ValueError(f"group-detection candidate/class does not match candidate list: {candidate}")
        key = (candidate, row["cell_group"].strip(), row["condition"].strip())
        if key in seen_group_keys:
            raise ValueError(f"duplicate pooled group/condition detection row: {key}")
        seen_group_keys.add(key)
        condition = row["condition"].strip()
        expected_time = {"LD": "ZT", "DD": "CT"}.get(condition)
        if expected_time is None or row["time_system"].strip() != expected_time:
            raise ValueError(f"condition/time-system mismatch for {candidate}: {condition}/{row['time_system']}")
        try:
            n_total = int(row["n_annotated_cells"])
            n_detected = int(row["n_cells_detected"])
            fraction = float(row["detection_fraction"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid detection counts/fraction for {key}") from exc
        if n_total < 0 or n_detected < 0 or n_detected > n_total or not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError(f"out-of-range detection counts/fraction for {key}")
        if n_total and abs(fraction - n_detected / n_total) > 1e-6:
            raise ValueError(f"detection fraction does not agree with counts for {key}")
        grouped[candidate].append(row)

    rhythms: dict[str, list[dict[str, str]]] = {candidate: [] for candidate in candidates}
    for row in rhythm_rows:
        candidate = row["candidate"].strip()
        if candidate not in candidates or row["priority_class"].strip() != candidates[candidate]["priority_class"]:
            raise ValueError(f"rhythm-table candidate/class does not match candidate list: {candidate}")
        if row["author_rhythm_class"].strip() != "HC_cycler":
            raise ValueError(f"unexpected author rhythm class for {candidate}: {row['author_rhythm_class']}")
        if row["condition"].strip() not in {"LD", "DD"}:
            raise ValueError(f"unexpected rhythm-table condition for {candidate}: {row['condition']}")
        rhythms[candidate].append(row)
    return list(candidates), candidates, grouped, rhythms


def _raw_log_row(candidate: str, candidate_class: str, feature: dict[str, str], groups: list[dict[str, str]], search_date: str) -> dict[str, str]:
    target_rows = [row for row in groups if row["cell_group"] in TARGET_GROUPS]
    detected_rows = [row for row in target_rows if int(row["n_cells_detected"]) > 0]
    detected_total = sum(int(row["n_cells_detected"]) for row in detected_rows)
    total_observed = sum(int(row["n_annotated_cells"]) for row in target_rows)
    feature_status = feature["raw_feature_status"]
    if detected_rows:
        label, target, readout, claim, decision = "direct", "direct_target_neuron", "expression_or_localization", "conclusion", "include"
        summary = (
            f"Exact feature status={feature_status}; raw UMI >0 was observed in {detected_total} of "
            f"{total_observed} pooled annotated cells across the named target groups. By group/condition: {_format_detection(groups)}. "
            "This is transcript-detection evidence only; cell counts are not independent fly-level n."
        )
        reason = "Include as direct target-neuron transcript evidence; do not infer protein abundance, channel current, membrane-potential rhythm, or causal behavior."
    else:
        label, target, readout, claim, decision = "unverified", "none_or_unverified", "none_or_unverified", "no_evidence", "conditional"
        summary = (
            f"Exact feature status={feature_status}; no nonzero raw UMI was observed in the pooled target-group rows available in this matrix. "
            f"By group/condition: {_format_detection(groups)}. Zero UMI can reflect dropout; an absent exact feature is not evaluable."
        )
        reason = "Keep conditional and do not label absent expression: single-cell dropout and feature-symbol representation remain possible explanations."
    return {
        "record_id": f"gse157504-raw-umi-{candidate}",
        "candidate": candidate,
        "query": f"GSE157504 raw UMI detection for {candidate} across annotated circadian-neuron groups",
        "database": "NCBI GEO GSE157504",
        "search_date": search_date,
        "source_id": "GSE157504",
        "source_url_or_identifier": SOURCE_GEO,
        "source_type": "GEO",
        "organism": "Drosophila melanogaster",
        "target_cell_scope": target,
        "assay": "single-cell RNA-seq raw UMI count matrix",
        "readout_match": readout,
        "evidence_label": label,
        "claim_type": claim,
        "source_support_status": "checked",
        "result_summary": summary,
        "decision": decision,
        "decision_reason": reason,
    }


def _rhythm_log_row(candidate: str, rhythm_rows: list[dict[str, str]], search_date: str) -> dict[str, str]:
    target_rows = [row for row in rhythm_rows if _cluster_group(row["cluster"]) in TARGET_GROUPS]
    ambiguous_rows = [row for row in rhythm_rows if _cluster_group(row["cluster"]) in AMBIGUOUS_GROUPS]
    if target_rows:
        label, target, readout, claim, decision = "direct", "direct_target_neuron", "expression_or_localization", "conclusion", "include"
        summary = "Author-reported high-confidence rhythm rows in target groups: " + _format_rhythms(target_rows) + ". The extraction transcribes the supplement and does not refit the rhythm model."
        reason = "Include as an author-reported transcript-rhythm call only; preserve the paper's method and biological-replicate limitations."
    elif ambiguous_rows:
        label, target, readout, claim, decision = "unverified", "none_or_unverified", "none_or_unverified", "no_evidence", "conditional"
        summary = "Rows were found only in the mixed LN_ITP cluster: " + _format_rhythms(ambiguous_rows) + ". Do not assign them to pure s-LNv or LNd."
        reason = "Conditional only: the cell class is mixed and not attributable to a pure target group."
    else:
        label, target, readout, claim, decision = "unverified", "none_or_unverified", "none_or_unverified", "no_evidence", "conditional"
        summary = "No target-group candidate row was found in the authors' high-confidence rhythm table. This means not listed under the authors' criteria, not proven arrhythmic."
        reason = "Keep conditional; absence from a high-confidence call list is not proof of no rhythm."
    return {
        "record_id": f"gse157504-author-rhythm-{candidate}",
        "candidate": candidate,
        "query": f"GSE157504 Supplementary file 1 high-confidence rhythm rows for {candidate}",
        "database": "eLife Supplementary file 1",
        "search_date": search_date,
        "source_id": PAPER_DOI,
        "source_url_or_identifier": SOURCE_PAPER,
        "source_type": "primary_paper",
        "organism": "Drosophila melanogaster",
        "target_cell_scope": target,
        "assay": "author-reported high-confidence single-cell transcript-rhythm table",
        "readout_match": readout,
        "evidence_label": label,
        "claim_type": claim,
        "source_support_status": "checked",
        "result_summary": summary,
        "decision": decision,
        "decision_reason": reason,
    }


def build_rows(
    candidate_rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    rhythm_rows: list[dict[str, str]],
    search_date: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    dt.date.fromisoformat(search_date)
    candidate_order, candidates, grouped, rhythms = _validate_and_index(candidate_rows, feature_rows, group_rows, rhythm_rows)
    feature_by_candidate = {row["candidate"].strip(): row for row in feature_rows}
    evidence: list[dict[str, str]] = []
    log: list[dict[str, str]] = []
    direct_expression = 0
    direct_rhythm = 0
    for candidate in candidate_order:
        item = candidates[candidate]
        feature = feature_by_candidate[candidate]
        detections = grouped[candidate]
        candidate_rhythms = rhythms[candidate]
        raw_record = _raw_log_row(candidate, item["priority_class"], feature, detections, search_date)
        rhythm_record = _rhythm_log_row(candidate, candidate_rhythms, search_date)
        log.extend((raw_record, rhythm_record))
        has_direct_expression = raw_record["evidence_label"] == "direct"
        has_direct_rhythm = rhythm_record["evidence_label"] == "direct"
        direct_expression += int(has_direct_expression)
        direct_rhythm += int(has_direct_rhythm)
        direct = has_direct_expression or has_direct_rhythm
        target_scope = "direct_target_neuron" if direct else "none_or_unverified"
        readout = "expression_or_localization" if direct else "none_or_unverified"
        label = "direct" if direct else "unverified"
        detection_text = _format_detection(detections)
        rhythm_text = _format_rhythms(candidate_rhythms)
        if not candidate_rhythms:
            rhythm_text = "No row in the author high-confidence table; not listed does not mean arrhythmic."
        feature_status = feature["raw_feature_status"]
        if feature_status != "exact_feature_present":
            reason = "Retain as conditional/unevaluable: the exact symbol is absent from this raw feature table; this is not evidence of biological absence."
            confidence = "low; exact-symbol matrix representation unresolved"
        elif direct:
            reason = "Retain on the candidate long list as transcript-level evidence only; this dataset does not measure channel protein, current, membrane potential, or behavioral causality."
            confidence = "moderate for transcript detection/rhythm-list membership only; function untested"
        else:
            reason = "Retain conditionally: zero UMI and/or no author high-confidence rhythm row cannot establish absence because of dropout and author cutoffs."
            confidence = "low for expression/rhythm absence; not a negative biological result"
        evidence.append({
            "candidate": candidate,
            "class": item["priority_class"],
            "organism": "Drosophila melanogaster",
            "target_cell_scope": target_scope,
            "assay": "single-cell RNA-seq raw UMI detection and author-reported rhythm-table extraction",
            "readout_match": readout,
            "evidence_label": label,
            "expression": "NA",
            "electrophysiology": "NA",
            "genetic_tools": "NA",
            "class_match": "NA",
            "rhythmic_evidence": "NA",
            "fly_causal": "NA",
            "cross_species": "NA",
            "keep_drop_reason": reason,
            "sources": f"GSE157504; {SOURCE_GEO}; {PAPER_DOI}; {SOURCE_PAPER}",
            "confidence": confidence,
            "evidence_notes": (
                f"Exact feature status={feature_status}. Raw UMI detection by target group/condition: {detection_text}. "
                f"Author rhythm-table rows: {rhythm_text}. All numeric ranking dimensions are deliberately NA because no validated 0-3 rubric maps these transcript-level summaries to a candidate score. "
                "Evidence is transcript-level only; cells are nested observations, zero counts may reflect dropout, and LN_ITP is a mixed class not assigned to pure s-LNv/LNd."
            ),
        })
    report = {
        "status": "executed_gse157504_candidate_evidence_bridge",
        "n_candidates": len(evidence),
        "n_search_log_records": len(log),
        "n_with_direct_target_group_raw_umi_detection": direct_expression,
        "n_with_author_high_confidence_rhythm_rows_in_target_groups": direct_rhythm,
        "n_candidates_with_all_ranking_dimensions_unrated": sum(all(row[field] == "NA" for field in EVIDENCE_FIELDS[7:14]) for row in evidence),
        "ranking_policy": "No 0-3 scores are assigned by this bridge. Feed the evidence rows into the candidate workflow, add separately sourced evidence, then score only after an explicit rubric is justified.",
        "inference_warning": "Raw UMI detection and author rhythm-list membership are transcript evidence only; neither establishes channel current, membrane-potential rhythm, behavior causality, or animal-level inference. Missing UMI/call rows do not prove biological absence or arrhythmicity.",
    }
    return evidence, log, report


def _write_csv(path: Path, rows: list[dict[str, str]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(
    candidate_csv: Path,
    feature_csv: Path,
    group_csv: Path,
    rhythm_csv: Path,
    evidence_output: Path,
    search_log_output: Path,
    report_output: Path,
    provenance_root: Path,
    expected_hashes: dict[str, str | None] | None = None,
    search_date: str | None = None,
) -> dict[str, Any]:
    root = provenance_root.resolve()
    inputs = {"candidate_list": candidate_csv, "feature_status": feature_csv, "group_detection": group_csv, "rhythm_details": rhythm_csv}
    expected_hashes = expected_hashes or {}
    input_hashes: dict[str, str] = {}
    for key, path in inputs.items():
        actual = _sha256(path)
        expected = expected_hashes.get(key)
        if expected and actual.lower() != expected.lower():
            raise ValueError(f"{key} input hash mismatch: expected {expected}, observed {actual}")
        input_hashes[key] = actual
    outputs = {"candidate_evidence": evidence_output, "evidence_search_log": search_log_output, "report": report_output}
    resolved_inputs = {path.resolve() for path in inputs.values()}
    resolved_outputs: set[Path] = set()
    output_paths: dict[str, str] = {}
    for label, path in outputs.items():
        resolved = path.resolve()
        if resolved in resolved_inputs:
            raise ValueError(f"output path would overwrite an input: {path}")
        if resolved in resolved_outputs:
            raise ValueError(f"output paths must be distinct: {path}")
        try:
            output_paths[label] = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"output must remain inside provenance root: {path}") from exc
        resolved_outputs.add(resolved)
    candidate_rows = _read_csv(candidate_csv, CANDIDATE_FIELDS)
    feature_rows = _read_csv(feature_csv, FEATURE_FIELDS)
    group_rows = _read_csv(group_csv, GROUP_FIELDS)
    rhythm_rows = _read_csv(rhythm_csv, RHYTHM_FIELDS)
    date = search_date or dt.datetime.now(dt.timezone.utc).date().isoformat()
    evidence, log, report = build_rows(candidate_rows, feature_rows, group_rows, rhythm_rows, date)
    _write_csv(evidence_output, evidence, EVIDENCE_FIELDS)
    _write_csv(search_log_output, log, SEARCH_LOG_FIELDS)
    report["search_date"] = date
    report["input_sha256"] = input_hashes
    report["output_paths"] = output_paths
    report["output_sha256"] = {key: _sha256(path) for key, path in outputs.items() if key != "report"}
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_list", type=Path)
    parser.add_argument("feature_status", type=Path)
    parser.add_argument("group_detection", type=Path)
    parser.add_argument("rhythm_details", type=Path)
    parser.add_argument("--provenance-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--expected-feature-sha256", required=True)
    parser.add_argument("--expected-group-sha256", required=True)
    parser.add_argument("--expected-rhythm-sha256", required=True)
    parser.add_argument("--search-date", required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--search-log-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        report = run(
            args.candidate_list,
            args.feature_status,
            args.group_detection,
            args.rhythm_details,
            args.evidence_output,
            args.search_log_output,
            args.report_output,
            args.provenance_root,
            {
                "candidate_list": args.expected_candidate_sha256,
                "feature_status": args.expected_feature_sha256,
                "group_detection": args.expected_group_sha256,
                "rhythm_details": args.expected_rhythm_sha256,
            },
            args.search_date,
        )
    except (OSError, UnicodeDecodeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
