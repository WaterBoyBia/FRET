"""Regression checks for table import and aligned chart data."""

from datetime import datetime
from pathlib import Path
import math
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from table_data import TableError, as_number, load_table, make_table, prepare_series, sheet_names


class TableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[1] / "output").mkdir(exist_ok=True)

    def test_duplicate_and_empty_headers(self):
        table = make_table([["X", "A", "A", None, None], [1, 2, 3, 4, None]])
        self.assertEqual(table.headers, ["X", "A", "A (2)", "列 4"])

    def test_ragged_and_empty_rows(self):
        table = make_table([["X", "Y"], [1, 2], [None, ""], [3]])
        self.assertEqual(table.rows, [(1, 2), (3, None)])

    def test_empty_table(self):
        for values in ([], [["X", "Y"]], [[None], [None]]):
            with self.assertRaises(TableError):
                make_table(values)

    def test_finite_numbers_only(self):
        for value in (None, "", "NaN", "inf", True, datetime(2026, 1, 1), "bad"):
            self.assertIsNone(as_number(value))
        self.assertEqual(as_number(" 1.2e3 "), 1200)

    def test_alignment_and_gaps(self):
        table = make_table([["X", "Y"], [1, 10], ["bad", 20], [3, ""], [4, 40]])
        x, lines, kind, dropped, missing = prepare_series(table, 0, [1])
        self.assertEqual(x, [1, 3, 4])
        self.assertEqual((kind, dropped, missing), ("number", 1, 1))
        self.assertTrue(math.isnan(lines[0][1]))
        self.assertEqual(lines[0][2], 40)

    def test_row_index(self):
        table = make_table([["A"], [8], [9]])
        self.assertEqual(prepare_series(table, None, [0])[:2], ([1, 2], [[8, 9]]))

    def test_dates_and_categories(self):
        dates = [datetime(2026, 1, 1), datetime(2026, 1, 2)]
        table = make_table([["Date", "Y"], [dates[0], 1], [dates[1], 2]])
        self.assertEqual(prepare_series(table, 0, [1])[2], "date")
        table = make_table([["Sample", "Y"], ["A", 1], ["A", 2]])
        self.assertEqual(prepare_series(table, 0, [1])[:3], (["A", "A"], [[1, 2]], "category"))

    def test_no_valid_series(self):
        table = make_table([["X", "Y"], [1, "abc"]])
        with self.assertRaises(TableError):
            prepare_series(table, 0, [1])
        with self.assertRaises(TableError):
            prepare_series(table, 0, [])

    def test_csv_encodings_and_quoted_newlines(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "output") as directory:
            for encoding in ("utf-8-sig", "gb18030", "utf-16"):
                path = Path(directory) / f"{encoding}.csv"
                path.write_bytes('波长,"曲线\n名称"\n560,12\n570,13\n'.encode(encoding))
                table = load_table(path)
                self.assertEqual(table.headers, ["波长", "曲线\n名称"])
                self.assertEqual(len(table.rows), 2)

    def test_tsv_and_semicolon(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "output") as directory:
            for delimiter, suffix in (("\t", ".tsv"), (";", ".csv")):
                path = Path(directory) / f"sample{suffix}"
                path.write_text(f"X{delimiter}Y\n1{delimiter}2\n", encoding="utf-8")
                self.assertEqual(load_table(path).headers, ["X", "Y"])

    def test_excel_sheets(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "output") as directory:
            path = Path(directory) / "sample.xlsx"
            book = Workbook()
            book.active.title = "光谱"
            book.active.append(["波长", "A"])
            book.active.append([560, 12])
            book.create_sheet("Second").append(["X", "B"])
            book["Second"].append([1, 7])
            book.save(path)
            book.close()
            self.assertEqual(sheet_names(path), ["光谱", "Second"])
            self.assertEqual(load_table(path, "Second").rows, [(1, 7)])


if __name__ == "__main__":
    unittest.main()
