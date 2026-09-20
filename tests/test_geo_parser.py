import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.parse_geo_series_matrix import parse


MINI_MATRIX = """!Series_geo_accession\t\"GSETEST\"
!Sample_geo_accession\t\"GSM1\"\t\"GSM2\"
!Sample_title\t\"s1\"\t\"s2\"
!Sample_organism_ch1\t\"Drosophila melanogaster\"\t\"Drosophila melanogaster\"
!Sample_characteristics_ch1\t\"time: ZT0\"\t\"time: ZT12\"
!Sample_platform_id\t\"GPLTEST\"\t\"GPLTEST\"
!series_matrix_table_begin
\"ID_REF\"\t\"GSM1\"\t\"GSM2\"
\"probe_1\"\t1\t2
\"probe_2\"\t3\t4
!series_matrix_table_end
"""


class GeoParserTests(unittest.TestCase):
    def _write(self, text=MINI_MATRIX):
        handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        return Path(handle.name)

    def test_sample_alignment_dimensions_and_hash_are_recorded(self):
        path = self._write()
        try:
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            summary, metadata = parse(path, expected_sha256=expected)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(summary["status"], "exploratory_geo_parse")
        self.assertEqual(summary["source_integrity"], "verified_sha256")
        self.assertEqual(summary["input_file_metadata"]["sha256"], expected)
        self.assertTrue(summary["sample_alignment_ok"])
        self.assertEqual(summary["n_samples_annotation"], 2)
        self.assertEqual(summary["n_samples_expression"], 2)
        self.assertEqual(summary["n_probes_or_features"], 2)
        self.assertEqual(metadata[0]["sample_id"], "GSM1")
        self.assertIn("time", metadata[0]["characteristics_json"])

    def test_sample_alignment_mismatch_is_blocked(self):
        path = self._write(MINI_MATRIX.replace('"GSM1"\t"GSM2"\n"probe_1"', '"GSM2"\t"GSM1"\n"probe_1"'))
        try:
            summary, _ = parse(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(summary["status"], "blocked_geo_parse")
        self.assertFalse(summary["sample_alignment_ok"])
        self.assertEqual(summary["issues"][0]["type"], "sample_alignment_mismatch")

    def test_expected_hash_mismatch_is_rejected(self):
        path = self._write()
        try:
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                parse(path, expected_sha256="0" * 64)
        finally:
            path.unlink(missing_ok=True)

    def test_portable_provenance_path_replaces_machine_specific_path(self):
        path = self._write()
        try:
            summary, _ = parse(path, provenance_path="validation/public-data/example_matrix.txt")
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(summary["source_file"], "validation/public-data/example_matrix.txt")
        self.assertEqual(summary["input_file_metadata"]["path"], "validation/public-data/example_matrix.txt")


if __name__ == "__main__":
    unittest.main()


