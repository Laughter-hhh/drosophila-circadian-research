import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_literature_panel_inventory import REQUIRED_COLUMNS, validate


def _row(panel_id="Fig. 1A", image_status="linked_not_inspected", caption_status="available", source="https://example.org/article#Fig1"):
    return {
        "panel_id": panel_id,
        "image_status": image_status,
        "caption_status": caption_status,
        "source/version/page/direct link": f"Version of record, Fig. 1: {source}",
        "caption-supported labels, groups and readout": "Genotype groups and locomotor readout are stated in the caption.",
        "visual-only unknown/unavailable": "Exact plotted points and axis ticks were not visually inspected.",
        "n and experimental unit (or unknown)": "n and fly-level unit are not stated in the caption; unknown.",
        "interpretation/caveat": "Caption-limited interpretation; do not infer artwork details.",
    }


def _markdown(*rows):
    head = "| " + " | ".join(REQUIRED_COLUMNS) + " |"
    rule = "| " + " | ".join("---" for _ in REQUIRED_COLUMNS) + " |"
    body = ["| " + " | ".join(row[column] for column in REQUIRED_COLUMNS) + " |" for row in rows]
    return "\n".join([head, rule, *body]) + "\n"


class LiteraturePanelInventoryTests(unittest.TestCase):
    def _validate_text(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(text)
            path = Path(handle.name)
        try:
            return validate(path)
        finally:
            path.unlink(missing_ok=True)

    def test_real_forwardtest_inventory_passes(self):
        path = ROOT / "validation" / "iteration-20260921-panel-status-forwardtest.md"
        result = validate(path)
        self.assertEqual(result["status"], "verified_literature_panel_inventory")
        self.assertEqual(result["n_rows"], 32)
        self.assertEqual(result["n_unique_panel_ids"], 32)

    def test_complete_inventory_passes(self):
        result = self._validate_text(_markdown(_row()))
        self.assertEqual(result["status"], "verified_literature_panel_inventory")
        self.assertEqual(result["n_rows"], 1)

    def test_figure_level_image_status_is_rejected(self):
        result = self._validate_text(_markdown(_row(image_status="caption-limited")))
        self.assertEqual(result["status"], "invalid_literature_panel_inventory")
        self.assertIn("invalid_image_status", {item["type"] for item in result["issues"]})

    def test_caption_status_is_checked_separately(self):
        result = self._validate_text(_markdown(_row(caption_status="image-verified")))
        self.assertIn("invalid_caption_status", {item["type"] for item in result["issues"]})

    def test_every_panel_requires_a_direct_source_link(self):
        result = self._validate_text(_markdown(_row(source="DOI not supplied")))
        self.assertIn("missing_direct_source_link", {item["type"] for item in result["issues"]})

    def test_duplicate_panel_ids_across_tables_are_rejected(self):
        result = self._validate_text(_markdown(_row()) + "\n" + _markdown(_row()))
        self.assertIn("duplicate_panel_id", {item["type"] for item in result["issues"]})

    def test_inventory_missing_required_columns_is_rejected(self):
        text = "| panel_id | image_status | caption_status |\n|---|---|---|\n| Fig. 1A | inspected | available |\n"
        result = self._validate_text(text)
        self.assertEqual(result["status"], "invalid_literature_panel_inventory")
        self.assertIn("missing_required_columns", {item["type"] for item in result["issues"]})

    def test_no_inventory_table_is_rejected(self):
        result = self._validate_text("# A reading report\n\nNo panel table yet.\n")
        self.assertEqual(result["status"], "invalid_literature_panel_inventory")
        self.assertIn("no_panel_inventory_table", {item["type"] for item in result["issues"]})


if __name__ == "__main__":
    unittest.main()
