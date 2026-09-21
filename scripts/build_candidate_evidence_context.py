#!/usr/bin/env python3
"""Overlay public transcript context on a literature-scored channel list.

This report is deliberately sidecar-only: public RNA detection/rhythm rows do
not change candidate scores, target-specific electrophysiology gates, or the
underlying evidence table. It verifies upstream manifests and score parity
before producing one row per candidate and target group.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gse157504_candidate_evidence import TARGET_GROUPS, _cluster_group
from scripts.score_candidates import score_row
from scripts.validate_candidate_evidence import validate as validate_candidate_table
from scripts.validate_evidence_search_log import validate as validate_search_log


FEATURE_FIELDS = ("candidate", "priority_class", "raw_feature_status", "n_cells_detected")
GROUP_FIELDS = (
    "candidate", "priority_class", "cell_group", "condition", "time_system",
    "n_annotated_cells", "n_cells_detected", "detection_fraction",
    "sum_raw_counts", "mean_raw_counts_per_cell",
)
RHYTHM_FIELDS = (
    "candidate", "priority_class", "condition", "cluster", "author_rhythm_class", "F24_score",
    "phase_F24_reported", "JTK_BH_q_value",
)
SCORE_FIELDS_TO_COMPARE = (
    "score", "coverage", "directness_score", "directness_gate",
    "shortlist_gate", "scoring_readout_match",
)
CONDITIONS = {"LD": "ZT", "DD": "CT"}
READOUT = "membrane_potential_or_current"
SCRIPT_DEPENDENCIES = (
    "scripts/build_gse157504_candidate_evidence.py",
    "scripts/score_candidates.py",
    "scripts/validate_candidate_evidence.py",
    "scripts/validate_evidence_search_log.py",
)
CSV_FIELDS = (
    "candidate", "literature_class", "priority_class", "target_group", "raw_feature_status", "transcript_evaluable",
    "LD_time_system", "LD_n_annotated_cells", "LD_n_cells_detected", "LD_detection_fraction",
    "LD_sum_raw_counts", "LD_mean_raw_counts_per_cell", "LD_detection_status",
    "DD_time_system", "DD_n_annotated_cells", "DD_n_cells_detected", "DD_detection_fraction",
    "DD_sum_raw_counts", "DD_mean_raw_counts_per_cell", "DD_detection_status",
    "target_author_rhythm_status", "target_author_rhythm_calls", "ambiguous_LN_ITP_rhythm_calls",
    "DN_subcluster_scope_note", "static_rationale_review_flag", "static_rationale_review_note",
    "literature_score", "literature_coverage", "ephys_directness_score", "ephys_directness_gate",
    "shortlist_gate", "scoring_readout_match",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path, required: tuple[str, ...] = ()) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(set(required) - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(missing)}")
        return list(reader)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _csv_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric value for {label}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite numeric value for {label}: {value!r}")
    return result


def _close(left: Any, right: Any) -> bool:
    def parse(value: Any) -> float | None:
        if value is None or str(value).strip().upper() in {"", "NA", "N/A", "NONE", "NULL"}:
            return None
        return float(value)
    a, b = parse(left), parse(right)
    return a is None and b is None or a is not None and b is not None and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)


def _parent_chain(manifest_path: Path, validation_path: Path, replay_path: Path, required_paths: set[str], root: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    validation = _read_json(validation_path)
    replay = _read_json(replay_path)
    if validation.get("status") != "verified_public_dataset_manifest":
        raise ValueError(f"upstream manifest validation is not verified: {validation.get('status')}")
    if validation.get("manifest_id") != manifest.get("manifest_id"):
        raise ValueError("upstream manifest validation ID does not match its manifest")
    if replay.get("status") != "verified_public_dataset_replay":
        raise ValueError(f"upstream isolated replay is not verified: {replay.get('status')}")
    replay_validation = replay.get("manifest_validation") or {}
    if replay_validation.get("status") != "verified_public_dataset_manifest" or replay_validation.get("manifest_id") != manifest.get("manifest_id"):
        raise ValueError("upstream isolated replay is not bound to the verified upstream manifest")
    file_records = {str(record.get("path")): record for record in manifest.get("files", []) if isinstance(record, dict)}
    checked_files = {str(check.get("path")): check for check in validation.get("file_checks", []) if isinstance(check, dict)}
    replay_outputs = {str(check.get("path")): check for check in replay.get("output_checks", []) if isinstance(check, dict)}
    input_hashes: dict[str, str] = {}
    for relative in sorted(required_paths):
        record = file_records.get(relative)
        check = checked_files.get(relative)
        if not record or not check or check.get("status") != "hash_verified":
            raise ValueError(f"required GSE input is not hash-verified by the parent manifest: {relative}")
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"upstream path escapes repository root: {relative}") from exc
        observed = _sha256(path)
        declared = str(record.get("sha256") or "").lower()
        if observed != declared or observed != str(check.get("observed_sha256") or "").lower():
            raise ValueError(f"upstream GSE input hash mismatch: {relative}")
        # Derived GSE files must also have been reproduced by isolated replay.
        if record.get("role") == "derived":
            replay_check = replay_outputs.get(relative)
            if not replay_check or replay_check.get("status") != "replay_hash_verified" or replay_check.get("observed_sha256") != observed:
                raise ValueError(f"upstream GSE derived input is not replay-verified: {relative}")
        input_hashes[relative] = observed
    return {
        "manifest_id": manifest.get("manifest_id"),
        "manifest_status": validation.get("status"),
        "replay_status": replay.get("status"),
        "input_sha256": input_hashes,
        "source_url": manifest.get("source_url"),
    }


def _rhythm_call(row: dict[str, str]) -> dict[str, Any]:
    return {
        "condition": row["condition"].strip(),
        "time_system": CONDITIONS[row["condition"].strip()],
        "cluster": row["cluster"].strip(),
        "mapped_group": _cluster_group(row["cluster"]),
        "author_rhythm_class": row["author_rhythm_class"].strip(),
        "F24_score": _float(row["F24_score"], "F24_score"),
        "phase_F24_reported": _float(row["phase_F24_reported"], "phase_F24_reported"),
        "JTK_BH_q_value": _float(row["JTK_BH_q_value"], "JTK_BH_q_value"),
    }


def _dn_target(group: str) -> bool:
    return group == "DN" or group in {"DN1", "DN1p", "DN1a", "DN2", "DN3"}


def _gap_rationale(reason: str) -> bool:
    text = reason.casefold()
    gap = re.search(r"\b(missing|lack(?:ing)?|absent|no)\b", text)
    target_gap = "target" in text and any(token in text for token in ("neuron", "cell", "clock"))
    rhythm_gap = any(token in text for token in ("circadian", "rhythm", "rhythmic"))
    return bool(gap and target_gap and rhythm_gap)


def build_context_rows(
    candidate_rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    rhythm_rows: list[dict[str, str]],
    target_score_rows: dict[str, dict[str, dict[str, str]]],
    search_log_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, str]] = {}
    for row in candidate_rows:
        gene = (row.get("candidate") or "").strip()
        if not gene or gene in candidates:
            raise ValueError(f"candidate table has missing or duplicate candidate: {gene!r}")
        candidates[gene] = row
    features: dict[str, dict[str, str]] = {}
    for row in feature_rows:
        gene = row["candidate"].strip()
        if gene in features:
            raise ValueError(f"duplicate GSE feature row: {gene}")
        features[gene] = row

    detections: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in group_rows:
        gene, group, condition = row["candidate"].strip(), row["cell_group"].strip(), row["condition"].strip()
        if gene not in features or condition not in CONDITIONS:
            raise ValueError(f"unexpected group-detection candidate/condition: {gene}/{condition}")
        if row["priority_class"].strip() != features[gene]["priority_class"].strip():
            raise ValueError(f"candidate class differs in group-detection table for {gene}")
        if row["time_system"].strip() != CONDITIONS[condition]:
            raise ValueError(f"condition/time-system mismatch for {gene}/{group}/{condition}")
        try:
            total, detected = int(row["n_annotated_cells"]), int(row["n_cells_detected"])
            fraction = _float(row["detection_fraction"], "detection_fraction")
            _float(row["sum_raw_counts"], "sum_raw_counts")
            _float(row["mean_raw_counts_per_cell"], "mean_raw_counts_per_cell")
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid group-detection values for {gene}/{group}/{condition}: {exc}") from exc
        if total < 0 or detected < 0 or detected > total or not 0 <= fraction <= 1:
            raise ValueError(f"out-of-range group-detection values for {gene}/{group}/{condition}")
        if total and not math.isclose(fraction, detected / total, rel_tol=0, abs_tol=1e-6):
            raise ValueError(f"detection fraction disagrees with counts for {gene}/{group}/{condition}")
        key = (gene, group, condition)
        if key in detections:
            raise ValueError(f"duplicate group-detection row: {key}")
        detections[key] = row

    rhythms: dict[str, list[dict[str, Any]]] = {gene: [] for gene in candidates}
    for row in rhythm_rows:
        gene, condition = row["candidate"].strip(), row["condition"].strip()
        if gene not in features or condition not in CONDITIONS or row["author_rhythm_class"].strip() != "HC_cycler":
            raise ValueError(f"unexpected author rhythm row: {gene}/{condition}")
        if row["priority_class"].strip() != features[gene]["priority_class"].strip():
            raise ValueError(f"candidate class differs in rhythm table for {gene}")
        call = _rhythm_call(row)
        if not 0 <= call["F24_score"] <= 1 or not 0 <= call["JTK_BH_q_value"] <= 1:
            raise ValueError(f"out-of-range author rhythm statistic for {gene}/{condition}/{row['cluster']}")
        if gene in rhythms:
            rhythms[gene].append(call)

    out: list[dict[str, Any]] = []
    for gene, candidate in candidates.items():
        feature = features.get(gene)
        raw_status = feature["raw_feature_status"].strip() if feature else "candidate_not_in_upstream_audit_not_evaluable"
        evaluable = raw_status == "exact_feature_present"
        for target in TARGET_GROUPS:
            group_values: dict[str, dict[str, Any]] = {}
            for condition in ("LD", "DD"):
                match = detections.get((gene, target, condition))
                if evaluable and match is None:
                    raise ValueError(f"missing target group/condition detection row for evaluable feature: {gene}/{target}/{condition}")
                if not evaluable:
                    values = {
                        "time_system": CONDITIONS[condition], "n_annotated_cells": "NA", "n_cells_detected": "NA",
                        "detection_fraction": "NA", "sum_raw_counts": "NA", "mean_raw_counts_per_cell": "NA",
                        "status": "candidate_not_in_upstream_audit_not_evaluable" if feature is None else "feature_not_evaluable_not_biological_absence",
                    }
                else:
                    assert match is not None
                    total, detected = int(match["n_annotated_cells"]), int(match["n_cells_detected"])
                    if total == 0:
                        status = "no_annotated_cells_no_detection_inference"
                    elif detected == 0:
                        status = "zero_UMI_dropout_sensitive_not_absent"
                    else:
                        status = "raw_UMI_detected_descriptive_only"
                    values = {
                        "time_system": match["time_system"].strip(),
                        "n_annotated_cells": total,
                        "n_cells_detected": detected,
                        "detection_fraction": _float(match["detection_fraction"], "detection_fraction"),
                        "sum_raw_counts": _float(match["sum_raw_counts"], "sum_raw_counts"),
                        "mean_raw_counts_per_cell": _float(match["mean_raw_counts_per_cell"], "mean_raw_counts_per_cell"),
                        "status": status,
                    }
                group_values[condition] = values

            calls = rhythms[gene]
            if target == "DN":
                target_calls = [call for call in calls if _dn_target(str(call["mapped_group"]))]
            else:
                target_calls = [call for call in calls if call["mapped_group"] == target]
            ambiguous_calls = [call for call in calls if call["mapped_group"] == "LN_ITP_ambiguous"]
            has_public_context = any(
                isinstance(group_values[c]["n_cells_detected"], int) and group_values[c]["n_cells_detected"] > 0
                for c in ("LD", "DD")
            ) or bool(target_calls)
            static_reason = candidate.get("keep_drop_reason", "")
            flag_static = _gap_rationale(static_reason) and has_public_context
            score = score_row(candidate, target_cells=[target], evidence_log=search_log_rows, readout_match=READOUT)
            expected = target_score_rows[target].get(gene)
            if expected is None:
                raise ValueError(f"target score file is missing candidate {gene} for {target}")
            for field in SCORE_FIELDS_TO_COMPARE:
                actual_value, expected_value = score.get(field), expected.get(field)
                if field in {"score", "coverage", "directness_score"}:
                    equal = _close(actual_value, expected_value)
                else:
                    equal = str(actual_value if actual_value is not None else "") == str(expected_value if expected_value is not None else "")
                if not equal:
                    raise ValueError(f"score/gate parity mismatch for {gene}/{target}/{field}: {actual_value!r} != {expected_value!r}")
            dn_note = "DN rhythm calls remain exact cluster/subcluster calls; a DN1p/DN2/etc. call is not evidence for all DN." if target == "DN" else ""
            row: dict[str, Any] = {
                "candidate": gene,
                "literature_class": candidate.get("class", ""),
                "priority_class": feature.get("priority_class", "NA") if feature else "NA",
                "target_group": target,
                "raw_feature_status": raw_status,
                "transcript_evaluable": "yes" if evaluable else "no",
                "target_author_rhythm_status": (
                    "candidate_not_in_upstream_audit_rhythm_status_not_evaluable" if feature is None
                    else "HC_call_listed_in_target_group" if target_calls
                    else "not_listed_under_author_HC_criteria_not_proven_arrhythmic"
                ),
                "target_author_rhythm_calls": "NA" if feature is None else _json_text(target_calls),
                "ambiguous_LN_ITP_rhythm_calls": "NA" if feature is None else _json_text(ambiguous_calls),
                "DN_subcluster_scope_note": dn_note,
                "static_rationale_review_flag": "review" if flag_static else "",
                "static_rationale_review_note": (
                    "Static literature rationale says target-neuron/circadian evidence is missing, while this transcript dataset contains target-group context; manually reconcile wording. Scores and ephys gate are unchanged."
                    if flag_static else ""
                ),
                "literature_score": score.get("score"),
                "literature_coverage": score.get("coverage"),
                "ephys_directness_score": score.get("directness_score"),
                "ephys_directness_gate": score.get("directness_gate"),
                "shortlist_gate": score.get("shortlist_gate"),
                "scoring_readout_match": score.get("scoring_readout_match"),
            }
            for condition in ("LD", "DD"):
                values = group_values[condition]
                row.update({
                    f"{condition}_time_system": values["time_system"],
                    f"{condition}_n_annotated_cells": values["n_annotated_cells"],
                    f"{condition}_n_cells_detected": values["n_cells_detected"],
                    f"{condition}_detection_fraction": values["detection_fraction"],
                    f"{condition}_sum_raw_counts": values["sum_raw_counts"],
                    f"{condition}_mean_raw_counts_per_cell": values["mean_raw_counts_per_cell"],
                    f"{condition}_detection_status": values["status"],
                })
            out.append(row)
    return out


def _normal_path(value: Path, root: Path) -> tuple[str, Path]:
    resolved = value.resolve() if value.is_absolute() else (root / value).resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"all manifest inputs/outputs must be inside repository root: {value}") from exc
    if not resolved.is_file() and relative not in {"validation/public-data/GSE157504_candidate_context_overlay.csv", "validation/public-data/GSE157504_candidate_context_overlay_report.json", "validation/public-data/GSE157504-candidate-context-overlay-manifest.json"}:
        raise ValueError(f"file does not exist: {relative}")
    return relative, resolved


def _manifest_payload(paths: dict[str, Path], context_path: Path, report_path: Path, manifest_path: Path, root: Path, argv: list[str], parent: dict[str, Any]) -> dict[str, Any]:
    file_roles: dict[str, str] = {}
    for key, path in paths.items():
        relative, resolved = _normal_path(path, root)
        role = "candidate_list" if key == "candidate_table" else "metadata" if "log" in key or "manifest" in key or "validation" in key or "replay" in key else "derived"
        file_roles[relative] = role
    script_relative = Path(__file__).resolve().relative_to(root.resolve()).as_posix()
    file_roles[script_relative] = "config"
    for relative in SCRIPT_DEPENDENCIES:
        dependency = root / relative
        if not dependency.is_file():
            raise ValueError(f"required script dependency is missing: {relative}")
        file_roles[relative] = "config"
    context_relative, context_resolved = _normal_path(context_path, root)
    report_relative, report_resolved = _normal_path(report_path, root)
    file_roles[context_relative] = "derived"
    file_roles[report_relative] = "derived"
    records = [{"path": rel, "role": role, "sha256": _sha256(root / rel)} for rel, role in sorted(file_roles.items())]
    command_argv = ["python", script_relative, *argv]
    source_manifest = next((path for key, path in paths.items() if key == "rhythm_manifest"), None)
    source_info = _read_json(source_manifest) if source_manifest else {}
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "manifest_id": "GSE157504-candidate-context-overlay-20260921",
        "dataset_id": "GSE157504",
        "accession": "GSE157504",
        "species": "Drosophila melanogaster",
        "source_url": source_manifest and source_info.get("source_url") or "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157504",
        "retrieved_at_utc": now,
        "source_access_status": "content_checked",
        "source_checked_at_utc": source_info.get("source_checked_at_utc", "2026-09-20T07:31:34Z"),
        "source_check_method": source_info.get("source_check_method", "web_open"),
        "source_observed_tokens": source_info.get("source_observed_tokens", ["GSE157504", "Drosophila melanogaster", "single-cell RNA sequencing", "LD", "DD"]),
        "source_observation_note": "The source content check is inherited from the hash-verified GSE157504 parent manifest. This overlay only joins published raw-UMI detection and author-reported rhythm calls with the existing candidate list; it does not perform a new biological assay or infer channel function.",
        "analysis_context": {
            "time_system": "LD is ZT; DD is CT; source labels and reported phase are preserved.",
            "experimental_unit": "Cells are nested within collection replicate; the overlay is descriptive and makes no fly-level inference.",
            "normalization_status": "Raw UMI detection only; no normalization, differential-expression test, or rhythm refit.",
            "biological_unit_limitations": "Zero UMI can reflect dropout; absent exact features are not evaluable; author-list omission is not proof of arrhythmicity; transcript does not establish protein, current, membrane potential, or behavior. LN_ITP remains ambiguous and DN rhythm evidence stays cluster-specific.",
            "upstream_manifest_id": parent["manifest_id"],
            "score_policy": "Literature scores and target-specific electrophysiology gates are recomputed only to verify parity with existing target score artifacts; transcript context never changes them.",
        },
        "files": records,
        "runs": [{
            "run_id": "build-gse157504-candidate-context-overlay",
            "script": script_relative,
            "script_sha256": _sha256(root / script_relative),
            "command": "python " + " ".join(command_argv[1:]),
            "command_argv": command_argv,
            "status": "verified",
            "inputs": sorted(relative for relative in file_roles if relative not in {context_relative, report_relative}),
            "outputs": [context_relative, report_relative],
        }],
    }


def run(args: argparse.Namespace, raw_argv: list[str]) -> dict[str, Any]:
    root = args.root.resolve()
    paths = {
        "candidate_table": args.candidate_table,
        "search_log": args.search_log,
        "feature_status": args.feature_status,
        "group_detection": args.group_detection,
        "rhythm_details": args.rhythm_details,
        "rhythm_manifest": args.rhythm_manifest,
        "rhythm_validation": args.rhythm_validation,
        "rhythm_replay": args.rhythm_replay,
    }
    for key, value in args.target_score:
        if key not in TARGET_GROUPS or key in paths:
            raise ValueError(f"invalid or duplicate target score key: {key}")
        paths[f"score_{key}"] = value
    if {key.removeprefix("score_") for key in paths if key.startswith("score_")} != set(TARGET_GROUPS):
        raise ValueError("provide exactly one --target-score TARGET=CSV for each target group")
    relative_path_map = {name: _normal_path(path, root)[0] for name, path in paths.items()}
    required_gse = {
        relative_path_map["feature_status"], relative_path_map["group_detection"], relative_path_map["rhythm_details"],
    }
    parent = _parent_chain(paths["rhythm_manifest"].resolve() if paths["rhythm_manifest"].is_absolute() else (root / paths["rhythm_manifest"]).resolve(),
                           paths["rhythm_validation"].resolve() if paths["rhythm_validation"].is_absolute() else (root / paths["rhythm_validation"]).resolve(),
                           paths["rhythm_replay"].resolve() if paths["rhythm_replay"].is_absolute() else (root / paths["rhythm_replay"]).resolve(),
                           required_gse, root)

    search_validation = validate_search_log(paths["search_log"] if paths["search_log"].is_absolute() else root / paths["search_log"])
    if search_validation.get("status") != "verified_evidence_search_log":
        raise ValueError(f"candidate source log failed validation: {search_validation.get('issues')}")
    candidate_validation = validate_candidate_table(
        paths["candidate_table"] if paths["candidate_table"].is_absolute() else root / paths["candidate_table"],
        paths["search_log"] if paths["search_log"].is_absolute() else root / paths["search_log"],
    )
    if candidate_validation.get("status") != "verified_candidate_evidence_table":
        raise ValueError(f"candidate evidence table failed validation: {candidate_validation.get('issues')}")

    candidate_rows = _read_csv(paths["candidate_table"] if paths["candidate_table"].is_absolute() else root / paths["candidate_table"])
    search_log_rows = _read_csv(paths["search_log"] if paths["search_log"].is_absolute() else root / paths["search_log"])
    feature_rows = _read_csv(paths["feature_status"] if paths["feature_status"].is_absolute() else root / paths["feature_status"], FEATURE_FIELDS)
    group_rows = _read_csv(paths["group_detection"] if paths["group_detection"].is_absolute() else root / paths["group_detection"], GROUP_FIELDS)
    rhythm_rows = _read_csv(paths["rhythm_details"] if paths["rhythm_details"].is_absolute() else root / paths["rhythm_details"], RHYTHM_FIELDS)
    target_score_rows: dict[str, dict[str, dict[str, str]]] = {}
    for target in TARGET_GROUPS:
        path = paths[f"score_{target}"]
        score_rows = _read_csv(path if path.is_absolute() else root / path, ("candidate", "score", "coverage", "directness_score", "directness_gate", "shortlist_gate", "scoring_readout_match"))
        keyed: dict[str, dict[str, str]] = {}
        for row in score_rows:
            gene = row["candidate"].strip()
            if gene in keyed:
                raise ValueError(f"duplicate candidate in {target} score file: {gene}")
            keyed[gene] = row
        target_score_rows[target] = keyed
        if set(keyed) != {row["candidate"].strip() for row in candidate_rows}:
            raise ValueError(f"candidate set in target score file does not match candidate evidence table: {target}")

    rows = build_context_rows(candidate_rows, feature_rows, group_rows, rhythm_rows, target_score_rows, search_log_rows)
    context_path = args.context_output if args.context_output.is_absolute() else root / args.context_output
    report_path = args.report_output if args.report_output.is_absolute() else root / args.report_output
    manifest_path = args.manifest_output if args.manifest_output.is_absolute() else root / args.manifest_output
    for output_path in (context_path, report_path, manifest_path):
        try:
            output_path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError(f"output must stay inside repository root: {output_path}") from exc

    _csv_write(context_path, rows)
    review_candidates = sorted({row["candidate"] for row in rows if row["static_rationale_review_flag"]})
    report = {
        "status": "verified_candidate_evidence_context_overlay",
        "n_candidates": len(candidate_rows),
        "target_groups": list(TARGET_GROUPS),
        "n_rows": len(rows),
        "candidate_set_difference": {
            "literature_candidates_not_in_GSE_candidate_audit": sorted(
                {row["candidate"].strip() for row in candidate_rows} - {row["candidate"].strip() for row in feature_rows}
            ),
            "GSE_candidates_not_in_literature_table": sorted(
                {row["candidate"].strip() for row in feature_rows} - {row["candidate"].strip() for row in candidate_rows}
            ),
        },
        "row_unit": "one candidate x target group; not an independent biological replicate",
        "candidate_table_validation": candidate_validation["status"],
        "search_log_validation": search_validation["status"],
        "parent_gse_chain": parent,
        "target_score_parity": "verified for score, coverage, directness score/gate, shortlist gate and readout",
        "static_rationales_flagged_for_human_review": review_candidates,
        "interpretation_limits": [
            "Raw UMI detection is descriptive; zero counts are dropout-sensitive and not evidence of biological absence.",
            "A feature absent from the exact matrix symbol list is not evaluable, not biologically absent.",
            "No author HC call means not listed under author criteria, not proven arrhythmic.",
            "LN_ITP calls are kept separate from pure s-LNv and LNd; DN calls retain author cluster/subcluster labels.",
            "Transcript detection or rhythmicity does not establish protein, current, membrane-potential rhythm, or causal behavior.",
            "Candidate score and target-specific ephys gate are unchanged; review flags request human reconciliation only.",
        ],
        "input_sha256": {relative_path_map[key]: _sha256((root / relative_path_map[key])) for key in sorted(relative_path_map)},
        "output_sha256": {context_path.relative_to(root).as_posix(): _sha256(context_path)},
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = _manifest_payload(paths, context_path, report_path, manifest_path, root, raw_argv, parent)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--candidate-table", type=Path, required=True)
    parser.add_argument("--search-log", type=Path, required=True)
    parser.add_argument("--feature-status", type=Path, required=True)
    parser.add_argument("--group-detection", type=Path, required=True)
    parser.add_argument("--rhythm-details", type=Path, required=True)
    parser.add_argument("--rhythm-manifest", type=Path, required=True)
    parser.add_argument("--rhythm-validation", type=Path, required=True)
    parser.add_argument("--rhythm-replay", type=Path, required=True)
    parser.add_argument("--target-score", action="append", required=True, metavar="TARGET=CSV")
    parser.add_argument("--context-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    parsed_scores = []
    for value in args.target_score:
        if "=" not in value:
            parser.error("--target-score must use TARGET=CSV")
        target, file_path = value.split("=", 1)
        parsed_scores.append((target, Path(file_path)))
    args.target_score = parsed_scores
    try:
        report = run(args, argv[1:])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
