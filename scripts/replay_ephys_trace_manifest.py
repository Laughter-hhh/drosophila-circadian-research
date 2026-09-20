#!/usr/bin/env python3
"""Replay a validated ephys trace-analysis manifest in a temporary mirror."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.validate_ephys_trace_replay_manifest import ALLOWED_SCRIPTS, validate_file
    from scripts.validate_public_dataset_manifest import _norm_rel, _resolve, _sha256
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.validate_ephys_trace_replay_manifest import ALLOWED_SCRIPTS, validate_file
    from scripts.validate_public_dataset_manifest import _norm_rel, _resolve, _sha256


def _copy_inputs(source_root: Path, replay_root: Path, payload: dict[str, Any]) -> None:
    shutil.copytree(source_root / "scripts", replay_root / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    produced = {_norm_rel(path) for run in payload["runs"] for path in run["outputs"]}
    for record in payload["files"]:
        relative = _norm_rel(record["path"])
        if relative in produced:
            continue
        target = _resolve(replay_root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_resolve(source_root, relative), target)


def replay_file(manifest_path: Path, source_root: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    validation = validate_file(manifest_path, source_root)
    if validation["status"] != "verified_ephys_trace_replay_manifest":
        return {"status": "blocked_ephys_trace_replay", "manifest_validation": validation, "runs": [], "output_checks": [], "issues": [{"type": "manifest_validation_failed"}]}
    with manifest_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    run_reports: list[dict[str, Any]] = []
    output_checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    files = {_norm_rel(item["path"]): item for item in payload["files"]}
    with tempfile.TemporaryDirectory(prefix="drosophila-ephys-replay-") as temporary:
        replay_root = Path(temporary)
        _copy_inputs(source_root, replay_root, payload)
        for run in payload["runs"]:
            argv = run["command_argv"]
            script = _norm_rel(run["script"])
            if argv[0] not in {"python", "python3"} or script not in ALLOWED_SCRIPTS:
                return {"status": "blocked_ephys_trace_replay", "manifest_validation": validation, "runs": run_reports, "output_checks": output_checks, "issues": [{"type": "argv_gate_failed"}]}
            completed = subprocess.run([sys.executable, str(_resolve(replay_root, script)), *argv[2:]], cwd=replay_root, text=True, capture_output=True, timeout=timeout_seconds, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            run_reports.append({"run_id": run["run_id"], "returncode": completed.returncode, "stdout_preview": completed.stdout[-1000:], "stderr_preview": completed.stderr[-1000:]})
            if completed.returncode != 0:
                issues.append({"run_id": run["run_id"], "type": "run_nonzero_exit", "returncode": completed.returncode})
                break
            for output_path in run["outputs"]:
                relative = _norm_rel(output_path)
                output = _resolve(replay_root, relative)
                expected = str(files[relative]["sha256"]).lower()
                observed = _sha256(output) if output.is_file() else None
                check = {"run_id": run["run_id"], "path": relative, "expected_sha256": expected, "observed_sha256": observed, "status": "replay_hash_verified" if observed == expected else "hash_mismatch_after_replay"}
                output_checks.append(check)
                if observed != expected:
                    issues.append({"run_id": run["run_id"], "type": "output_hash_mismatch_after_replay", "path": relative})
            if issues:
                break
    return {"status": "verified_ephys_trace_replay" if not issues else "blocked_ephys_trace_replay", "n_runs": len(run_reports), "n_output_checks": len(output_checks), "runs": run_reports, "output_checks": output_checks, "issues": issues, "manifest_validation": validation, "inference_warning": "Replay verifies deterministic raw/QC/derivation/analysis execution from registered synthetic inputs; it does not establish any biological result."}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    result = replay_file(args.input, args.root, args.timeout_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_ephys_trace_replay" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

