"""Integration checks for renaming, selections and rendered chart state."""

from pathlib import Path
from io import StringIO
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from main import App, configure_fonts
from table_data import make_table


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_fonts()

    def setUp(self):
        self.app = App()
        self.app.apply_table(make_table([["X", "A", "B"], [1, 2, 3], [2, 4, 6]]))
        self.app.draw_plot()

    def tearDown(self):
        self.app.close()

    def legend_labels(self):
        return [text.get_text() for text in self.app.ax.get_legend().get_texts()]

    def test_rename_and_restore(self):
        self.app.series_controls[1]["label"].set("供体 / Donor")
        self.app.series_controls[2]["label"].set("_acceptor")
        self.app.draw_plot()
        self.assertEqual(self.legend_labels(), ["供体 / Donor", "_acceptor"])
        self.app.series_controls[1]["label"].set("   ")
        self.app.draw_plot()
        self.assertEqual(self.legend_labels()[0], "A")
        self.app.reset_names()
        self.app.draw_plot()
        self.assertEqual(self.legend_labels(), ["A", "B"])
        self.assertEqual(self.app.table.headers, ["X", "A", "B"])

    def test_selection_and_x_axis(self):
        self.app.select_all(False)
        self.app.draw_plot()
        self.assertFalse(self.app.plot_valid)
        self.assertTrue(self.app.export_button.instate(["disabled"]))
        self.app.x_choice.set(self.app.x_options[2])
        self.app.change_x()
        self.app.select_all(True)
        self.app.draw_plot()
        self.assertTrue(self.app.plot_valid)
        self.assertFalse(self.app.series_controls[1]["selected"].get())
        self.assertEqual(list(self.app.ax.lines[0].get_xdata()), [2, 4])
        self.assertEqual(len(self.app.ax.lines), 2)

    def test_invalid_width_and_legend_toggle(self):
        self.app.line_width.set("nan")
        self.app.draw_plot()
        self.assertFalse(self.app.plot_valid)
        self.app.line_width.set("2.5")
        self.app.show_legend.set(False)
        self.app.draw_plot()
        self.assertTrue(self.app.plot_valid)
        self.assertIsNone(self.app.ax.get_legend())

    def test_category_positions_and_single_point(self):
        self.app.apply_table(make_table([["Group", "Y"], ["A", 1], ["A", 2]]))
        self.app.draw_plot()
        self.assertEqual(list(self.app.ax.lines[0].get_xdata()), [0, 1])
        self.app.apply_table(make_table([["X", "Y"], [1, 2]]))
        self.app.draw_plot()
        self.assertEqual(self.app.ax.lines[0].get_marker(), "^")

    def test_triangle_markers_match_legend(self):
        self.assertTrue(self.app.show_markers.get())
        for line in [*self.app.ax.lines, *self.app.ax.get_legend().get_lines()]:
            self.assertEqual(line.get_marker(), "^")
            self.assertEqual(line.get_markersize(), 4)
        self.assertTrue(all(line.get_markevery() is None for line in self.app.ax.lines))
        self.app.show_markers.set(False)
        self.app.draw_plot()
        self.assertTrue(all(line.get_marker() == "None" for line in self.app.ax.lines))

    def test_mixed_language_fonts_in_export(self):
        self.app.chart_title.set("波长 Spectrum")
        self.app.y_label.set("强度 Intensity")
        self.app.draw_plot()
        output = StringIO()
        self.app.figure.savefig(output, format="svg")
        svg = output.getvalue()
        self.assertIn("TimesNewRomanPSMT-", svg)
        self.assertIn("SimSun-", svg)

    def test_layout_has_visible_controls(self):
        self.app.update()
        self.assertGreater(self.app.series_canvas.winfo_height(), 100)
        self.assertGreater(self.app.canvas.get_tk_widget().winfo_width(), 500)
        self.assertEqual(len(self.app.tree.get_children()), 2)

    def test_many_series_keep_distinct_colors(self):
        headers = ["X"] + [f"Series {i}" for i in range(1, 25)]
        self.app.apply_table(make_table([headers, list(range(25)), list(range(1, 26))]))
        self.app.draw_plot()
        colors = [line.get_color() for line in self.app.ax.lines]
        self.assertEqual(len(colors), 24)
        self.assertEqual(len(set(colors)), 24)
        legend_colors = [line.get_color() for line in self.app.ax.get_legend().get_lines()]
        self.assertEqual(legend_colors, colors)
        self.app.series_controls[10]["label"].set("Renamed series")
        self.app.series_controls[5]["selected"].set(False)
        self.app.draw_plot()
        self.assertEqual([line.get_color() for line in self.app.ax.lines], colors[:4] + colors[5:])


if __name__ == "__main__":
    unittest.main()
