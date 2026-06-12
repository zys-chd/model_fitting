# 常见问题

## 拟合相关问题

### Q: 拟合失败，统计树显示"无数据"

**可能原因与解决：**

1. **样本量不足** — 每组至少需要 3 个数据点（三参数模型需 5 个）。检查分组后每组的样本数。
2. **数据含非正值** — Weibull / Exponential / Gamma 等模型要求 x > 0。检查数据是否有 0 或负数。
3. **初始参数不合适** — `curve_fit` 收敛失败。可调整模型文件中 `fit()` 的 `p0` 初始猜测值。
4. **数据跨度过大** — 尝试使用对数坐标轴（绘图控制 → X 轴 → 对数）。

### Q: R² 很低怎么办？

- 换一个分布模型试试（如从 Weibull 换 Lognormal）
- 查看 CDF 图上散点与拟合线的偏离程度，判断是否存在多峰或混合分布
- 使用自动去除离群点功能排除异常值后重新拟合

### Q: 某些分组的数据在图上不显示

- 检查统计树中对应分组的 checkbox 是否被取消（☐ 状态），点击可切换
- 点击列标题 checkbox 可批量切换该列所有分组的显示/隐藏

---

## 界面相关问题

### Q: matplotlib 图表中文显示为方框

已在 `config.py` 中设置：
```python
plt.rcParams['font.family'] = 'Microsoft YaHei'
plt.rcParams['axes.unicode_minus'] = False
```

如果仍出现方框，说明系统缺少微软雅黑字体。解决方法：
- Windows：通常已内置，检查是否被精简版系统移除
- 或者改用其他已安装中文字体，修改 `config.py` 中的 `FONT_FAMILY`

### Q: 菜单栏一级标题字体太小

菜单字体通过 `self.option_add('*Menu.font', menu_font)` 全局设置。如有需要，在 `model_fitting_app.py` 的 `_build_menu` 中调整 `FONT_SIZE + 2` 的偏移量。

### Q: 窗口打开后 matplotlib 工具栏不显示

工具栏依赖 `NavigationToolbar2Tk`，如果创建失败会静默跳过（日志中有 debug 记录）。通常不影响使用，图表仍可通过菜单保存。

---

## PyInstaller 打包问题

### Q: 打包后运行闪退

1. 从命令行运行 exe 查看报错信息：
   ```bash
   dist\分布拟合测试工具.exe
   ```
2. 常见原因：缺少 `--hidden-import`，需要在打包命令中添加：
   ```
   --hidden-import scipy
   --hidden-import PIL
   --hidden-import openpyxl
   ```
3. 检查 `build_test.bat` 是否包含了所有 `--add-data`

### Q: 打包后图标不显示 / 找不到 VERSION 文件

确保打包时通过 `--add-data` 将资源文件复制到 exe 内部：
```
--add-data "model_fitting\VERSION:."
--add-data "model_fitting\model_fitting.ico:."
--add-data "model_fitting\model_fitting.png:."
```

程序通过 `_data_dir()` 在 `sys._MEIPASS` 中查找这些文件。

### Q: 打包后 scipy 报错

scipy 的某些子模块不会被 PyInstaller 自动检测。在打包命令中添加：
```
--hidden-import scipy
--hidden-import scipy.optimize
--hidden-import scipy.stats
```

### Q: 打包文件太大

scipy、numpy、pandas、matplotlib 都是大型库。减小体积的方法：
- 使用 `--onedir` 替代 `--onefile`（方便增量更新）
- 在虚拟环境中只安装必需的包
- 考虑使用 `--exclude-module` 排除不需要的 scipy 子模块（谨慎使用）

---

## 数据格式问题

### Q: 为什么某些列没有出现在下拉框中？

列检测逻辑（`utils.py → detect_columns`）会自动排除：
- `PART_ID` / `part_id` → 识别为 ID 列
- `group` / `Group` / `GROUP` / `组` / `分组` → 识别为分组列

如果你的列名恰好匹配这些关键词，它会被自动排除。如需修改，编辑 `config.py` 中的 `ID_CANDIDATES` 和 `GROUP_CANDIDATES`。

### Q: Excel 文件读取失败

- 确保安装了 `openpyxl`：`pip install openpyxl`
- 旧版 .xls 文件可能需要 `xlrd`：`pip install xlrd`
- 多 sheet 文件会弹窗选择工作表

---

## 开发相关问题

### Q: 嵌入模式 vs 独立模式有什么区别？

详见 [架构总览](architecture.md#两种运行模式)。

嵌入模式下 App 是其他 tkinter 窗口的 `Toplevel` 子窗口；独立模式下 App 自带隐藏的 `Tk()` 根窗口和独立事件循环。

### Q: 如何调试？

- 日志文件位于 `log/model_fitting_XXX.log`，每个窗口实例独立日志
- 日志级别为 DEBUG，包含拟合参数、R²、异常信息
- 在源码中运行可直接看到控制台输出

### Q: 修改代码后如何快速测试？

```bash
# 直接运行主程序
python model_fitting_app.py

# 运行测试启动器（含嵌入和独立两种模式）
python test_app.py

# 加载指定 CSV
python run.py test_weibull.csv
```
