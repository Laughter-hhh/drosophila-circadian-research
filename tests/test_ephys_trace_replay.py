import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_ephys_trace_manifest import replay_file
from scripts.validate_ephys_trace_replay_manifest import _read_raw_qc, validate_file, validate_payload
from scripts.validate_experiment_metadata import validate as validate_metadata


class EphysTraceReplayTests(unittest.TestCase):
    manifest_path = ROOT / "validation" / "synthetic-ephys-trace-replay-manifest.json"

    def test_portable_metadata_provenance_uses_relative_path(self):
        result = validate_metadata(
            ROOT / "validation" / "synthetic-ephys-trace-metadata.csv",
            assay="ephys",
            stage="exploratory",
            provenance_root=ROOT,
        )
        self.assertEqual(result["status"], "verified_metadata")
        self.assertEqual(
            result["input_file_metadata"]["path"],
            "validation/synthetic-ephys-trace-metadata.csv",
        )

    def test_real_synthetic_trace_manifest_replays_in_isolation(self):
        result = replay_file(self.manifest_path, ROOT, timeout_seconds=120)
        self.assertEqual(result["status"], "verified_ephys_trace_replay")
        self.assertEqual(result["n_runs"], 5)
        self.assertEqual(result["n_output_checks"], 6)
        self.assertTrue(all(item["status"] == "replay_hash_verified" for item in result["output_checks"]))

    def test_unregistered_absolute_raw_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw-qc.csv"
            path.write_text(
                "record_id,raw_file_path,raw_file_sha256,file_status\n"
                "r1,C:/outside/trace.abf,0,present\n",
                encoding="utf-8",
            )
            issues = _read_raw_qc(path, ROOT, {})
        self.assertTrue(any(item["type"] == "raw_file_path_must_be_safe_relative" for item in issues))

    def test_non_python_command_is_rejected(self):
        with self.manifest_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        payload = copy.deepcopy(payload)
        payload["runs"][0]["command_argv"][0] = "cmd"
        result = validate_payload(payload, ROOT)
        self.assertEqual(result["status"], "invalid_ephys_trace_replay_manifest")
        self.assertTrue(any(item["type"] == "command_argv_requires_python_launcher" for item in result["issues"]))


if __name__ == "__main__":
    unittest.main()

