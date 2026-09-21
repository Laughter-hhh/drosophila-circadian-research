import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_geo_sample_map import audit_geo_sample_map


class GeoSampleMapTests(unittest.TestCase):
    def _fixture(self, directory: Path):
        soft_path = directory / "family.soft"
        matrix_path = directory / "matrix.tsv"
        mapping_path = directory / "mapping.csv"
        times = (2, 6, 10, 14, 18, 22)
        sample_rows = []
        matrix_columns = []
        for course_index in range(2):
            for time in times:
                accession = f"GSM{1000000 + course_index * 10 + time}"
                title = f"COURSE{course_index + 1}_ZT{time}"
                column = title
                matrix_columns.append(column)
                sample_rows.append((accession, title, column, f"course_{course_index + 1}", time))

        blocks = []
        for accession, title, _, _, time in sample_rows:
            blocks.extend([
                f"^SAMPLE = {accession}",
                f"!Sample_title = {title}",
                "!Sample_source_name_ch1 = LNv",
                "!Sample_characteristics_ch1 = timepoint: ZT" + str(time),
                "!Sample_characteristics_ch1 = tissue: neurons",
                "!Sample_characteristics_ch1 = type: LNv",
            ])
        soft_path.write_text("\n".join(blocks) + "\n", encoding="utf-8")
        with matrix_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["Symbol", "", *matrix_columns])
            writer.writerow(["FBtr1", "Sh", *(["1"] * len(matrix_columns))])
        with mapping_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "matrix_path", "matrix_column", "matrix_alias", "gsm_accession", "timecourse_id",
            ])
            writer.writeheader()
            for accession, title, column, course_id, _ in sample_rows:
                writer.writerow({
                    "matrix_path": matrix_path.as_posix(),
                    "matrix_column": column,
                    "matrix_alias": title,
                    "gsm_accession": accession,
                    "timecourse_id": course_id,
                })
        return soft_path, mapping_path, matrix_path

    def test_valid_map_checks_all_columns_and_two_complete_timecourses(self):
        with tempfile.TemporaryDirectory() as tmp:
            soft_path, mapping_path, matrix_path = self._fixture(Path(tmp))
            report, metadata = audit_geo_sample_map(
                soft_path, mapping_path, [("LNv", matrix_path)],
            )

        self.assertEqual(report["status"], "verified_geo_sample_mapping")
        self.assertEqual(report["n_sample_columns"], 12)
        self.assertEqual(report["n_unique_geo_samples"], 12)
        self.assertEqual(len(metadata), 12)
        self.assertEqual(metadata[0]["experimental_unit"], "pooled_neuron_library")
        self.assertEqual(metadata[0]["biological_replicate_id"], "GSM1000002")

    def test_swapped_gsm_is_rejected_by_title_alias_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            soft_path, mapping_path, matrix_path = self._fixture(Path(tmp))
            with mapping_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["gsm_accession"], rows[1]["gsm_accession"] = rows[1]["gsm_accession"], rows[0]["gsm_accession"]
            with mapping_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "matrix alias does not match GEO title"):
                audit_geo_sample_map(soft_path, mapping_path, [("LNv", matrix_path)])

    def test_unmapped_matrix_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            soft_path, mapping_path, matrix_path = self._fixture(Path(tmp))
            with mapping_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows.pop()
            with mapping_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "matrix columns missing from mapping"):
                audit_geo_sample_map(soft_path, mapping_path, [("LNv", matrix_path)])

    def test_duplicate_timepoint_inside_course_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            soft_path, mapping_path, matrix_path = self._fixture(Path(tmp))
            text = soft_path.read_text(encoding="utf-8")
            text = text.replace("timepoint: ZT6", "timepoint: ZT2", 1)
            soft_path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "six unique timepoints"):
                audit_geo_sample_map(soft_path, mapping_path, [("LNv", matrix_path)])


if __name__ == "__main__":
    unittest.main()
