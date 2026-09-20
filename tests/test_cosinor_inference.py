import csv
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_cosinor_inference import analyze_file


class CosinorInferenceTests(unittest.TestCase):
    def _write_direct(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=["subject_id", "time_hours", "value"])
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def _write_expression(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "time", "expression", "gene_symbol", "cell_type", "background"])
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def _write_metadata(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        fields = ["sample_id", "ZT_or_CT", "experimental_unit", "biological_replicate_id", "batch_id", "temperature_C"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def _rows(self, amplitude=0.0, repeated=False):
        rows = []
        for index, time in enumerate([0.0, 6.0, 12.0, 18.0] * 6):
            subject = f"s{index}" if not repeated else "s0"
            value = 5.0 + amplitude * math.cos(2.0 * math.pi * time / 24.0) + ((index % 3) - 1) * 0.03
            rows.append({"subject_id": subject, "time_hours": time, "value": value})
        return rows

    def test_time_system_is_required(self):
        path = self._write_direct(self._rows(amplitude=4.0))
        try:
            result = analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7, experimental_unit="fly")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_time_system_unspecified")

    def test_strong_rhythm_has_low_permutation_p_with_declared_unit(self):
        path = self._write_direct(self._rows(amplitude=4.0))
        try:
            result = analyze_file(path, n_permutations=200, n_bootstrap=200, seed=7, experimental_unit="independent_sample", time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        group = result["groups"][0]
        self.assertEqual(group["status"], "exploratory_inferential_cosinor")
        self.assertLess(group["p_amplitude_permutation"], 0.05)
        self.assertLess(group["bootstrap_amplitude_ci95"][0], 4.0)
        self.assertIsNotNone(group["q_amplitude_bh"])
        self.assertEqual(len(result["input_file_metadata"]["sha256"]), 64)
        self.assertEqual(result["time_system"], "ZT")

    def test_flat_signal_does_not_become_rhythmic(self):
        path = self._write_direct(self._rows(amplitude=0.0))
        try:
            result = analyze_file(path, n_permutations=200, n_bootstrap=200, seed=7, experimental_unit="independent_sample", time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        group = result["groups"][0]
        self.assertEqual(group["status"], "exploratory_inferential_cosinor")
        self.assertGreater(group["p_amplitude_permutation"], 0.1)

    def test_repeated_subjects_are_blocked(self):
        path = self._write_direct(self._rows(amplitude=4.0, repeated=True))
        try:
            result = analyze_file(path, n_permutations=50, n_bootstrap=50, seed=7, experimental_unit="independent_sample", time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        group = result["groups"][0]
        self.assertEqual(group["status"], "blocked_repeated_subjects")
        self.assertIn("s0", group["repeated_subject_ids"])

    def test_missing_unit_is_blocked_instead_of_inferred_from_sample_id(self):
        path = self._write_direct(self._rows(amplitude=4.0))
        try:
            result = analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7, time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_experimental_unit_unspecified")
        self.assertEqual(result["groups"][0]["status"], "blocked_experimental_unit_unspecified")

    def test_dirty_missing_declared_unit_is_blocked(self):
        path = self._write_direct(self._rows(amplitude=4.0))
        try:
            result = analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7, experimental_unit="nan", time_system="ZT")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_experimental_unit_unspecified")
        self.assertEqual(result["groups"][0]["experimental_unit"], "unspecified")

    def test_nonfinite_direct_time_or_value_is_rejected(self):
        for field in ("time_hours", "value"):
            rows = self._rows(amplitude=0.0)
            rows[0][field] = "nan"
            path = self._write_direct(rows)
            try:
                with self.assertRaisesRegex(ValueError, "invalid numeric/time row"):
                    analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7, experimental_unit="fly", time_system="ZT")
            finally:
                path.unlink(missing_ok=True)

    def test_nonfinite_expression_value_is_rejected(self):
        rows = [{
            "sample_id": f"sample{index}", "time": f"ZT{time}",
            "expression": ("nan" if index == 0 else "1"),
            "gene_symbol": "na", "cell_type": "s-LNv", "background": "w1118",
        } for index, time in enumerate([0, 6, 12, 18])]
        path = self._write_expression(rows)
        try:
            with self.assertRaisesRegex(ValueError, "invalid numeric/time row"):
                analyze_file(path, n_permutations=20, n_bootstrap=20, seed=7, experimental_unit="fly", time_system="ZT")
        finally:
            path.unlink(missing_ok=True)

    def test_metadata_join_sets_biological_unit_and_time(self):
        data_rows = []
        metadata_rows = []
        for index, time in enumerate([0, 6, 12, 18]):
            sample_id = f"sample{index}"
            data_rows.append({
                "sample_id": sample_id,
                "time": f"ZT{time}",
                "expression": 5.0 + 4.0 * math.cos(2.0 * math.pi * time / 24.0),
                "gene_symbol": "na", "cell_type": "s-LNv", "background": "w1118",
            })
            metadata_rows.append({
                "sample_id": sample_id, "ZT_or_CT": f"ZT{time}", "experimental_unit": "fly",
                "biological_replicate_id": sample_id, "batch_id": "batch1", "temperature_C": "25",
            })
        data_path = self._write_expression(data_rows)
        metadata_path = self._write_metadata(metadata_rows)
        try:
            result = analyze_file(data_path, n_permutations=50, n_bootstrap=50, seed=7, metadata_path=metadata_path, time_system="ZT")
        finally:
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        group = result["groups"][0]
        self.assertTrue(result["metadata_joined"])
        self.assertEqual(group["experimental_unit"], "fly")
        self.assertEqual(group["n_biological_replicates"], 4)
        self.assertEqual(group["status"], "exploratory_inferential_cosinor")
        self.assertEqual(len(result["metadata_file_metadata"]["sha256"]), 64)

    def test_time_basis_mismatch_is_rejected(self):
        data_path = self._write_expression([{
            "sample_id": "sample0", "time": "CT0", "expression": "1", "gene_symbol": "na", "cell_type": "s-LNv", "background": "w1118"
        }])
        metadata_path = self._write_metadata([{
            "sample_id": "sample0", "ZT_or_CT": "CT0", "experimental_unit": "fly", "biological_replicate_id": "sample0", "batch_id": "batch1", "temperature_C": "25"
        }])
        try:
            with self.assertRaisesRegex(ValueError, "time system mismatch"):
                analyze_file(data_path, metadata_path=metadata_path, time_system="ZT")
        finally:
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)

    def test_metadata_time_mismatch_is_rejected(self):
        data_path = self._write_expression([{
            "sample_id": "sample0", "time": "ZT0", "expression": "1", "gene_symbol": "na", "cell_type": "s-LNv", "background": "w1118"
        }])
        metadata_path = self._write_metadata([{
            "sample_id": "sample0", "ZT_or_CT": "ZT6", "experimental_unit": "fly", "biological_replicate_id": "sample0", "batch_id": "batch1", "temperature_C": "25"
        }])
        try:
            with self.assertRaisesRegex(ValueError, "time mismatch"):
                analyze_file(data_path, metadata_path=metadata_path, time_system="ZT")
        finally:
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)

    def test_gse22308_public_matrix_uses_pooled_sample_unit(self):
        data_path = ROOT / "validation" / "public-data" / "GSE22308_channel_regulator_expression_samples.csv"
        metadata_path = ROOT / "validation" / "public-data" / "GSE22308_sample_metadata.csv"
        result = analyze_file(data_path, n_permutations=20, n_bootstrap=20, seed=20260906, metadata_path=metadata_path, time_system="ZT")
        statuses = {status: sum(group["status"] == status for group in result["groups"]) for status in {
            "exploratory_inferential_cosinor", "insufficient_or_invalid_time_series"
        }}
        self.assertTrue(result["metadata_joined"])
        self.assertEqual(result["n_groups"], 76)
        self.assertEqual(statuses["exploratory_inferential_cosinor"], 19)
        self.assertEqual(statuses["insufficient_or_invalid_time_series"], 57)
        testable = next(group for group in result["groups"] if group["status"] == "exploratory_inferential_cosinor")
        self.assertEqual(testable["experimental_unit"], "pooled_cell_sample")
        self.assertIn("not an animal-level effect estimate", testable["inference_warning"])


if __name__ == "__main__":
    unittest.main()
