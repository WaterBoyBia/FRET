"""FRET desktop line chart application."""

import argparse
import colorsys
from pathlib import Path
import sys
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from table_data import TableError, load_table, prepare_series, sheet_names


COLORS = ["#2563EB", "#E76F51", "#10A37F", "#9254DE", "#E6A000", "#D94C93", "#0891B2", "#64748B"]
BG = "#F1F5F9"


def series_colors(count):
    """Extend the default palette without cycling through existing colors."""
    palette = COLORS[:count]
    used = set(palette)
    index = 0
    while len(palette) < count:
        hue = (0.05 + index * 0.618033988749895) % 1
        saturation = (0.68, 0.86, 0.56)[index % 3]
        brightness = (0.78, 0.62, 0.9)[(index // 3) % 3]
        channels = colorsys.hsv_to_rgb(hue, saturation, brightness)
        color = "#" + "".join(f"{round(channel * 255):02X}" for channel in channels)
        if color not in used:
            used.add(color)
            palette.append(color)
        index += 1
    return palette


def configure_fonts():
    # Matplotlib selects the first font containing each glyph: Latin from
    # Times New Roman, then Chinese from SimSun.
    families = ["Times New Roman", "SimSun"]
    matplotlib.rcParams.update({"font.family": families, "font.serif": families,
                               "axes.unicode_minus": False, "font.size": 10,
                               "mathtext.fontset": "custom", "mathtext.rm": "Times New Roman",
                               "mathtext.it": "Times New Roman:italic",
                               "mathtext.bf": "Times New Roman:bold",
                               "svg.fonttype": "path", "pdf.fonttype": 42})


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FRET · 表格折线图")
        self.geometry("1380x900")
        self.minsize(1100, 740)
        self.configure(bg=BG)
        self.table = None
        self.path = None
        self.series_controls = {}
        self.pending_draw = None
        self.loading = False
        self.plot_valid = False
        self.chart_title = tk.StringVar(value="光谱折线图")
        self.x_label = tk.StringVar()
        self.y_label = tk.StringVar(value="强度")
        self.x_choice = tk.StringVar()
        self.sheet_choice = tk.StringVar()
        self.show_grid = tk.BooleanVar(value=True)
        self.show_legend = tk.BooleanVar(value=True)
        self.show_markers = tk.BooleanVar(value=True)
        self.line_width = tk.StringVar(value="2.0")
        self.status = tk.StringVar(value="导入表格开始绘图 · 支持 Excel / CSV / TSV")
        self._style()
        self._layout()
        for variable in (self.chart_title, self.x_label, self.y_label, self.line_width):
            variable.trace_add("write", lambda *_: self.schedule_draw())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _style(self):
        self.option_add("*Font", ("Microsoft YaHei UI", 10))
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground="#334155")
        style.configure("TCheckbutton", background=BG, foreground="#334155")
        style.configure("TLabelframe", background=BG, bordercolor="#DCE3EC")
        style.configure("TLabelframe.Label", background=BG, foreground="#0F172A", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TButton", padding=(10, 7))
        style.configure("Primary.TButton", background="#2563EB", foreground="white")
        style.map("Primary.TButton", background=[("active", "#1D4ED8")])
        style.configure("Treeview", rowheight=27, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 9))

    def _layout(self):
        header = tk.Frame(self, bg="#10233F", height=86)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="FRET", font=("Segoe UI", 25, "bold"), fg="white", bg="#10233F").pack(side="left", padx=(24, 14))
        tk.Label(header, text="表格折线图  /  从数据到清晰表达", fg="#C7D6ED", bg="#10233F", font=("Microsoft YaHei UI", 12)).pack(side="left")
        ttk.Button(header, text="导入表格", style="Primary.TButton", command=self.import_file).pack(side="right", padx=(10, 24))
        self.export_button = ttk.Button(header, text="导出图像", command=self.export, state="disabled")
        self.export_button.pack(side="right")
        body = ttk.Frame(self, padding=(18, 16))
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body, width=370)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        source = ttk.LabelFrame(left, text="01  数据来源", padding=12)
        source.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        source.columnconfigure(1, weight=1)
        self.file_label = ttk.Label(source, text="尚未导入文件", wraplength=320)
        self.file_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(source, text="工作表").grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.sheet_box = ttk.Combobox(source, textvariable=self.sheet_choice, state="disabled", width=23)
        self.sheet_box.grid(row=1, column=1, sticky="ew")
        self.sheet_box.bind("<<ComboboxSelected>>", self.change_sheet)
        ttk.Label(source, text="X 轴列").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.x_box = ttk.Combobox(source, textvariable=self.x_choice, state="disabled", width=23)
        self.x_box.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        self.x_box.bind("<<ComboboxSelected>>", self.change_x)
        self.data_info = ttk.Label(source, text="第一行为列名，第二行起为数据。", wraplength=320)
        self.data_info.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))

        series = ttk.LabelFrame(left, text="02  折线与图例名称", padding=10)
        series.grid(row=1, column=0, sticky="nsew", pady=(0, 14))
        ttk.Label(series, text="勾选绘制 · 点击色块换色 · 输入新名称", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(0, 8))
        actions = ttk.Frame(series)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="全选", command=lambda: self.select_all(True)).pack(side="left")
        ttk.Button(actions, text="全不选", command=lambda: self.select_all(False)).pack(side="left", padx=6)
        ttk.Button(actions, text="恢复名称", command=self.reset_names).pack(side="right")
        viewport = ttk.Frame(series)
        viewport.pack(fill="both", expand=True)
        self.series_canvas = tk.Canvas(viewport, bg=BG, highlightthickness=0, width=300)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self.series_canvas.yview)
        self.series_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.series_canvas.pack(side="left", fill="both", expand=True)
        self.series_frame = ttk.Frame(self.series_canvas)
        window = self.series_canvas.create_window((0, 0), window=self.series_frame, anchor="nw")
        self.series_frame.bind("<Configure>", lambda _: self.series_canvas.configure(scrollregion=self.series_canvas.bbox("all")))
        self.series_canvas.bind("<Configure>", lambda event: self.series_canvas.itemconfigure(window, width=event.width))
        self.series_canvas.bind("<MouseWheel>", lambda event: self.series_canvas.yview_scroll(-int(event.delta / 120), "units"))
        ttk.Label(self.series_frame, text="导入后将在此列出可绘制的数据列。", wraplength=300).pack(anchor="w", pady=16)

        settings = ttk.LabelFrame(left, text="03  图表设置", padding=12)
        settings.grid(row=2, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((("标题", self.chart_title), ("X 轴名称", self.x_label), ("Y 轴名称", self.y_label))):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            ttk.Entry(settings, textvariable=variable, width=22).grid(row=row, column=1, sticky="ew", pady=4)
        options = ttk.Frame(settings)
        options.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for label, variable in (("网格", self.show_grid), ("图例", self.show_legend), ("三角点", self.show_markers)):
            ttk.Checkbutton(options, text=label, variable=variable, command=self.schedule_draw).pack(side="left", padx=(0, 8))
        ttk.Label(settings, text="线宽").grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Spinbox(settings, textvariable=self.line_width, from_=0.5, to=8, increment=0.5, width=8).grid(row=4, column=1, sticky="w", pady=(10, 0))

        tabs = ttk.Notebook(body)
        tabs.grid(row=0, column=1, sticky="nsew")
        plot_tab, data_tab = ttk.Frame(tabs), ttk.Frame(tabs, padding=12)
        tabs.add(plot_tab, text="图表预览")
        tabs.add(data_tab, text="原始数据")
        self.figure = Figure(figsize=(8, 6), dpi=100, layout="constrained", facecolor="white")
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_tab)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar_frame = ttk.Frame(plot_tab)
        toolbar_frame.pack(fill="x")
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self.toolbar.pack(side="left", fill="x")
        ttk.Label(plot_tab, text="工具栏支持缩放和平移；修改左侧设置后自动更新。", padding=(12, 8)).pack(fill="x")
        ttk.Label(data_tab, text="原始数据预览（前 200 行）；图例名称修改不影响原表。", padding=(0, 0, 0, 10)).pack(anchor="w")
        tree_frame = ttk.Frame(data_tab)
        tree_frame.pack(fill="both", expand=True)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")
        xbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        ybar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xbar.grid(row=1, column=0, sticky="ew")
        ybar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        ttk.Label(self, textvariable=self.status, padding=(24, 9), background="#E2E8F0").pack(fill="x")
        self.draw_plot()

    def import_file(self):
        path = filedialog.askopenfilename(title="选择表格文件", filetypes=[("表格文件", "*.xlsx *.xls *.csv *.tsv *.txt"), ("Excel", "*.xlsx *.xls"), ("CSV / TSV", "*.csv *.tsv *.txt")])
        if path:
            self.open_path(path)

    def open_path(self, path):
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            sheets = sheet_names(path)
            table = load_table(path, sheets[0] if sheets else None)
        except Exception as error:
            messagebox.showerror("无法导入表格", f"请检查文件格式、读取权限或文件是否损坏。\n\n{error}", parent=self)
            return False
        finally:
            self.configure(cursor="")
        self.path = Path(path)
        self.sheet_box.configure(values=sheets, state="readonly" if sheets else "disabled")
        self.sheet_choice.set(sheets[0] if sheets else "文本表格")
        self.file_label.configure(text=self.path.name)
        self.apply_table(table)
        return True

    def change_sheet(self, _=None):
        try:
            table = load_table(self.path, self.sheet_choice.get())
        except Exception as error:
            messagebox.showerror("无法读取工作表", str(error), parent=self)
            self.sheet_choice.set(self.active_sheet)
            return
        self.apply_table(table)

    def apply_table(self, table):
        self.loading = True
        self.table = table
        self.active_sheet = self.sheet_choice.get()
        self.x_options = ["按数据行序号"] + [f"{i + 1} · {header}" for i, header in enumerate(table.headers)]
        self.x_box.configure(values=self.x_options, state="readonly")
        self.x_choice.set(self.x_options[1])
        self.x_label.set(table.headers[0])
        self.data_info.configure(text=f"{len(table.rows):,} 行数据 · {len(table.headers)} 列 · {len(table.numeric_columns)} 个数值列")
        for child in self.series_frame.winfo_children():
            child.destroy()
        self.series_controls = {}
        numeric_columns = table.numeric_columns
        palette = series_colors(len(numeric_columns))
        for position, column in enumerate(numeric_columns):
            frame = ttk.Frame(self.series_frame, padding=(0, 5))
            frame.pack(fill="x")
            selected = tk.BooleanVar(value=column != 0)
            label = tk.StringVar(value=table.headers[column])
            color = palette[position]
            check = ttk.Checkbutton(frame, variable=selected, command=self.schedule_draw)
            check.pack(side="left")
            button = tk.Button(frame, bg=color, activebackground=color, width=2, relief="flat", command=lambda c=column: self.choose_color(c))
            button.pack(side="left", padx=(0, 8))
            entry = ttk.Entry(frame, textvariable=label)
            entry.pack(side="left", fill="x", expand=True)
            ttk.Label(self.series_frame, text=f"来源：{table.headers[column]}", font=("Microsoft YaHei UI", 8), foreground="#64748B").pack(anchor="w", padx=27)
            label.trace_add("write", lambda *_: self.schedule_draw())
            self.series_controls[column] = dict(selected=selected, label=label, color=color, button=button, check=check)
        if not self.series_controls:
            ttk.Label(self.series_frame, text="此表没有可用的数值列。", wraplength=300).pack(anchor="w", pady=12)
        self.tree.delete(*self.tree.get_children())
        ids = [str(i) for i in range(len(table.headers))]
        self.tree.configure(columns=ids)
        for column, label in zip(ids, table.headers):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=130, minwidth=80, stretch=False)
        for row in table.rows[:200]:
            self.tree.insert("", "end", values=["" if value is None else str(value) for value in row])
        self.loading = False
        self.change_x()

    def x_column(self):
        return self.x_options.index(self.x_choice.get()) - 1 if self.x_choice.get() != self.x_options[0] else None

    def change_x(self, _=None):
        x_column = self.x_column()
        self.x_label.set(self.table.headers[x_column] if x_column is not None else "数据行序号")
        for column, controls in self.series_controls.items():
            if column == x_column:
                controls["selected"].set(False)
                controls["check"].state(["disabled"])
            else:
                controls["check"].state(["!disabled"])
        self.schedule_draw()

    def select_all(self, selected):
        if self.table:
            for column, controls in self.series_controls.items():
                controls["selected"].set(selected and column != self.x_column())
            self.schedule_draw()

    def reset_names(self):
        for column, controls in self.series_controls.items():
            controls["label"].set(self.table.headers[column])

    def choose_color(self, column):
        controls = self.series_controls[column]
        color = colorchooser.askcolor(color=controls["color"], title="选择折线颜色", parent=self)[1]
        if color:
            controls["color"] = color
            controls["button"].configure(bg=color, activebackground=color)
            self.schedule_draw()

    def schedule_draw(self):
        if self.loading:
            return
        if self.pending_draw:
            self.after_cancel(self.pending_draw)
        self.pending_draw = self.after(250, self.draw_plot)

    def draw_plot(self):
        if self.pending_draw:
            self.after_cancel(self.pending_draw)
        self.pending_draw = None
        self.ax.clear()
        self.plot_valid = False
        self.export_button.configure(state="disabled")
        if self.table is None:
            self.ax.set_axis_off()
            self.ax.text(0.5, 0.56, "让数据成为折线", ha="center", va="center", fontsize=23, color="#10233F", transform=self.ax.transAxes)
            self.ax.text(0.5, 0.45, "导入表格 → 选择数据列 → 自定义名称 → 导出图像", ha="center", color="#64748B", fontsize=11, transform=self.ax.transAxes)
            self.canvas.draw_idle()
            return
        try:
            columns = [column for column, controls in self.series_controls.items() if controls["selected"].get()]
            x_values, series, kind, dropped, missing = prepare_series(self.table, self.x_column(), columns)
            width = float(self.line_width.get())
            if not 0.1 <= width <= 20:
                raise ValueError()
        except (TableError, ValueError) as error:
            message = str(error) or "线宽请输入 0.1 至 20 之间的数字。"
            self.status.set(message)
            self.ax.set_axis_off()
            self.ax.text(0.5, 0.5, message, ha="center", va="center", color="#64748B", wrap=True, transform=self.ax.transAxes)
            self.canvas.draw_idle()
            return
        self.ax.set_axis_on()
        for column, values in zip(columns, series):
            controls = self.series_controls[column]
            name = controls["label"].get().strip() or self.table.headers[column]
            self.ax.plot(list(range(len(x_values))) if kind == "category" else x_values, values,
                         label=name, color=controls["color"], linewidth=width,
                         marker="^" if self.show_markers.get() or len(x_values) == 1 else None,
                         markersize=4, markevery=None)
        if kind == "category":
            step = max(1, (len(x_values) + 11) // 12)
            ticks = list(range(0, len(x_values), step))
            self.ax.set_xticks(ticks, [x_values[i] for i in ticks], rotation=25, ha="right")
        elif kind == "number":
            self.ax.xaxis.set_major_locator(MaxNLocator(nbins=8))
        self.ax.set_title(self.chart_title.get(), loc="left", fontsize=16, fontweight="bold", pad=18, color="#10233F")
        self.ax.set_xlabel(self.x_label.get(), labelpad=10)
        self.ax.set_ylabel(self.y_label.get(), labelpad=10)
        self.ax.spines[["top", "right"]].set_visible(False)
        self.ax.spines[["bottom", "left"]].set_color("#CBD5E1")
        self.ax.tick_params(colors="#475569")
        self.ax.grid(self.show_grid.get(), color="#E2E8F0", linewidth=0.8) if self.show_grid.get() else self.ax.grid(False)
        self.ax.set_axisbelow(True)
        if self.show_legend.get():
            handles = list(self.ax.lines)
            self.ax.legend(handles=handles, labels=[handle.get_label() for handle in handles],
                           loc="best", frameon=False, fontsize=9, numpoints=1,
                           ncols=max(1, (len(columns) + 9) // 10))
        self.ax.margins(x=0.03)
        self.toolbar.update()
        self.plot_valid = True
        self.export_button.configure(state="normal")
        self.status.set(f"已绘制 {len(columns)} 条折线 · {len(x_values):,} 个数据行 · 跳过 {dropped} 行无效 X 值 · {missing} 个缺失 Y 值显示为断点")
        self.canvas.draw_idle()

    def export(self):
        self.draw_plot()
        if not self.plot_valid:
            return
        path = filedialog.asksaveasfilename(title="导出图像", defaultextension=".png", initialfile=f"{self.path.stem}_折线图.png", filetypes=[("PNG（300 DPI）", "*.png"), ("SVG 矢量图", "*.svg"), ("PDF 矢量图", "*.pdf")])
        if path:
            try:
                self.figure.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
                self.status.set(f"图像已导出：{path}")
            except Exception as error:
                messagebox.showerror("导出失败", str(error), parent=self)

    def close(self):
        if self.pending_draw:
            self.after_cancel(self.pending_draw)
        self.update_idletasks()
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="FRET line chart desktop tool")
    parser.add_argument("file", nargs="?")
    parser.add_argument("--smoke-test", metavar="OUTPUT_DIR")
    args = parser.parse_args()
    configure_fonts()
    app = App()
    if args.smoke_test:
        output = Path(args.smoke_test)
        output.mkdir(parents=True, exist_ok=True)
        if not args.file:
            raise ValueError("A table path is required for the smoke test")
        if not app.open_path(args.file):
            raise RuntimeError("Table import failed")
        selected = [controls for controls in app.series_controls.values() if controls["selected"].get()]
        selected[0]["label"].set("自定义折线 / Custom series")
        app.draw_plot()
        app.update()
        assert app.plot_valid
        assert app.ax.get_legend().get_texts()[0].get_text() == "自定义折线 / Custom series"
        for suffix in ("png", "svg", "pdf"):
            app.figure.savefig(output / f"smoke_chart.{suffix}", dpi=150)
        (output / "smoke_result.txt").write_text(f"PASS\nFrozen: {getattr(sys, 'frozen', False)}\nSeries: {len(selected)}\n{app.status.get()}\n", encoding="utf-8")
        app.close()
    else:
        if args.file:
            app.open_path(args.file)
        app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if "--smoke-test" in sys.argv:
            import traceback
            destination = Path(sys.argv[sys.argv.index("--smoke-test") + 1])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "smoke_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1)
        raise
