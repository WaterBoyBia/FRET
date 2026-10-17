# FRET 表格折线图工具

桌面绘图工具，导入表格后可逐条修改折线的图例名称，实时预览并导出图片。不会修改原始表格。

## 启动方式

- 源码运行：在项目目录执行 `conda run --no-capture-output -n donna python src/main.py`，或运行 `start.ps1`。
- 完整程序包：运行 `version/FRET/FRET.exe`，无需安装。分发时复制整个 `version/FRET/` 文件夹，必须保留其中的 `_internal/` 依赖目录，不能只复制 EXE。

程序包面向 Windows 10/11 64 位，包含 Python 和运行依赖，目标电脑无需安装 conda 或 Python。其他操作系统需要分别构建。

## 使用步骤

1. 点击“导入表格”，选择 `.xlsx`、`.xls`、`.csv` 或 `.tsv` 文件。
2. Excel 可选择工作表，第一行为列名，第二行起为数据。CSV 支持 UTF-8、GB18030 和带字节序标记的 UTF-16，自动识别逗号、制表符和分号分隔。
3. 默认第一列作为 X 轴，其余含数值的列作为折线。可切换 X 轴列或选择“按数据行序号”。
4. 在“折线与图例名称”里勾选需要的列，编辑名称即更新图例。每条折线默认分配不同颜色，超过 8 条时自动扩展配色；点击色块可手动换色。留空时使用原始列名，“恢复名称”可恢复原名。
5. 调整图表标题、坐标轴名称、网格、图例、三角点和线宽。每个有效数据点默认显示同色的小三角形，图例同步显示三角形标记；可取消勾选“三角点”隐藏标记。工具栏可缩放、平移、恢复视图；修改数据或设置会重置视图。
6. 点击“导出图像”，选择 PNG（300 DPI）、SVG 或 PDF。导出会按当前设置重新绘制完整数据范围。中文名称会包含在导出图例中。

“原始数据”页最多预览前 200 行，绘图使用全部数据。行顺序保持原样，不自动排序、聚合或插值。数值型 X 轴的空值、非数值和无穷值所在行会跳过；Y 值缺失或无效时显示断点。状态栏显示跳过行数和缺失值数。文本 X 轴按行排列，同名文本也保留独立数据点；Excel 日期单元格支持日期轴，CSV 日期文本按文本标签显示。单个数据点自动显示标记。

请保证 Excel 公式已在 Excel 中计算并保存；程序读取公式的缓存结果，不运行公式。尚未计算的公式可能按缺失值处理。无数值列、未勾选折线或线宽无效时会显示提示并禁用导出。大量数据和大量折线的载入、重绘可能需要等待。

图表中的中文使用宋体（SimSun），英文和数字使用 Times New Roman；同一标题或图例里的中英文按字符选择对应字体。该规则适用于图表预览和 PNG/SVG/PDF 导出，运行电脑需安装这两种字体。

## 项目结构

- `src/main.py`：Tkinter 界面与 matplotlib 绘图。
- `src/table_data.py`：表格读取、数值校验与绘图数据准备。
- `tests/`：导入及数据对齐回归测试。
- `data/`：示例数据。
- `output/`：验证图像及运行结果。
- `version/FRET/`：完整程序文件夹，包含 `FRET.exe` 和运行依赖。
- `version/build/`、`version/temp/`：构建时产生的中间文件，无需分发。

## 验证与打包

所有 Python 活动使用已有的 `donna` 环境，不需要修改环境。

经确认后执行下列打包命令，生成包含最新配色、宋体/Times New Roman 字体规则及三角形数据点的完整程序文件夹。不生成安装程序或分发用压缩包；运行依赖内部的归档文件属于程序组成部分，需保留。

```powershell
conda run --no-capture-output -n donna python -m unittest discover -s tests -v
conda run --no-capture-output -n donna python src/main.py "data/20261012-fret-光谱-2-2-1.xlsx" --smoke-test output/source-check
powershell -ExecutionPolicy Bypass -File build.ps1
```

构建脚本先运行测试，再由 donna 中的 PyInstaller 收集运行依赖（显式包含 SVG/PDF 导出后端），将完整程序生成在 `version/FRET/`，并在移除 conda/Python 搜索路径后测试独立 EXE。构建不调用 Inno Setup。临时目录和构建缓存位于项目内，程序界面使用中文。

打包验证包含本机独立 EXE 的真实 Excel 导入、图例改名、图形绘制和三种导出。尚未在干净的 Windows 虚拟机或其他物理电脑上验收，因此不承诺所有硬件与系统配置均兼容。
