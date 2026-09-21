import sys
import tempfile
import unittest
import zipfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_published_cycle_candidates import (  # noqa: E402
    TARGET_SHEETS,
    build_output_rows,
    read_published_cyclers,
)

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _column_name(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _cell_xml(reference, value):
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"><v>{value}</v></c>'
    return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _sheet_xml(rows):
    serialized = []
    for row_number, values in enumerate(rows, start=1):
        cells = "".join(
            _cell_xml(f"{_column_name(column)}{row_number}", value)
            for column, value in enumerate(values, start=1)
        )
        serialized.append(f'<row r="{row_number}">{cells}</row>')
    return f'<worksheet xmlns="{MAIN_NS}"><sheetData>{"".join(serialized)}</sheetData></worksheet>'


def _record(symbol, cycle_class, f24_value, jtk_value, f24_score=0.7, jtk_p=0.02):
    return {
        "symbol": symbol,
        "cycle_class": cycle_class,
        "f24_value": f24_value,
        "jtk_value": jtk_value,
        "f24_score": f24_score,
        "f24_phase": 6,
        "jtk_p": jtk_p,
        "jtk_phase": 6,
    }


def _write_fixture(path):
    sheet_headers = {
        "LNv_cyclers": [
            "symbol (yellow=HC cycler)", "JTK cycler?", "F24 cycler?", "cycling?",
            "F24 score", "F24 phase", "JTK p-value", "JTK phase", "max/min", "average expression",
        ],
        "LNd_cyclers": [
            "symbol (yellow=HC cycler)", "F24 cycler?", "JTK cycler?", "cycling?",
            "F24 score", "F24 phase", "JTK p-value", "JTK phase", "max/min", "average expression",
        ],
        "DN1_cyclers": [
            "symbol (HC cyclers in yellow)", "F24-cycler", "JTK cycler ", "cycling?",
            "F24 score", "F24 phase", "JTK p-value", "JTK phase", "max/min (if min is 0)", "average all tp",
        ],
    }
    records = {
        "LNv_cyclers": [
            _record("Shal", "HC-cycler", "F24 cycler", "JTK cycler"),
            _record("Shal", "LC-cycler", "F24 cycler", False, jtk_p=0.1),
        ],
        "LNd_cyclers": [_record("Sh", "LC-cycler", "F24 cycler", False, jtk_p=0.1)],
        "DN1_cyclers": [_record("Shaw", "LC-cycler", "F24 cycler", False, jtk_p=0.1)],
    }
    workbook = (
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{DOC_REL_NS}"><sheets>'
        + "".join(
            f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
            for index, name in enumerate(TARGET_SHEETS, start=1)
        )
        + "</sheets></workbook>"
    )
    relationships = (
        f'<Relationships xmlns="{PKG_REL_NS}">'
        + "".join(
            f'<Relationship Id="rId{index}" Target="worksheets/sheet{index}.xml" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
            for index in range(1, 4)
        )
        + "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        for index, sheet_name in enumerate(TARGET_SHEETS, start=1):
            header = sheet_headers[sheet_name]
            rows = [header]
            for record in records[sheet_name]:
                values = []
                for name in header:
                    normalized = name.lower().replace("?", "").replace("-", " ").strip()
                    if normalized.startswith("symbol"):
                        values.append(record["symbol"])
                    elif normalized.startswith("f24 cycler"):
                        values.append(record["f24_value"])
                    elif normalized.startswith("jtk cycler"):
                        values.append(record["jtk_value"])
                    elif normalized == "cycling":
                        values.append(record["cycle_class"])
                    elif normalized == "f24 score":
                        values.append(record["f24_score"])
                    elif normalized == "f24 phase":
                        values.append(record["f24_phase"])
                    elif normalized == "jtk p value":
                        values.append(record["jtk_p"])
                    elif normalized == "jtk phase":
                        values.append(record["jtk_phase"])
                    elif normalized.startswith("max/min"):
                        values.append(3.0)
                    else:
                        values.append(20.0)
                rows.append(values)
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))


class PublishedCycleCandidateAuditTests(unittest.TestCase):
    def test_sheet_specific_header_order_and_exact_symbol_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            workbook = Path(tmp) / "published.xlsx"
            _write_fixture(workbook)
            candidates = {"Sh", "Shal", "Shaw"}
            matches, qc = read_published_cyclers(workbook, candidates)
            rows = build_output_rows(["Sh", "Shal", "Shaw"], matches)

        self.assertEqual(len(qc), 3)
        self.assertTrue(all(item["flag_columns_resolved_by_header"] for item in qc))
        self.assertEqual(qc[0]["paper_reported_HC_n"], 249)
        self.assertFalse(qc[0]["supplement_HC_count_matches_paper_text"])
        lnv = matches["LNv_cyclers"][0]
        self.assertEqual((lnv["candidate_symbol"], lnv["published_cycle_class"]), ("Shal", "HC"))
        self.assertEqual(len(matches["LNv_cyclers"]), 2)
        self.assertTrue(lnv["author_F24_flag"])
        self.assertTrue(lnv["author_JTK_flag"])
        lnd = matches["LNd_cyclers"][0]
        self.assertEqual((lnd["candidate_symbol"], lnd["published_cycle_class"]), ("Sh", "LC"))
        self.assertTrue(lnd["author_F24_flag"])
        self.assertFalse(lnd["author_JTK_flag"])
        dn1 = matches["DN1_cyclers"][0]
        self.assertEqual((dn1["candidate_symbol"], dn1["published_cycle_class"]), ("Shaw", "LC"))
        self.assertEqual(len(rows), 10)
        sh_in_lnv = next(row for row in rows if row["candidate_symbol"] == "Sh" and row["source_sheet"] == "LNv_cyclers")
        self.assertEqual(sh_in_lnv["published_cycle_class"], "not_listed")
        self.assertEqual(sh_in_lnv["source_list_status"], "not_listed_in_published_cycler_supplement")

    def test_header_resolution_rejects_ambiguous_rhythm_columns(self):
        from scripts.audit_published_cycle_candidates import _header_indexes

        headers = {
            1: "symbol", 2: "F24 score", 3: "F24 phase", 4: "JTK p-value",
            5: "JTK phase", 6: "F24 cycler", 7: "F24 cycler", 8: "cycling?",
            9: "max/min", 10: "average expression",
        }
        with self.assertRaisesRegex(ValueError, "expected one F24 cycler flag"):
            _header_indexes(headers)


if __name__ == "__main__":
    unittest.main()
