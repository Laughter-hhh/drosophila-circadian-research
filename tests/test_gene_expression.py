import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.extract_gene_expression import summarize


class GeneExpressionTests(unittest.TestCase):
    def test_probe_mapping_and_descriptive_group_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            annotation = root / "annotation.txt"
            annotation.write_text(
                "^Annotation\nID\tGene title\tGene symbol\n"
                "p1\tShaker\tSh\n"
                "p2\tShaker\tSh\n"
                "p3\tpara\tpara\n",
                encoding="utf-8",
            )
            matrix = root / "matrix.txt"
            matrix.write_text(
                "!series_matrix_table_begin\n"
                '"ID_REF"\t"S1"\t"S2"\n'
                '"p1"\t1\t3\n'
                '"p2"\t2\t4\n'
                '"p3"\t5\t6\n'
                "!series_matrix_table_end\n",
                encoding="utf-8",
            )
            metadata = root / "metadata.csv"
            with metadata.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["sample_id", "characteristics_json"])
                writer.writeheader()
                writer.writerow({"sample_id": "S1", "characteristics_json": json.dumps({"cell type": "s-LNv", "time": "ZT0", "background": "yw"})})
                writer.writerow({"sample_id": "S2", "characteristics_json": json.dumps({"cell type": "s-LNv", "time": "ZT12", "background": "yw"})})
            candidates = root / "candidates.csv"
            candidates.write_text("gene_symbol\nSh\npara\nmissing\n", encoding="utf-8")

            summary, samples = summarize(matrix, annotation, metadata, candidates)

        sh_samples = [row for row in samples if row["gene_symbol"] == "Sh"]
        self.assertEqual([row["expression"] for row in sh_samples], [1.5, 3.5])
        sh_summary = [row for row in summary if row["gene_symbol"] == "Sh"]
        self.assertEqual(len(sh_summary), 2)
        self.assertEqual(sh_summary[0]["status"], "descriptive_probe_mapped_summary")
        missing = [row for row in summary if row["gene_symbol"] == "missing"]
        self.assertEqual(missing[0]["status"], "not_found_or_no_numeric_values")


    def test_different_developmental_stages_are_not_collapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            annotation = root / "annotation.txt"
            annotation.write_text("ID\tGene symbol\np1\tSh\n", encoding="utf-8")
            matrix = root / "matrix.txt"
            matrix.write_text(
                "!series_matrix_table_begin\n"
                '"ID_REF"\t"S_larva"\t"S_adult"\n'
                '"p1"\t1\t9\n'
                "!series_matrix_table_end\n",
                encoding="utf-8",
            )
            metadata = root / "metadata.csv"
            with metadata.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["sample_id", "characteristics_json"])
                writer.writeheader()
                writer.writerow({"sample_id": "S_larva", "characteristics_json": json.dumps({"cell type": "Elav-GAL4", "developmental stage": "larva"})})
                writer.writerow({"sample_id": "S_adult", "characteristics_json": json.dumps({"cell_type": "Elav-GAL4", "stage": "adult"})})
            candidates = root / "candidates.csv"
            candidates.write_text("gene_symbol\nSh\n", encoding="utf-8")

            summary, samples = summarize(matrix, annotation, metadata, candidates)

        self.assertEqual(len(summary), 2)
        self.assertEqual({row["developmental_stage"] for row in summary}, {"larva", "adult"})
        self.assertEqual({row["n_samples"] for row in summary}, {1})
        self.assertEqual({row["developmental_stage"] for row in samples}, {"larva", "adult"})

    def test_gse17803_retains_developmental_stage_and_unknown_time(self):
        public_data = Path(__file__).resolve().parents[1] / "validation" / "public-data"
        summary, samples = summarize(
            public_data / "GSE17803_series_matrix.txt.gz",
            public_data / "GPL1322.annot.gz",
            public_data / "GSE17803_parsed_metadata.csv",
            public_data / "GSE22308_candidate_genes.csv",
        )

        sh_elav = [
            row for row in summary
            if row.get("gene_symbol") == "Sh" and row.get("cell_type") == "Elav-GAL4"
        ]
        self.assertEqual(
            {(row["developmental_stage"], row["n_samples"]) for row in sh_elav},
            {("adult", 3), ("larva", 3)},
        )
        small_pdf = [
            row for row in summary
            if row.get("gene_symbol") == "Sh" and row.get("cell_type") == "small Pdf-GAL4"
        ]
        self.assertEqual(len(small_pdf), 1)
        self.assertEqual((small_pdf[0]["developmental_stage"], small_pdf[0]["n_samples"]), ("adult", 2))
        self.assertEqual({row["time"] for row in samples}, {"unknown"})

    def test_sex_and_gender_aliases_are_preserved_and_stratified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            annotation = root / "annotation.txt"
            annotation.write_text("ID\tGene symbol\np1\tSh\n", encoding="utf-8")
            matrix = root / "matrix.txt"
            matrix.write_text(
                "!series_matrix_table_begin\n"
                '"ID_REF"\t"S_female"\t"S_male"\n'
                '"p1"\t1\t9\n'
                "!series_matrix_table_end\n",
                encoding="utf-8",
            )
            metadata = root / "metadata.csv"
            with metadata.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["sample_id", "characteristics_json"])
                writer.writeheader()
                writer.writerow({"sample_id": "S_female", "characteristics_json": json.dumps({"cell type": "LNd", "time": "ZT0", "background": "yw", "sex": "female"})})
                writer.writerow({"sample_id": "S_male", "characteristics_json": json.dumps({"cell type": "LNd", "time": "ZT0", "background": "yw", "gender": "male"})})
            candidates = root / "candidates.csv"
            candidates.write_text("gene_symbol\nSh\n", encoding="utf-8")

            summary, samples = summarize(matrix, annotation, metadata, candidates)

        self.assertEqual({row["sex"] for row in samples}, {"female", "male"})
        self.assertEqual({(row["sex"], row["n_samples"]) for row in summary}, {("female", 1), ("male", 1)})

    def test_gse22308_retains_mixed_and_male_gender_context(self):
        public_data = Path(__file__).resolve().parents[1] / "validation" / "public-data"
        summary, samples = summarize(
            public_data / "GSE22308_series_matrix.txt.gz",
            public_data / "GPL1322.annot.gz",
            public_data / "GSE22308_parsed_metadata.csv",
            public_data / "GSE22308_candidate_genes.csv",
        )

        large_pdf = [
            row for row in samples
            if row.get("gene_symbol") == "Sh" and row.get("cell_type") == "large PDF circadian neurons"
        ]
        self.assertEqual(
            {row["sex"] for row in large_pdf if row["background"] == "yw"},
            {"male and female"},
        )
        self.assertEqual(
            {row["sex"] for row in large_pdf if row["background"] == "per01"},
            {"male"},
        )
        self.assertEqual(
            {(row["background"], row["sex"]) for row in summary if row.get("gene_symbol") == "Sh" and row.get("cell_type") == "large PDF circadian neurons"},
            {("yw", "male and female"), ("per01", "male")},
        )

if __name__ == "__main__":
    unittest.main()
