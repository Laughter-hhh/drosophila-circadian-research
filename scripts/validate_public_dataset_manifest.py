#!/usr/bin/env python3
"""Validate public-dataset provenance, hashes, commands and analysis context.

The gate checks file integrity and traceability only.  It does not validate that
the public dataset is biologically representative, that normalization is suitable,
or that an exploratory result is a causal or publication-grade conclusion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


REQUIRED = {
    "manifest_id", "dataset_id", "accession", "species", "source_url",
    "retrieved_at_utc", "source_access_status", "files", "runs", "analysis_context",
}
FILE_ROLES = {"raw", "annotation", "metadata", "candidate_list", "config", "derived", "other"}
RUN_STATUSES = {"executed", "verified"}
SOURCE_ACCESS = {"content_checked", "identifier_checked", "not_checked", "blocked"}
SOURCE_CHECK_METHODS = {"web_open", "browser_manual", "automated_http"}
MANIFEST_STAGES = {"planning", "executed", "verified"}
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _norm_rel(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _is_safe_relative(value: str) -> bool:
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return False
    return ".." not in value.split("/")


def _resolve(root: Path, relative: str) -> Path:
    return (root / Path(relative)).resolve()


def _under_root(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def _validate_planned_runs(
    planned_runs: Any,
    root: Path,
    files_by_path: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    if not isinstance(planned_runs, list) or not planned_runs:
        return [], [{"type": "planned_runs_must_be_nonempty_list"}]

    produced_paths: set[str] = set()
    seen_ids: set[str] = set()
    for index, planned in enumerate(planned_runs, start=1):
        run_issues_before = len(issues)
        if not isinstance(planned, dict):
            issues.append({"index": index, "type": "planned_run_record_must_be_object"})
            continue
        run_id = str(planned.get("run_id") or "").strip()
        script = _norm_rel(planned.get("script"))
        script_hash = str(planned.get("script_sha256") or "").strip().lower()
        command = str(planned.get("command") or "").strip()
        argv = planned.get("command_argv")
        inputs = planned.get("inputs")
        outputs = planned.get("outputs")
        if not run_id or not script or not command:
            issues.append({"index": index, "run_id": run_id, "type": "planned_run_requires_id_script_command"})
        if "status" in planned:
            issues.append({"index": index, "run_id": run_id, "type": "planned_run_must_not_claim_execution_status"})
        if run_id:
            if run_id in seen_ids:
                issues.append({"index": index, "run_id": run_id, "type": "duplicate_planned_run_id"})
            seen_ids.add(run_id)

        if not isinstance(argv, list) or len(argv) < 2 or not all(isinstance(item, str) and item for item in argv):
            issues.append({"index": index, "run_id": run_id, "type": "planned_command_argv_must_be_nonempty_string_list"})
        else:
            normalized_argv = [_norm_rel(item) for item in argv]
            if argv[0] not in {"python", "python3"}:
                issues.append({"index": index, "run_id": run_id, "type": "planned_command_argv_requires_python_launcher"})
            if normalized_argv[1] != script:
                issues.append({"index": index, "run_id": run_id, "type": "planned_command_argv_script_mismatch", "script": normalized_argv[1]})
            for argument in argv[1:]:
                if "\x00" in argument or not _is_safe_relative(_norm_rel(argument)):
                    issues.append({"index": index, "run_id": run_id, "type": "planned_command_argv_contains_unsafe_path", "argument": argument})
                    break

        if not _is_safe_relative(script):
            issues.append({"index": index, "run_id": run_id, "type": "planned_script_path_must_be_safe_relative"})
        else:
            script_path = _resolve(root, script)
            if not _under_root(root, script_path) or not script_path.is_file():
                issues.append({"index": index, "run_id": run_id, "type": "planned_script_not_found", "script": script})
            elif not SHA_RE.fullmatch(script_hash):
                issues.append({"index": index, "run_id": run_id, "type": "invalid_planned_script_sha256"})
            elif _sha256(script_path) != script_hash:
                issues.append({"index": index, "run_id": run_id, "type": "planned_script_sha256_mismatch", "script": script})

        if not isinstance(inputs, list) or not inputs:
            issues.append({"index": index, "run_id": run_id, "type": "planned_run_inputs_must_be_nonempty_list"})
            inputs = []
        if not isinstance(outputs, list) or not outputs:
            issues.append({"index": index, "run_id": run_id, "type": "planned_run_outputs_must_be_nonempty_list"})
            outputs = []

        normalized_inputs: list[str] = []
        for raw_path in inputs:
            relative = _norm_rel(raw_path)
            normalized_inputs.append(relative)
            if not _is_safe_relative(relative):
                issues.append({"index": index, "run_id": run_id, "type": "planned_input_path_must_be_safe_relative", "path": relative})
            elif relative not in files_by_path and relative not in produced_paths:
                issues.append({"index": index, "run_id": run_id, "type": "planned_input_not_available_before_run", "path": relative})

        normalized_outputs: list[str] = []
        for raw_path in outputs:
            relative = _norm_rel(raw_path)
            normalized_outputs.append(relative)
            if not _is_safe_relative(relative):
                issues.append({"index": index, "run_id": run_id, "type": "planned_output_path_must_be_safe_relative", "path": relative})
                continue
            if relative in files_by_path:
                issues.append({"index": index, "run_id": run_id, "type": "planned_output_must_not_be_declared_as_existing_file", "path": relative})
            if relative in produced_paths:
                issues.append({"index": index, "run_id": run_id, "type": "planned_output_path_is_not_unique", "path": relative})
            resolved = _resolve(root, relative)
            if not _under_root(root, resolved):
                issues.append({"index": index, "run_id": run_id, "type": "planned_output_resolves_outside_root", "path": relative})
            elif resolved.exists():
                issues.append({"index": index, "run_id": run_id, "type": "planned_output_path_already_exists", "path": relative})
        produced_paths.update(path for path in normalized_outputs if _is_safe_relative(path))
        checks.append({
            "run_id": run_id,
            "script": script,
            "status": "planning" if len(issues) == run_issues_before else "blocked",
            "inputs": normalized_inputs,
            "planned_outputs": normalized_outputs,
        })
    return checks, issues


def validate_payload(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return {"status": "invalid_public_dataset_manifest", "issues": [{"type": "top_level_must_be_object"}], "warnings": []}
    missing = sorted(REQUIRED - set(payload))
    if missing:
        return {"status": "invalid_public_dataset_manifest", "issues": [{"type": "missing_fields", "fields": missing}], "warnings": []}

    requested_stage = str(payload.get("manifest_stage") or "executed").strip().lower()
    manifest_stage = requested_stage if requested_stage in MANIFEST_STAGES else "executed"
    if requested_stage not in MANIFEST_STAGES:
        issues.append({"type": "invalid_manifest_stage", "value": requested_stage})

    source_url = str(payload.get("source_url") or "").strip()
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.username or parsed_url.password:
        issues.append({"type": "source_url_must_be_https_without_credentials", "value": source_url})
    try:
        observed_time = datetime.fromisoformat(str(payload.get("retrieved_at_utc")).replace("Z", "+00:00"))
        if observed_time.tzinfo is None:
            issues.append({"type": "retrieved_at_utc_requires_timezone"})
    except (TypeError, ValueError):
        issues.append({"type": "invalid_retrieved_at_utc"})
    access_status = str(payload.get("source_access_status") or "").strip().lower()
    if access_status not in SOURCE_ACCESS:
        issues.append({"type": "invalid_source_access_status", "value": access_status})
    elif access_status != "content_checked":
        warnings.append({"type": "online_source_content_not_fully_checked", "source_access_status": access_status})
    else:
        checked_at = str(payload.get("source_checked_at_utc") or "").strip()
        check_method = str(payload.get("source_check_method") or "").strip().lower()
        observed_tokens = payload.get("source_observed_tokens")
        observation_note = str(payload.get("source_observation_note") or "").strip()
        try:
            checked_time = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
            if checked_time.tzinfo is None:
                issues.append({"type": "source_checked_at_utc_requires_timezone"})
        except (TypeError, ValueError):
            issues.append({"type": "invalid_source_checked_at_utc"})
        if check_method not in SOURCE_CHECK_METHODS:
            issues.append({"type": "invalid_source_check_method", "value": check_method})
        if not isinstance(observed_tokens, list) or not observed_tokens or not all(_nonempty(token) for token in observed_tokens):
            issues.append({"type": "source_observed_tokens_must_be_nonempty_list"})
        if not observation_note:
            issues.append({"type": "source_observation_note_required"})

    context = payload.get("analysis_context")
    if not isinstance(context, dict):
        issues.append({"type": "analysis_context_must_be_object"})
    else:
        for field in ("time_system", "experimental_unit", "normalization_status", "biological_unit_limitations"):
            if not _nonempty(context.get(field)):
                issues.append({"type": f"analysis_context_missing_{field}"})

    file_records = payload.get("files")
    if not isinstance(file_records, list) or not file_records:
        issues.append({"type": "files_must_be_nonempty_list"})
        file_records = []
    files_by_path: dict[str, dict[str, Any]] = {}
    file_checks: list[dict[str, Any]] = []
    for index, record in enumerate(file_records, start=1):
        if not isinstance(record, dict):
            issues.append({"index": index, "type": "file_record_must_be_object"})
            continue
        relative = _norm_rel(record.get("path"))
        role = str(record.get("role") or "").strip().lower()
        expected = str(record.get("sha256") or "").strip().lower()
        if not _is_safe_relative(relative):
            issues.append({"index": index, "path": relative, "type": "file_path_must_be_safe_relative"})
            continue
        if relative in files_by_path:
            issues.append({"index": index, "path": relative, "type": "duplicate_file_path"})
        files_by_path[relative] = record
        if role not in FILE_ROLES:
            issues.append({"index": index, "path": relative, "type": "invalid_file_role", "value": role})
        if not SHA_RE.fullmatch(expected):
            issues.append({"index": index, "path": relative, "type": "invalid_sha256"})
        resolved = _resolve(root, relative)
        check: dict[str, Any] = {"path": relative, "role": role, "expected_sha256": expected}
        if not _under_root(root, resolved):
            issues.append({"index": index, "path": relative, "type": "file_resolves_outside_root"})
            check["status"] = "blocked_outside_root"
        elif not resolved.is_file():
            issues.append({"index": index, "path": relative, "type": "file_not_found"})
            check["status"] = "blocked_file_not_found"
        else:
            observed = _sha256(resolved)
            check.update({"observed_sha256": observed, "size_bytes": resolved.stat().st_size})
            if expected and observed != expected:
                issues.append({"index": index, "path": relative, "type": "sha256_mismatch", "expected": expected, "observed": observed})
                check["status"] = "hash_mismatch"
            else:
                check["status"] = "hash_verified"
        file_checks.append(check)

    planned_run_checks: list[dict[str, Any]] = []
    if manifest_stage == "planning":
        if payload.get("runs") not in ([], None):
            issues.append({"type": "planning_manifest_runs_must_be_empty"})
        planned_run_checks, planned_issues = _validate_planned_runs(payload.get("planned_runs"), root, files_by_path)
        issues.extend(planned_issues)
    elif payload.get("planned_runs") not in (None, []):
        issues.append({"type": "planned_runs_not_allowed_after_execution"})

    run_records = payload.get("runs")
    if not isinstance(run_records, list):
        issues.append({"type": "runs_must_be_list"})
        run_records = []
    if manifest_stage != "planning" and not run_records:
        issues.append({"type": "runs_must_be_nonempty_list"})
    run_checks: list[dict[str, Any]] = []
    for index, run in enumerate(run_records if manifest_stage != "planning" else [], start=1):
        if not isinstance(run, dict):
            issues.append({"index": index, "type": "run_record_must_be_object"})
            continue
        run_id = str(run.get("run_id") or "").strip()
        script = _norm_rel(run.get("script"))
        script_hash = str(run.get("script_sha256") or "").strip().lower()
        command = str(run.get("command") or "").strip()
        command_argv = run.get("command_argv")
        status = str(run.get("status") or "").strip().lower()
        inputs = run.get("inputs")
        outputs = run.get("outputs")
        if not run_id or not script or not command:
            issues.append({"index": index, "run_id": run_id, "type": "run_requires_id_script_command"})
        if not isinstance(command_argv, list) or len(command_argv) < 2 or not all(isinstance(item, str) and item for item in command_argv):
            issues.append({"index": index, "run_id": run_id, "type": "command_argv_must_be_nonempty_string_list"})
        else:
            normalized_argv = [_norm_rel(item) for item in command_argv]
            if command_argv[0] not in {"python", "python3"}:
                issues.append({"index": index, "run_id": run_id, "type": "command_argv_requires_python_launcher"})
            if normalized_argv[1] != script:
                issues.append({"index": index, "run_id": run_id, "type": "command_argv_script_mismatch", "script": normalized_argv[1]})
            for argument in command_argv[1:]:
                normalized_argument = _norm_rel(argument)
                if "\x00" in argument or not _is_safe_relative(normalized_argument):
                    issues.append({"index": index, "run_id": run_id, "type": "command_argv_contains_unsafe_path", "argument": argument})
                    break
        if status not in RUN_STATUSES:
            issues.append({"index": index, "run_id": run_id, "type": "invalid_run_status", "value": status})
        elif manifest_stage == "verified" and status != "verified":
            issues.append({"index": index, "run_id": run_id, "type": "verified_manifest_requires_verified_runs"})
        if not isinstance(inputs, list) or not inputs:
            issues.append({"index": index, "run_id": run_id, "type": "run_inputs_must_be_nonempty_list"})
            inputs = []
        if not isinstance(outputs, list) or not outputs:
            issues.append({"index": index, "run_id": run_id, "type": "run_outputs_must_be_nonempty_list"})
            outputs = []
        if not _is_safe_relative(script):
            issues.append({"index": index, "run_id": run_id, "type": "script_path_must_be_safe_relative"})
        else:
            script_path = _resolve(root, script)
            if not _under_root(root, script_path) or not script_path.is_file():
                issues.append({"index": index, "run_id": run_id, "type": "script_not_found", "script": script})
            elif not SHA_RE.fullmatch(script_hash):
                issues.append({"index": index, "run_id": run_id, "type": "invalid_script_sha256"})
            elif _sha256(script_path) != script_hash:
                issues.append({"index": index, "run_id": run_id, "type": "script_sha256_mismatch", "script": script})
        for io_kind, paths in (("input", inputs), ("output", outputs)):
            for relative_value in paths:
                relative = _norm_rel(relative_value)
                if relative not in files_by_path:
                    issues.append({"index": index, "run_id": run_id, "type": f"run_{io_kind}_not_listed_in_files", "path": relative})
                elif io_kind == "output" and str(files_by_path[relative].get("role", "")).lower() not in {"derived", "metadata", "other"}:
                    issues.append({"index": index, "run_id": run_id, "type": "run_output_role_not_output_compatible", "path": relative})
        run_checks.append({"run_id": run_id, "script": script, "status": "verified" if not any(item.get("run_id") == run_id and item.get("index") == index for item in issues) else "blocked", "inputs": inputs, "outputs": outputs})

    seen_runs: set[str] = set()
    for run in run_records:
        if isinstance(run, dict):
            run_id = str(run.get("run_id") or "").strip()
            if run_id and run_id in seen_runs:
                issues.append({"run_id": run_id, "type": "duplicate_run_id"})
            seen_runs.add(run_id)

    if not issues and files_by_path and manifest_stage == "planning" and planned_run_checks:
        status = "planning_public_dataset_manifest"
    elif not issues and files_by_path and run_records:
        status = "verified_public_dataset_manifest"
    else:
        status = "invalid_public_dataset_manifest"
    if manifest_stage == "planning" and status == "planning_public_dataset_manifest":
        formal_status = "planning_source_content_checked" if access_status == "content_checked" else "planning_source_access_conditional"
    else:
        formal_status = "online_source_content_verified" if status == "verified_public_dataset_manifest" and access_status == "content_checked" else "conditional_online_source_access"
    if issues:
        formal_status = "blocked_by_manifest_issues"
    return {
        "status": status,
        "manifest_stage": manifest_stage,
        "formal_status": formal_status,
        "manifest_id": payload.get("manifest_id", ""),
        "dataset_id": payload.get("dataset_id", ""),
        "accession": payload.get("accession", ""),
        "n_files": len(file_records),
        "n_runs": len(run_records),
        "n_planned_runs": len(planned_run_checks),
        "planned_run_checks": planned_run_checks,
        "file_checks": file_checks,
        "run_checks": run_checks,
        "issues": issues,
        "warnings": warnings,
        "inference_warning": "Manifest verification establishes local file integrity, provenance linkage and declared context only; it does not verify normalization suitability, biological representativeness, cell identity, statistical validity or causality.",
    }


def validate_file(path: Path, root: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return validate_payload(payload, root)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root used to resolve relative paths")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        result = validate_file(args.input, args.root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] in {"planning_public_dataset_manifest", "verified_public_dataset_manifest"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))








