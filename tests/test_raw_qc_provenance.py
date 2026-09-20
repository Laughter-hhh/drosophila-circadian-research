import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_raw_qc_provenance import validate


FIELDS = [
    "record_id", "raw_file_path", "raw_file_sha256", "file_status", "metadata_row_id", "biological_replicate_id", "experimental_unit", "assay", "cell_type", "cell_identity_method", "qc_status", "exclusion_reason", "blinding_status", "derived_output_path",
    "seal_MOhm", "access_resistance_MOhm", "holding_current_pA", "baseline_drift_mV_per_min", "sampling_rate_Hz",
]
IMG_FIELDS = FIELDS[:14] + ["roi_count", "motion_qc", "focus_qc", "signal_to_noise"]


class RawQcProvenanceTests(unittest.TestCase):
    def _write(self, rows, fields=FIELDS):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return Path(handle.name)

    def _row(self, record_id="r1", qc_status="pass"):
        return {
            "record_id": record_id, "raw_file_path": "trace.abf", "raw_file_sha256": "0" * 64, "file_status": "present",
            "metadata_row_id": "m1", "biological_replicate_id": "fly1", "experimental_unit": "cell", "assay": "ephys",
            "cell_type": "s-LNv", "cell_identity_method": "anatomy", "qc_status": qc_status, "exclusion_reason": "",
            "blinding_status": "blinded", "derived_output_path": "out.csv", "seal_MOhm": "1.2", "access_resistance_MOhm": "18",
            "holding_current_pA": "-3", "baseline_drift_mV_per_min": "0.02", "sampling_rate_Hz": "10000",
        }

    def test_public_synthetic_manifest_verifies_real_hashes(self):
        path = ROOT / "validation" / "synthetic-ephys-raw-qc.csv"
        result = validate(path, assay="ephys", check_files=True)
        self.assertEqual(result["status"], "verified_raw_qc_provenance")
        self.assertEqual(result["n_rows"], 3)
        self.assertTrue(any(w["type"] == "raw_file_not_attached" for w in result["warnings"]))

    def test_hash_mismatch_is_blocked_when_file_check_enabled(self):
        raw = tempfile.NamedTemporaryFile("w", delete=False, suffix=".abf", encoding="utf-8")
        raw.write("trace")
        raw.close()
        row = self._row()
        row["raw_file_path"] = raw.name
        path = self._write([row])
        try:
            result = validate(path, assay="ephys", check_files=True)
        finally:
            path.unlink(missing_ok=True)
            Path(raw.name).unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_raw_qc_provenance")
        self.assertTrue(any(issue["type"] == "raw_file_hash_mismatch" for issue in result["issues"]))

    def test_excluded_record_requires_reason(self):
        row = self._row(qc_status="excluded")
        row["exclusion_reason"] = ""
        path = self._write([row])
        try:
            result = validate(path, assay="ephys")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_raw_qc_provenance")
        self.assertTrue(any(issue["type"] == "exclusion_reason_required" for issue in result["issues"]))

    def test_pass_qc_requires_finite_metrics(self):
        row = self._row()
        row["access_resistance_MOhm"] = "nan"
        path = self._write([row])
        try:
            result = validate(path, assay="ephys")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_raw_qc_provenance")
        self.assertTrue(any(issue["type"] == "pass_qc_requires_finite_metric" for issue in result["issues"]))

    def test_metadata_join_conflict_is_blocked(self):
        row = self._row()
        manifest = self._write([row])
        metadata = self._write([{"metadata_row_id": "m1", "biological_replicate_id": "fly2", "cell_type": "s-LNv"}], fields=["metadata_row_id", "biological_replicate_id", "cell_type"])
        try:
            result = validate(manifest, assay="ephys", metadata_path=metadata)
        finally:
            manifest.unlink(missing_ok=True)
            metadata.unlink(missing_ok=True)
        self.assertEqual(result["status"], "blocked_raw_qc_provenance")
        self.assertTrue(any(issue["type"] == "metadata_join_conflict" for issue in result["issues"]))

    def test_imaging_pass_requires_roi_and_quality_metrics(self):
        row = {field: "" for field in IMG_FIELDS}
        row.update({"record_id": "img1", "raw_file_path": "image.tif", "raw_file_sha256": "0" * 64, "file_status": "present", "metadata_row_id": "m1", "biological_replicate_id": "fly1", "experimental_unit": "cell", "assay": "imaging", "cell_type": "s-LNv", "cell_identity_method": "anatomy", "qc_status": "pass", "blinding_status": "blinded", "derived_output_path": "out.csv", "roi_count": "2", "motion_qc": "0.1", "focus_qc": "0.9", "signal_to_noise": "5"})
        path = self._write([row], fields=IMG_FIELDS)
        try:
            result = validate(path, assay="imaging")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result["status"], "verified_raw_qc_provenance")


if __name__ == "__main__":
    unittest.main()
