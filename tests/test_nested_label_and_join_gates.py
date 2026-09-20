import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_preanalysis_nested_cosinor import analyze_bundle


class NestedLabelAndJoinGateTests(unittest.TestCase):
    def setUp(self):
        self.metadata = ROOT / "validation" / "synthetic-ephys-nested-metadata.csv"
        self.raw_qc = ROOT / "validation" / "synthetic-ephys-nested-raw-qc.csv"
        self.measurements = ROOT / "validation" / "synthetic-ephys-nested-derived.csv"

    def test_named_metric_with_unlabeled_rows_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing_metric.csv"
            path.write_text(self.measurements.read_text(encoding="utf-8") + "rec01,meta01,fly01,0,12.0,,mV,cellC\n", encoding="utf-8")
            result = analyze_bundle(self.metadata, self.raw_qc, path, time_system="ZT", metric_name="resting_membrane_potential", n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["status"], "blocked_preanalysis_nested_cosinor")
        self.assertEqual(result["issues"][0]["type"], "metric_name_missing_rows")

    def test_duplicate_metadata_join_key_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate_metadata.csv"
            path.write_text(self.metadata.read_text(encoding="utf-8") + self.metadata.read_text(encoding="utf-8").splitlines()[1] + "\n", encoding="utf-8")
            result = analyze_bundle(path, self.raw_qc, self.measurements, time_system="ZT", metric_name="resting_membrane_potential", n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["status"], "blocked_preanalysis_nested_cosinor")
        self.assertIn(result["issues"][0]["type"], {"preanalysis_bundle_gate_failed", "duplicate_metadata_join_key"})

    def test_duplicate_raw_record_id_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate_raw.csv"
            raw_text = self.raw_qc.read_text(encoding="utf-8")
            path.write_text(raw_text + raw_text.splitlines()[1] + "\n", encoding="utf-8")
            result = analyze_bundle(self.metadata, path, self.measurements, time_system="ZT", metric_name="resting_membrane_potential", n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["status"], "blocked_preanalysis_nested_cosinor")
        self.assertIn(result["issues"][0]["type"], {"preanalysis_bundle_gate_failed", "duplicate_raw_qc_record_id"})


if __name__ == "__main__":
    unittest.main()
