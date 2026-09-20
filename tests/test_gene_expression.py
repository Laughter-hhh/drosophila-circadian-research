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


if __name__ == "__main__":
    unittest.main()
