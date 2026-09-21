#!/usr/bin/env python3
"""Join verified transcript-context sidecars without changing candidate scores.

The output is one row per existing candidate/target context row, enriched with
author-reported Abruzzi et al. (2017) S3 transcript-cycling calls. Broad source
groups are never presented as subtype-resolved evidence, and no transcript
field is used to recompute candidate scores or electrophysiology gates.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_public_dataset_manifest import validate_file


CONTEXT_REQUIRED = (
    "candidate", "target_group", "literature_score", "literature_coverage",
    "ephys_directness_score", "ephys_directness_gate", "shortlist_gate",
    "scoring_readout_match",
)
CYCLE_REQUIRED = (
    "candidate_symbol", "cell_group", "source_row", "source_list_status",
    "published_cycle_class", "author_F24_flag", "author_JTK_flag",
    "cell_group_scope_note",
)
SOURCE_GROUPS = (
    "LNv_PDF_positive_small_and_large_mixed",
    "LNd_plus_fifth_PDF_negative_s_LNv",
    "DN1_subset",
)
TARGET_CROSSWALK: dict[str, dict[str, str]] = {
    "s-LNv": {
        "source_group": SOURCE_GROUPS[0],
        "target_scope_relation": "pooled_LNv_does_not_resolve_s_LNv",
    },
    "l-LNv": {
        "source_group": SOURCE_GROUPS[0],
        "target_scope_relation": "pooled_LNv_does_not_resolve_l_LNv",
    },
    "LNd": {
        "source_group": SOURCE_GROUPS[1],
        "target_scope_relation": "LNd_group_also_includes_fifth_PDF_negative_s_LNv",
    },
    "DN": {
        "source_group": SOURCE_GROUPS[2],
        "target_scope_relation": "DN1_subset_not_all_dorsal_neurons",
    },
}
SOURCE_SCOPE_NOTES = {
    SOURCE_GROUPS[0]: "The paper profiles PDF-positive small and large LNvs together; this group cannot resolve s-LNv from l-LNv.",
    SOURCE_GROUPS[1]: "The paper's LNd group includes the fifth PDF-negative s-LNv; this is not LNd-only evidence.",
    SOURCE_GROUPS[2]: "The paper profiles a DN1 subset, not all dorsal clock neurons.",
}
ADDED_FIELDS = (
    "published_cycle_audit_candidate_status",
    "published_cycle_source_group",
    "published_cycle_record_status",
    "published_cycle_author_class",
    "published_cycle_audit_entry_count",
    "published_cycle_source_row_count",
    "published_cycle_source_rows_json",
    "published_cycle_author_calls_json",
    "published_cycle_target_scope_relation",
    "published_cycle_source_scope_note",
    "published_cycle_inference_limit",
)
PRESERVED_SCORE_FIELDS = (
    "literature_score", "literature_coverage", "ephys_directness_score",
    "ephys_directness_gate", "shortlist_gate", "scoring_readout_match",
)
NOT_LISTED = "not_listed_in_published_cycler_supplement"
LISTED = "listed_as_published_cycler"
INFERENCE_LIMIT = (
    "Author-reported transcript-cycling membership does not establish channel protein abundance, "
    "membrane current, membrane-potential rhythm, behavioral causality, or a channel mechanism."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path, required: tuple[str, ...]) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        missing = sorted(set(required) - set(fields))
        if missing:
            raise ValueError(f"{path}: missing required columns: {', '.join(missing)}")
        return fields, list(reader)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _relative(path: Path, root: Path) -> tuple[str, Path]:
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        rel = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path must resolve inside repository root: {path}") from exc
    if not resolved.is_file():
        raise ValueError(f"input file does not exist: {rel}")
    return rel, resolved


def _output_path(path: Path, root: Path) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"provenance output paths must be safe repository-relative paths: {path}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"output path escapes repository root: {path}") from exc
    return resolved


def _verify_parent_bundle(
    name: str,
    manifest_path: Path,
    validation_path: Path,
    replay_path: Path,
    required_outputs: tuple[str, ...],
    root: Path,
) -> dict[str, Any]:
    manifest_rel, manifest_file = _relative(manifest_path, root)
    validation_rel, validation_file = _relative(validation_path, root)
    replay_rel, replay_file = _relative(replay_path, root)
    manifest = _read_json(manifest_file)
    stored_validation = _read_json(validation_file)
    replay = _read_json(replay_file)
    current_validation = validate_file(manifest_file, root)
    manifest_id = manifest.get("manifest_id")
    if current_validation.get("status") != "verified_public_dataset_manifest":
        raise ValueError(f"{name} parent manifest is not currently valid: {current_validation.get('issues')}")
    if stored_validation.get("status") != "verified_public_dataset_manifest" or stored_validation.get("manifest_id") != manifest_id:
        raise ValueError(f"{name} stored validation is not bound to its parent manifest")
    if replay.get("status") != "verified_public_dataset_replay":
        raise ValueError(f"{name} isolated replay is not verified: {replay.get('status')}")
    replay_validation = replay.get("manifest_validation") or {}
    if replay_validation.get("status") != "verified_public_dataset_manifest" or replay_validation.get("manifest_id") != manifest_id:
        raise ValueError(f"{name} replay is not bound to its verified parent manifest")

    records = {str(item.get("path")): item for item in manifest.get("files", []) if isinstance(item, dict)}
    current_checks = {str(item.get("path")): item for item in current_validation.get("file_checks", []) if isinstance(item, dict)}
    stored_checks = {str(item.get("path")): item for item in stored_validation.get("file_checks", []) if isinstance(item, dict)}
    replay_checks = {str(item.get("path")): item for item in replay.get("output_checks", []) if isinstance(item, dict)}
    verified_hashes: dict[str, str] = {}
    for relative in required_outputs:
        record = records.get(relative)
        current_check = current_checks.get(relative)
        stored_check = stored_checks.get(relative)
        replay_check = replay_checks.get(relative)
        if not record or str(record.get("role", "")).lower() != "derived":
            raise ValueError(f"{name} required output is not declared as a derived parent artifact: {relative}")
        actual_path = (root / relative).resolve()
        try:
            actual_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"{name} parent output escapes the repository root: {relative}") from exc
        if not actual_path.is_file():
            raise ValueError(f"{name} parent output is missing: {relative}")
        observed = _sha256(actual_path)
        declared = str(record.get("sha256") or "").lower()
        if observed != declared:
            raise ValueError(f"{name} parent output hash differs from its manifest: {relative}")
        if not current_check or current_check.get("status") != "hash_verified" or current_check.get("observed_sha256") != observed:
            raise ValueError(f"{name} parent output failed current manifest validation: {relative}")
        if not stored_check or stored_check.get("status") != "hash_verified" or stored_check.get("observed_sha256") != observed:
            raise ValueError(f"{name} stored validation does not attest to the current output hash: {relative}")
        if not replay_check or replay_check.get("status") != "replay_hash_verified" or replay_check.get("observed_sha256") != observed:
            raise ValueError(f"{name} parent output is not confirmed by isolated replay: {relative}")
        verified_hashes[relative] = observed

    return {
        "name": name,
        "manifest_id": manifest_id,
        "dataset_id": manifest.get("dataset_id"),
        "accession": manifest.get("accession"),
        "source_url": manifest.get("source_url"),
        "manifest_path": manifest_rel,
        "validation_path": validation_rel,
        "replay_path": replay_rel,
        "status": "verified_parent_manifest_and_replay",
        "verified_output_sha256": verified_hashes,
        "files": manifest.get("files", []),
    }


def _flag(value: str, label: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"invalid author flag {label}: {value!r}")


def _validate_cycle_audit(
    rows: list[dict[str, str]], audit: dict[str, Any]
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], set[str], dict[str, Any]]:
    matching = audit.get("matching") or {}
    summaries = audit.get("candidate_summary")
    if not isinstance(summaries, list) or not summaries:
        raise ValueError("published-cycle audit report has no candidate_summary")
    summary_by_candidate: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        if not isinstance(summary, dict):
            raise ValueError("candidate_summary entries must be objects")
        gene = str(summary.get("candidate_symbol") or "").strip()
        if not gene or gene in summary_by_candidate:
            raise ValueError(f"published-cycle report has missing or duplicate candidate symbol: {gene!r}")
        by_group = summary.get("by_group")
        if not isinstance(by_group, dict) or set(by_group) != set(SOURCE_GROUPS):
            raise ValueError(f"published-cycle report does not contain exactly the expected groups for {gene}")
        summary_by_candidate[gene] = summary
    expected_rows = len(summary_by_candidate) * len(SOURCE_GROUPS)
    if matching.get("candidate_count") != len(summary_by_candidate):
        raise ValueError("published-cycle report candidate_count disagrees with candidate_summary")
    if matching.get("target_group_count") != len(SOURCE_GROUPS) or matching.get("candidate_group_rows") != expected_rows:
        raise ValueError("published-cycle report group counts do not match the candidate_summary shape")

    records_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    seen_source_rows: set[tuple[str, str, int]] = set()
    scope_notes: dict[str, str] = {}
    for raw in rows:
        gene = raw["candidate_symbol"].strip()
        group = raw["cell_group"].strip()
        if gene not in summary_by_candidate or group not in SOURCE_GROUPS:
            raise ValueError(f"published-cycle evidence has unexpected candidate or group: {gene}/{group}")
        status = raw["source_list_status"].strip()
        call_class = raw["published_cycle_class"].strip()
        note = raw["cell_group_scope_note"].strip()
        if not note or (group in scope_notes and scope_notes[group] != note):
            raise ValueError(f"missing or inconsistent source scope note for {group}")
        scope_notes[group] = note
        record: dict[str, Any] = {
            "source_list_status": status,
            "published_cycle_class": call_class,
            "cell_group_scope_note": note,
        }
        if status == LISTED:
            if call_class not in {"HC", "LC"}:
                raise ValueError(f"listed source row has invalid author class for {gene}/{group}: {call_class}")
            try:
                source_row = int(raw["source_row"].strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"listed source row lacks a valid source row number for {gene}/{group}") from exc
            if source_row <= 0 or (gene, group, source_row) in seen_source_rows:
                raise ValueError(f"invalid or repeated source row for {gene}/{group}: {source_row}")
            seen_source_rows.add((gene, group, source_row))
            f24 = _flag(raw["author_F24_flag"], "author_F24_flag")
            jtk = _flag(raw["author_JTK_flag"], "author_JTK_flag")
            if (call_class == "HC" and not (f24 and jtk)) or (call_class == "LC" and f24 == jtk):
                raise ValueError(f"author flags disagree with HC/LC class for {gene}/{group}/{source_row}")
            record.update({"source_row": source_row, "author_F24_flag": f24, "author_JTK_flag": jtk})
        elif status == NOT_LISTED:
            if call_class != "not_listed" or raw["source_row"].strip() or raw["author_F24_flag"].strip() or raw["author_JTK_flag"].strip():
                raise ValueError(f"not-listed source row contains inconsistent call fields for {gene}/{group}")
        else:
            raise ValueError(f"unknown published-cycle source_list_status: {status!r}")
        records_by_key[(gene, group)].append(record)

    for gene, summary in summary_by_candidate.items():
        for group in SOURCE_GROUPS:
            expected_calls = summary["by_group"][group]
            if not isinstance(expected_calls, list):
                raise ValueError(f"published-cycle report calls must be lists for {gene}/{group}")
            source_records = records_by_key.get((gene, group), [])
            listed_records = [record for record in source_records if record["source_list_status"] == LISTED]
            not_listed_records = [record for record in source_records if record["source_list_status"] == NOT_LISTED]
            expected_pairs: list[tuple[str, int]] = []
            for call in expected_calls:
                if not isinstance(call, dict) or call.get("cycle_class") not in {"HC", "LC"}:
                    raise ValueError(f"invalid summary call for {gene}/{group}")
                try:
                    expected_pairs.append((str(call["cycle_class"]), int(call["source_row"])))
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"invalid summary source row for {gene}/{group}") from exc
            observed_pairs = sorted((record["published_cycle_class"], int(record["source_row"])) for record in listed_records)
            if expected_pairs:
                if not listed_records or not_listed_records or sorted(expected_pairs) != observed_pairs:
                    raise ValueError(f"published-cycle evidence rows disagree with the audit report for {gene}/{group}")
            elif listed_records or len(not_listed_records) != 1:
                raise ValueError(f"missing or inconsistent not-listed evidence row for {gene}/{group}")

    if set(records_by_key) != {
        (gene, group) for gene in summary_by_candidate for group in SOURCE_GROUPS
    }:
        raise ValueError("published-cycle evidence candidate/group coverage disagrees with the audit report")
    return dict(records_by_key), set(summary_by_candidate), {
        "n_candidates": len(summary_by_candidate),
        "n_candidate_group_rows": expected_rows,
        "source_scope_notes": scope_notes,
        "candidate_symbols": sorted(summary_by_candidate),
    }


def build_context_rows(
    base_rows: list[dict[str, str]],
    base_fields: list[str],
    cycle_records: dict[tuple[str, str], list[dict[str, Any]]],
    cycle_candidates: set[str],
    scope_notes: dict[str, str],
) -> list[dict[str, Any]]:
    collisions = sorted(set(base_fields) & set(ADDED_FIELDS))
    if collisions:
        raise ValueError(f"base context already contains published-cycle fields: {collisions}")
    seen_keys: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for source in base_rows:
        gene = source["candidate"].strip()
        target = source["target_group"].strip()
        key = (gene, target)
        if not gene or not target or key in seen_keys:
            raise ValueError(f"base context has missing or duplicate candidate/target key: {key}")
        seen_keys.add(key)
        crosswalk = TARGET_CROSSWALK.get(target)
        if not crosswalk:
            source_group = ""
            audit_status = "not_evaluable_target_group_not_mapped"
            record_status = "source_group_not_mapped"
            author_class = "not_evaluable"
            matching_records: list[dict[str, Any]] = []
            scope_note = "No published-cycle source-group crosswalk is defined for this target group."
            scope_relation = "target_group_not_mapped"
        else:
            source_group = crosswalk["source_group"]
            scope_relation = crosswalk["target_scope_relation"]
            scope_note = scope_notes.get(source_group, SOURCE_SCOPE_NOTES[source_group])
            if gene not in cycle_candidates:
                audit_status = "candidate_not_in_published_cycle_audit_candidate_set"
                record_status = "candidate_not_in_published_cycle_audit_not_evaluable"
                author_class = "not_evaluable"
                matching_records = []
            else:
                audit_status = "candidate_in_published_cycle_audit_candidate_set"
                matching_records = cycle_records.get((gene, source_group), [])
                if not matching_records:
                    record_status = "source_group_record_missing_not_evaluable"
                    author_class = "not_evaluable"
                else:
                    classes = {record["published_cycle_class"] for record in matching_records}
                    listed_flags = {record["source_list_status"] for record in matching_records}
                    if listed_flags == {NOT_LISTED}:
                        record_status = NOT_LISTED
                        author_class = "not_listed"
                    elif listed_flags == {LISTED} and len(classes) == 1:
                        record_status = LISTED
                        author_class = next(iter(classes))
                    else:
                        record_status = "conflicting_published_cycle_source_records"
                        author_class = "conflict"
        call_details = [
            {
                "source_row": record.get("source_row"),
                "author_class": record["published_cycle_class"],
                "author_F24_flag": record.get("author_F24_flag"),
                "author_JTK_flag": record.get("author_JTK_flag"),
            }
            for record in matching_records
            if record["source_list_status"] == LISTED
        ]
        source_rows = sorted(record["source_row"] for record in matching_records if "source_row" in record)
        enriched: dict[str, Any] = dict(source)
        enriched.update({
            "published_cycle_audit_candidate_status": audit_status,
            "published_cycle_source_group": source_group or "NA",
            "published_cycle_record_status": record_status,
            "published_cycle_author_class": author_class,
            "published_cycle_audit_entry_count": len(matching_records),
            "published_cycle_source_row_count": len(source_rows),
            "published_cycle_source_rows_json": _json_text(source_rows),
            "published_cycle_author_calls_json": _json_text(call_details),
            "published_cycle_target_scope_relation": scope_relation,
            "published_cycle_source_scope_note": scope_note,
            "published_cycle_inference_limit": INFERENCE_LIMIT,
        })
        output.append(enriched)
    return output


def _verify_base_context_report(
    context_path: Path, context_rel: str, report_path: Path
) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    fields, rows = _read_csv(context_path, CONTEXT_REQUIRED)
    report = _read_json(report_path)
    if report.get("status") != "verified_candidate_evidence_context_overlay":
        raise ValueError(f"base GSE candidate context is not verified: {report.get('status')}")
    if report.get("n_rows") != len(rows) or report.get("n_candidates") != len({row["candidate"].strip() for row in rows}):
        raise ValueError("base GSE context report row/candidate counts disagree with the context CSV")
    if report.get("target_score_parity") != "verified for score, coverage, directness score/gate, shortlist gate and readout":
        raise ValueError("base GSE context report does not record target-score parity")
    targets = report.get("target_groups")
    if not isinstance(targets, list) or set(targets) != set(TARGET_CROSSWALK):
        raise ValueError("base GSE context report target groups do not match the supported crosswalk")
    if len(targets) != len(set(targets)):
        raise ValueError("base GSE context report contains duplicate target groups")
    candidate_set = {row["candidate"].strip() for row in rows}
    observed_pairs = {(row["candidate"].strip(), row["target_group"].strip()) for row in rows}
    expected_pairs = {(candidate, target) for candidate in candidate_set for target in targets}
    if observed_pairs != expected_pairs:
        raise ValueError("base GSE context is not a complete candidate x target-group grid")
    output_hashes = report.get("output_sha256") or {}
    if output_hashes.get(context_rel) != _sha256(context_path):
        raise ValueError("base GSE context CSV hash disagrees with its report")
    return report, rows, fields


def _validate_outputs(output_paths: tuple[Path, ...], inputs: list[Path], root: Path) -> None:
    resolved_root = root.resolve()
    protected = {path.resolve() for path in inputs}
    protected.update({
        Path(__file__).resolve(),
        (resolved_root / "scripts/validate_public_dataset_manifest.py").resolve(),
    })
    normalized = [path.resolve() for path in output_paths]
    if len(set(normalized)) != len(normalized):
        raise ValueError("output CSV, report and manifest paths must be distinct")
    for path in normalized:
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"output must stay inside repository root: {path}") from exc
        if path in protected:
            raise ValueError(f"output would overwrite an input or executable helper: {path}")


def _merge_file_records(parent_bundles: list[dict[str, Any]], metadata_paths: list[tuple[str, Path]], root: Path) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for bundle in parent_bundles:
        for raw in bundle.get("files", []):
            relative = str(raw.get("path") or "").replace("\\", "/")
            if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise ValueError(f"unsafe path in parent manifest: {relative!r}")
            record = {key: value for key, value in raw.items() if key in {"path", "role", "sha256", "source_url"} and value is not None}
            observed = _sha256(root / relative)
            if str(record.get("sha256", "")).lower() != observed:
                raise ValueError(f"parent manifest file hash no longer matches: {relative}")
            previous = merged.get(relative)
            if previous and (previous.get("sha256") != record.get("sha256") or previous.get("role") != record.get("role")):
                raise ValueError(f"parent manifests disagree about the role or hash of {relative}")
            merged[relative] = {**(previous or {}), **record}
    for relative, path in metadata_paths:
        observed = _sha256(path)
        record = {"path": relative, "role": "metadata", "sha256": observed}
        previous = merged.get(relative)
        if previous and previous.get("sha256") != observed:
            raise ValueError(f"parent manifest metadata path has conflicting hash: {relative}")
        if previous:
            # A parent manifest can also list one of these records as a config;
            # retain its original role while still recording its observed hash.
            previous["sha256"] = observed
            continue
        merged[relative] = record
    return [merged[key] for key in sorted(merged)]


def _build_manifest(
    *,
    root: Path,
    argv: list[str],
    paths: dict[str, Path],
    parent_bundles: list[dict[str, Any]],
    csv_path: Path,
    report_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    script_rel = Path(__file__).resolve().relative_to(root.resolve()).as_posix()
    dependency_rel = "scripts/validate_public_dataset_manifest.py"
    replay_helper_rel = "scripts/replay_public_dataset_manifest.py"
    file_records = _merge_file_records(
        parent_bundles,
        [(relative, path) for relative, path in paths.items() if relative.endswith(("-manifest.json", "-validation.json", "-replay.json"))],
        root,
    )
    file_map = {record["path"]: record for record in file_records}
    for relative in (script_rel, dependency_rel, replay_helper_rel):
        current_hash = _sha256(root / relative)
        if relative in file_map and file_map[relative]["sha256"] != current_hash:
            raise ValueError(f"script dependency hash differs from a parent manifest record: {relative}")
        file_map[relative] = {"path": relative, "role": "config", "sha256": current_hash}

    csv_rel = csv_path.resolve().relative_to(root.resolve()).as_posix()
    report_rel = report_path.resolve().relative_to(root.resolve()).as_posix()
    manifest_rel = manifest_path.resolve().relative_to(root.resolve()).as_posix()
    file_map[csv_rel] = {"path": csv_rel, "role": "derived", "sha256": _sha256(csv_path)}
    file_map[report_rel] = {"path": report_rel, "role": "derived", "sha256": _sha256(report_path)}
    command_argv = ["python", script_rel, *argv]
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    source_checked = now
    source_tokens = [
        "GSE157504", "GSE77451", "10.1371/journal.pgen.1006613",
        "LNv", "LNd", "DN1", "RNA-seq",
    ]
    return {
        "manifest_id": "GSE157504-Abruzzi2017-S3-candidate-context-20260921",
        "dataset_id": "GSE157504-plus-Abruzzi2017-S3-candidate-context",
        "accession": "GSE157504; GSE77451; PLOS DOI 10.1371/journal.pgen.1006613.s003",
        "species": "Drosophila melanogaster",
        "source_url": "https://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.1006613",
        "retrieved_at_utc": now,
        "source_access_status": "content_checked",
        "source_checked_at_utc": source_checked,
        "source_check_method": "web_open",
        "source_observed_tokens": source_tokens,
        "source_observation_note": "The official PLOS article page was checked online; GEO and S3 input content and output hashes are inherited and rechecked through both verified parent manifests and isolated replays.",
        "analysis_context": {
            "time_system": "GSE157504 context retains source LD/ZT and DD/CT labels; Abruzzi et al. S3 reports LD transcript-cycling calls in ZT. No new time-series fit or conversion is performed.",
            "experimental_unit": "Output rows are candidate x target-group evidence records, not biological replicates. GSE cells remain nested in samples; Abruzzi et al. libraries are pooled neuron samples.",
            "normalization_status": "No new normalization, differential-expression analysis, or rhythm fit. Existing GSE raw-UMI context and published S3 author calls are joined as separate source columns.",
            "biological_unit_limitations": "The PLOS LNv group mixes PDF-positive s-LNv and l-LNv; its LNd group includes the fifth PDF-negative s-LNv; DN1 is a subset. Transcript-level calls do not establish protein, current, membrane potential, or behavior. The LNv manuscript-versus-S3 HC count discrepancy is retained.",
            "sources": [
                {"manifest_id": parent_bundles[0]["manifest_id"], "source_url": parent_bundles[0].get("source_url"), "accession": parent_bundles[0].get("accession")},
                {"manifest_id": parent_bundles[1]["manifest_id"], "source_url": parent_bundles[1].get("source_url"), "accession": parent_bundles[1].get("accession")},
            ],
            "score_policy": "Existing GSE literature/electrophysiology score and gate columns are copied verbatim. Published transcript-cycling calls do not change ranks, score dimensions, shortlist decisions, or electrophysiology directness.",
        },
        "files": [file_map[key] for key in sorted(file_map)],
        "runs": [{
            "run_id": "join-verified-gse-and-abruzzi2017-cycle-context",
            "script": script_rel,
            "script_sha256": _sha256(root / script_rel),
            "command": "python " + " ".join(command_argv[1:]),
            "command_argv": command_argv,
            "status": "executed",
            "inputs": sorted(relative for relative in file_map if relative not in {csv_rel, report_rel}),
            "outputs": [csv_rel, report_rel],
        }],
    }


def run(args: argparse.Namespace, argv: list[str]) -> dict[str, Any]:
    root = args.root.resolve()
    path_args = {
        "gse_context": args.gse_context,
        "gse_report": args.gse_report,
        "gse_manifest": args.gse_manifest,
        "gse_validation": args.gse_validation,
        "gse_replay": args.gse_replay,
        "cycle_evidence": args.cycle_evidence,
        "cycle_report": args.cycle_report,
        "cycle_manifest": args.cycle_manifest,
        "cycle_validation": args.cycle_validation,
        "cycle_replay": args.cycle_replay,
    }
    for key, path in path_args.items():
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"provenance input paths must be safe repository-relative paths: {key}={path}")
    normalized: dict[str, tuple[str, Path]] = {key: _relative(path, root) for key, path in path_args.items()}
    relatives = {key: item[0] for key, item in normalized.items()}
    files = {key: item[1] for key, item in normalized.items()}

    gse_parent = _verify_parent_bundle(
        "GSE157504 candidate context",
        files["gse_manifest"], files["gse_validation"], files["gse_replay"],
        (relatives["gse_context"], relatives["gse_report"]), root,
    )
    cycle_parent = _verify_parent_bundle(
        "Abruzzi2017 S3 candidate-cycle audit",
        files["cycle_manifest"], files["cycle_validation"], files["cycle_replay"],
        (relatives["cycle_evidence"], relatives["cycle_report"]), root,
    )

    context_report, context_rows, context_fields = _verify_base_context_report(
        files["gse_context"], relatives["gse_context"], files["gse_report"],
    )
    cycle_fields, cycle_rows = _read_csv(files["cycle_evidence"], CYCLE_REQUIRED)
    cycle_report = _read_json(files["cycle_report"])
    if cycle_report.get("status") not in {"executed_with_source_count_discrepancy", "verified_published_cycle_candidate_audit"}:
        raise ValueError(f"published-cycle audit report has an unexpected status: {cycle_report.get('status')}")
    cycle_hashes = cycle_parent["verified_output_sha256"]
    if cycle_hashes[relatives["cycle_report"]] != _sha256(files["cycle_report"]):
        raise ValueError("published-cycle audit report hash mismatch")
    cycle_records, cycle_candidates, cycle_shape = _validate_cycle_audit(cycle_rows, cycle_report)

    base_candidates = {row["candidate"].strip() for row in context_rows}
    candidate_set_difference = {
        "gse_context_candidates_not_in_published_cycle_audit": sorted(base_candidates - cycle_candidates),
        "published_cycle_audit_candidates_not_in_gse_context": sorted(cycle_candidates - base_candidates),
    }
    output_rows = build_context_rows(
        context_rows,
        context_fields,
        cycle_records,
        cycle_candidates,
        cycle_shape["source_scope_notes"],
    )
    output_fields = [*context_fields, *ADDED_FIELDS]
    output_path = _output_path(args.output_csv, root)
    report_path = _output_path(args.output_report, root)
    manifest_path = _output_path(args.manifest_output, root)
    parent_file_paths = [root / str(record["path"]) for parent in (gse_parent, cycle_parent) for record in parent["files"]]
    input_paths = [*files.values(), *parent_file_paths]
    _validate_outputs((output_path, report_path, manifest_path), input_paths, root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    status_counts = Counter(row["published_cycle_record_status"] for row in output_rows)
    class_counts = Counter(row["published_cycle_author_class"] for row in output_rows)
    listed_rows = [row for row in output_rows if row["published_cycle_record_status"] == LISTED]
    listed_source_pairs = {
        key for key, records in cycle_records.items()
        if any(record["source_list_status"] == LISTED for record in records)
    }
    source_pair_classes = {
        key: {record["published_cycle_class"] for record in cycle_records[key] if record["source_list_status"] == LISTED}
        for key in listed_source_pairs
    }
    score_invariants = {
        "preserved_context_columns": context_fields,
        "score_and_gate_columns": list(PRESERVED_SCORE_FIELDS),
        "all_input_context_values_copied_verbatim": all(
            all(row[field] == source[field] for field in context_fields)
            for row, source in zip(output_rows, context_rows, strict=True)
        ),
        "scores_recomputed": False,
        "ephys_gate_recomputed": False,
    }
    if not score_invariants["all_input_context_values_copied_verbatim"]:
        raise ValueError("output did not preserve every base context field verbatim")

    report: dict[str, Any] = {
        "status": "executed_published_cycle_candidate_context_overlay",
        "n_input_context_rows": len(context_rows),
        "n_output_rows": len(output_rows),
        "row_unit": "candidate x target-group context row; not a biological replicate",
        "candidate_set_difference": candidate_set_difference,
        "base_gse_candidate_set_difference": context_report.get("candidate_set_difference", {}),
        "published_cycle_candidate_audit_shape": cycle_shape,
        "target_source_group_crosswalk": {
            target: {
                **mapping,
                "scope_note": cycle_shape["source_scope_notes"].get(
                    mapping["source_group"], SOURCE_SCOPE_NOTES[mapping["source_group"]],
                ),
            }
            for target, mapping in TARGET_CROSSWALK.items()
        },
        "record_status_counts": dict(sorted(status_counts.items())),
        "author_class_counts": dict(sorted(class_counts.items())),
        "n_listed_HC_target_rows": class_counts.get("HC", 0),
        "n_listed_LC_target_rows": class_counts.get("LC", 0),
        "n_not_listed_target_rows": class_counts.get("not_listed", 0),
        "n_not_evaluable_or_conflicting_target_rows": class_counts.get("not_evaluable", 0) + class_counts.get("conflict", 0),
        "distinct_published_source_calls": {
            "candidate_group_pairs": len(listed_source_pairs),
            "source_records": sum(
                1 for records in cycle_records.values()
                for record in records if record["source_list_status"] == LISTED
            ),
            "candidate_symbols": sorted({gene for gene, _ in listed_source_pairs}),
            "HC_candidate_group_pairs": sum(classes == {"HC"} for classes in source_pair_classes.values()),
            "LC_candidate_group_pairs": sum(classes == {"LC"} for classes in source_pair_classes.values()),
            "conflicting_candidate_group_pairs": sum(len(classes) != 1 for classes in source_pair_classes.values()),
            "note": "A pooled LNv source call is shown on both s-LNv and l-LNv context rows; target-row counts are not independent source calls.",
        },
        "listed_candidate_target_calls": [
            {
                "candidate": row["candidate"],
                "target_group": row["target_group"],
                "author_class": row["published_cycle_author_class"],
                "source_group": row["published_cycle_source_group"],
                "source_rows": json.loads(row["published_cycle_source_rows_json"]),
            }
            for row in listed_rows
        ],
        "score_and_gate_invariants": score_invariants,
        "parent_gse_context": {
            "manifest_id": gse_parent["manifest_id"],
            "status": gse_parent["status"],
            "verified_outputs": gse_parent["verified_output_sha256"],
        },
        "parent_published_cycle_audit": {
            "manifest_id": cycle_parent["manifest_id"],
            "status": cycle_parent["status"],
            "verified_outputs": cycle_parent["verified_output_sha256"],
            "source_discrepancies": cycle_report.get("manuscript_vs_supplement_count_discrepancies", []),
        },
        "interpretation_limits": [
            "PLOS S3 calls are author-reported transcript-cycling classifications; this workflow does not refit rhythm statistics.",
            "No exact-symbol row in a selected sheet means not listed under the author criteria, not unexpressed or arrhythmic.",
            "LNv calls are mapped to both s-LNv and l-LNv context rows only as pooled-group context; they do not resolve subtype.",
            "The paper's LNd group includes the fifth PDF-negative s-LNv, and its DN1 sample is a subset rather than all DN.",
            "Transcript-level evidence does not establish channel protein, current, membrane-potential rhythm, or causal behavior.",
            "The GSE scores, shortlist decisions, and electrophysiology gates are copied without recalculation or update.",
            "The LNv manuscript-versus-S3 HC count discrepancy is carried forward unresolved.",
        ],
        "input_sha256": {relative: _sha256(root / relative) for relative in sorted(relatives.values())},
        "output_sha256": {output_path.relative_to(root).as_posix(): _sha256(output_path)},
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_paths = {
        relative: path for relative, path in normalized.values()
    }
    manifest = _build_manifest(
        root=root,
        argv=argv,
        paths=manifest_paths,
        parent_bundles=[gse_parent, cycle_parent],
        csv_path=output_path,
        report_path=report_path,
        manifest_path=manifest_path,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    for option in (
        "gse-context", "gse-report", "gse-manifest", "gse-validation", "gse-replay",
        "cycle-evidence", "cycle-report", "cycle-manifest", "cycle-validation", "cycle-replay",
    ):
        parser.add_argument(f"--{option}", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        report = run(args, argv[1:])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
