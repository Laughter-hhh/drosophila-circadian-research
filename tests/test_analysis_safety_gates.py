import shutil
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_preanalysis_cosinor import analyze_bundle as analyze_fixed_bundle
from scripts.analyze_preanalysis_nested_cosinor import analyze_bundle as analyze_nested_bundle


class AnalysisSafetyGateTests(unittest.TestCase):
    def setUp(self):
        self.metadata = ROOT / "validation" / "synthetic-ephys-bundle-metadata.csv"
        self.raw_qc = ROOT / "validation" / "synthetic-ephys-raw-qc.csv"
        self.measurements = ROOT / "validation" / "synthetic-ephys-cosinor-derived.csv"
        self.nested_metadata = ROOT / "validation" / "synthetic-ephys-nested-metadata.csv"
        self.nested_raw_qc = ROOT / "validation" / "synthetic-ephys-nested-raw-qc.csv"
        self.nested_measurements = ROOT / "validation" / "synthetic-ephys-nested-derived.csv"

    def test_time_system_is_required_before_fixed_fit(self):
        result = analyze_fixed_bundle(self.metadata, self.raw_qc, self.measurements)
        self.assertEqual(result["status"], "blocked_preanalysis_cosinor")
        self.assertEqual(result["issues"][0]["type"], "time_system_unspecified")

    def test_time_system_is_required_before_nested_fit(self):
        result = analyze_nested_bundle(self.nested_metadata, self.nested_raw_qc, self.nested_measurements, metric_name="resting_membrane_potential", n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["status"], "blocked_preanalysis_nested_cosinor")
        self.assertEqual(result["issues"][0]["type"], "time_system_unspecified")

    def test_condition_column_must_be_explicitly_grouped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "condition_metadata.csv"
            lines = self.metadata.read_text(encoding="utf-8").splitlines()
            lines[0] += ",treatment"
            lines[1:] = [line + ",vehicle" for line in lines[1:]]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = analyze_fixed_bundle(path, self.raw_qc, self.measurements, time_system="ZT")
        self.assertEqual(result["status"], "blocked_preanalysis_cosinor")
        self.assertEqual(result["issues"][0]["type"], "condition_fields_not_grouped")

    def test_mixed_metrics_are_not_pooled_in_fixed_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mixed_metrics.csv"
            lines = self.measurements.read_text(encoding="utf-8").splitlines()
            lines[0] += ",metric_name,value_unit"
            lines[1:] = [line + ",resting_membrane_potential,mV" for line in lines[1:]]
            lines.append(lines[1].replace(",resting_membrane_potential,mV", ",calcium_signal,AU"))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = analyze_fixed_bundle(self.metadata, self.raw_qc, path, time_system="ZT")
        self.assertEqual(result["status"], "blocked_preanalysis_cosinor")
        self.assertEqual(result["issues"][0]["type"], "multiple_metrics_unspecified")

    def test_pass_raw_record_without_attached_file_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw_qc.csv"
            shutil.copytree(ROOT / "validation" / "synthetic-raw", Path(directory) / "synthetic-raw")
            lines = self.raw_qc.read_text(encoding="utf-8").splitlines()
            fields = lines[0].split(",")
            status_index = fields.index("file_status")
            hash_index = fields.index("raw_file_sha256")
            row = lines[1].split(",")
            row[status_index] = "not_attached"
            row[hash_index] = "not_available"
            lines[1] = ",".join(row)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = analyze_fixed_bundle(self.metadata, path, self.measurements, time_system="ZT")
        self.assertEqual(result["status"], "blocked_preanalysis_cosinor")
        self.assertEqual(result["issues"][0]["type"], "pass_raw_file_not_present")


if __name__ == "__main__":
    unittest.main()
