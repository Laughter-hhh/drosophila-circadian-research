import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_public_dataset_manifest import ALLOWED_SCRIPTS, _safe_argv


class GSE157504EvidenceBridgeReplayTests(unittest.TestCase):
    def test_bridge_validator_and_scorer_scripts_are_explicitly_allowlisted(self):
        scripts = (
            "scripts/build_gse157504_candidate_evidence.py",
            "scripts/validate_evidence_search_log.py",
            "scripts/validate_candidate_evidence.py",
            "scripts/score_candidates.py",
        )
        for script in scripts:
            with self.subTest(script=script):
                self.assertIn(script, ALLOWED_SCRIPTS)
                argv, issue = _safe_argv({"run_id": "test", "script": script, "command_argv": ["python", script, "input.csv"]})
                self.assertEqual(argv, ["python", script, "input.csv"])
                self.assertIsNone(issue)

    def test_unreviewed_script_remains_blocked(self):
        argv, issue = _safe_argv({
            "run_id": "test",
            "script": "scripts/not_reviewed.py",
            "command_argv": ["python", "scripts/not_reviewed.py", "input.csv"],
        })
        self.assertIsNone(argv)
        self.assertEqual(issue["type"], "command_argv_script_not_allowed")


if __name__ == "__main__":
    unittest.main()
