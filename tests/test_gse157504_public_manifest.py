import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_public_dataset_manifest import _safe_argv
from scripts.validate_public_dataset_manifest import validate_file


class GSE157504PublicManifestTests(unittest.TestCase):
    def test_real_manifest_verifies_all_hashes_and_run_links(self):
        manifest = ROOT / "validation" / "public-data" / "GSE157504-candidate-channel-rhythm-provenance-manifest.json"
        result = validate_file(manifest, ROOT)
        self.assertEqual(result["status"], "verified_public_dataset_manifest")
        self.assertEqual(result["n_files"], 11)
        self.assertEqual(result["n_runs"], 2)
        self.assertEqual(result["issues"], [])

    def test_new_scripts_are_allowlisted_for_structured_replay(self):
        for script in (
            "scripts/extract_published_sc_clock_channel_rhythms.py",
            "scripts/audit_gse157504_candidate_detection.py",
        ):
            argv = ["python", script, "input.csv"]
            safe, issue = _safe_argv({"run_id": "test", "script": script, "command_argv": argv})
            self.assertEqual(safe, argv)
            self.assertIsNone(issue)


if __name__ == "__main__":
    unittest.main()
