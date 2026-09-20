import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_gse157504_candidate_detection import run
from tests.test_gse157504_candidate_detection import GSE157504CandidateDetectionTests


class GSE157504DetectionApiTests(unittest.TestCase):
    def test_run_api_is_callable_without_cli_main(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_tar, annotation, candidates = GSE157504CandidateDetectionTests()._fixture(root)
            sample_rows, group_rows, feature_rows, report = run(raw_tar, annotation, candidates, root)
            self.assertTrue(report["join"]["join_complete"])
            self.assertEqual(len(sample_rows), 2)
            self.assertEqual(len(group_rows), 2)
            self.assertEqual(len(feature_rows), 2)


if __name__ == "__main__":
    unittest.main()
