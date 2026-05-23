import os
import sys
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from scipy.special import gamma
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import matplotlib.patches as mpatches
from datetime import datetime


# matplotlib设置中文字体
plt.rcParams['font.family'] = 'Microsoft YaHei'
plt.rcParams['axes.unicode_minus'] = False  # 显示负号

# Global configuration
FONT_FAMILY = "微软雅黑"
FONT_SIZE = 10
MAX_SERIES = 4
COLORS = plt.cm.tab10(np.linspace(0, 1, 10))  # 10 different colors

# ============ Distribution Models ============

class DistributionModel:
	"""Base class for distribution models"""
	def __init__(self, name):
		self.name = name
		self.params = None
		self.pcov = None
		self.r_squared = None
	
	def fit(self, samples):
		"""Fit model to samples, return (params, pcov, r_squared)"""
		raise NotImplementedError
	
	def cdf(self, x, params):
		"""Calculate CDF at x"""
		raise NotImplementedError
	
	def get_formula(self):
		"""Return formula string"""
		raise NotImplementedError
	
	def get_param_names(self):
		"""Return parameter names"""
		raise NotImplementedError

class WeibullModel(DistributionModel):
	def __init__(self):
		super().__init__("Weibull")
	
	def fit(self, samples):
		x = np.asarray(samples)
		x = x[x > 0]
		if len(x) < 3:
			raise RuntimeError("Not enough positive samples to fit")
		xs = np.sort(x)
		cdf = np.arange(1, len(xs) + 1) / (len(xs) + 1)
		k0, lam0 = 1.5, np.mean(xs)
		try:
			popt, pcov = curve_fit(self._cdf_func, xs, cdf, p0=(k0, lam0), maxfev=10000)
		except:
			raise RuntimeError("Weibull fit failed")
		
		# Calculate R²
		y_pred = self._cdf_func(xs, *popt)
		ss_res = np.sum((cdf - y_pred) ** 2)
		ss_tot = np.sum((cdf - np.mean(cdf)) ** 2)
		r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
		
		self.params = popt
		self.pcov = pcov
		self.r_squared = r_squared
		return popt, pcov, r_squared, xs, cdf
	
	def _cdf_func(self, x, k, lam):
		return 1 - np.exp(-(x / lam) ** k)
	
	def cdf(self, x, params):
		k, lam = params
		return self._cdf_func(x, k, lam)
	
	def get_formula(self):
		return "F(x) = 1 - exp(-(x/λ)^k)"
	
	def get_param_names(self):
		return ["k (shape)", "λ (scale)"]

class LognormalModel(DistributionModel):
	def __init__(self):
		super().__init__("Lognormal")
	
	def fit(self, samples):
		from scipy.stats import lognorm
		x = np.asarray(samples)
		x = x[x > 0]
		if len(x) < 3:
			raise RuntimeError("Not enough positive samples to fit")
		xs = np.sort(x)
		cdf = np.arange(1, len(xs) + 1) / (len(xs) + 1)
		
		log_x = np.log(x)
		mu = np.mean(log_x)
		sigma = np.std(log_x)
		
		try:
			popt, pcov = curve_fit(self._cdf_func, xs, cdf, p0=(sigma, 0, mu), maxfev=10000)
		except:
			raise RuntimeError("Lognormal fit failed")
		
		y_pred = self._cdf_func(xs, *popt)
		ss_res = np.sum((cdf - y_pred) ** 2)
		ss_tot = np.sum((cdf - np.mean(cdf)) ** 2)
		r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
		
		self.params = popt
		self.pcov = pcov
		self.r_squared = r_squared
		return popt, pcov, r_squared, xs, cdf
	
	def _cdf_func(self, x, s, loc, scale):
		from scipy.stats import lognorm
		return lognorm.cdf(x, s, loc, scale)
	
	def cdf(self, x, params):
		return self._cdf_func(x, *params)
	
	def get_formula(self):
		return "F(x) = Φ((ln(x)-μ)/σ)"
	
	def get_param_names(self):
		return ["σ (shape)", "μ (location)", "scale"]

class NormalModel(DistributionModel):
	def __init__(self):
		super().__init__("Normal")
	
	def fit(self, samples):
		from scipy.stats import norm
		x = np.asarray(samples)
		if len(x) < 3:
			raise RuntimeError("Not enough samples to fit")
		xs = np.sort(x)
		cdf = np.arange(1, len(xs) + 1) / (len(xs) + 1)
		
		mu = np.mean(x)
		sigma = np.std(x)
		
		try:
			popt, pcov = curve_fit(self._cdf_func, xs, cdf, p0=(mu, sigma), maxfev=10000)
		except:
			raise RuntimeError("Normal fit failed")
		
		y_pred = self._cdf_func(xs, *popt)
		ss_res = np.sum((cdf - y_pred) ** 2)
		ss_tot = np.sum((cdf - np.mean(cdf)) ** 2)
		r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
		
		self.params = popt
		self.pcov = pcov
		self.r_squared = r_squared
		return popt, pcov, r_squared, xs, cdf
	
	def _cdf_func(self, x, mu, sigma):
		from scipy.stats import norm
		return norm.cdf(x, mu, sigma)
	
	def cdf(self, x, params):
		return self._cdf_func(x, *params)
	
	def get_formula(self):
		return "F(x) = Φ((x-μ)/σ)"
	
	def get_param_names(self):
		return ["μ (mean)", "σ (std)"]

def generate_test_data(path):
	"""Generate synthetic test data with group column"""
	rng = np.random.default_rng(12345)
	rows = 200
	groups = ['GroupA', 'GroupB', 'GroupC', 'GroupD', 'GroupE']
	
	data = {
		'PART_ID': [f'P{i:03d}' for i in range(rows)],
		'group': [groups[i % len(groups)] for i in range(rows)],
	}
	
	# Generate value columns (e.g., IDSS1, IDSS2, IGSS1, IGSS2)
	for col_idx, col_name in enumerate(['IDSS1', 'IDSS2', 'IGSS1', 'IGSS2']):
		k = 0.8 + 0.3 * col_idx
		lam = 50 + 10 * col_idx
		samples = rng.weibull(k, size=rows) * lam
		samples[rng.choice(rows, size=5, replace=False)] *= rng.uniform(1.5, 3.0, size=5)
		data[col_name] = samples
	
	df = pd.DataFrame(data)
	df.to_csv(path, index=False)


class SeriesSelector(ttk.Frame):
	"""数值列选择组件"""
	def __init__(self, master, columns, idx, remove_callback, *args, **kwargs):
		super().__init__(master, *args, **kwargs)
		self.idx = idx
		self.columns = columns
		self.remove_callback = remove_callback
		self.var = tk.StringVar()

		ttk.Label(self, text=f"列 {idx+1}：", font=(FONT_FAMILY, FONT_SIZE)).pack(side=tk.LEFT, padx=2)
		self.combo = ttk.Combobox(self, values=columns, textvariable=self.var, state='readonly', width=20)
		if columns:
			self.combo.current(0)
		self.combo.pack(side=tk.LEFT)

		btn = ttk.Button(self, text="移除", command=self._on_remove)
		btn.pack(side=tk.LEFT, padx=4)

	def _on_remove(self):
		self.remove_callback(self)

	def get_selection(self):
		return self.var.get()

# 缩放选项：显示名 -> matplotlib 内部名
SCALE_DISPLAY = ['线性', '对数']
SCALE_MAP = {'线性': 'linear', '对数': 'log'}

# 模型名映射：内部键 -> 显示名
MODEL_KEYS = ['Weibull', 'Lognormal', 'Normal']
MODEL_DISPLAY = ['Weibull（威布尔）', 'Lognormal（对数正态）', 'Normal（正态）']
MODEL_DISPLAY_MAP = dict(zip(MODEL_KEYS, MODEL_DISPLAY))
MODEL_KEY_MAP = dict(zip(MODEL_DISPLAY, MODEL_KEYS))

class App(tk.Toplevel):
	def __init__(self, parent=None, dataframe=None):
		# 支持嵌入其他 tkinter 程序：有 parent 则作为子窗口，否则独立运行
		self._standalone = parent is None
		if self._standalone:
			self._tk_root = tk.Tk()
			self._tk_root.withdraw()
			super().__init__(self._tk_root)
		else:
			super().__init__(parent)

		self.title("分布拟合工具")
		self.geometry("1400x900")
		self.protocol("WM_DELETE_WINDOW", self._on_close)

		style = ttk.Style(self)
		style.configure('.', font=(FONT_FAMILY, FONT_SIZE))

		self.data = None
		self.columns = []
		self.value_columns = []  # 数据列（不含 PART_ID 和 group）
		self.group_column = None
		self.selectors = []
		self.models = {
			'Weibull': WeibullModel(),
			'Lognormal': LognormalModel(),
			'Normal': NormalModel(),
		}
		self.current_model = 'Weibull'
		self.fit_results = {}  # {(col, group): (model, params, r2, xs, cdf)}
		self.figure = None
		self.canvas = None
		self.canvas_frame = None
		self.toolbar = None
		self.toolbar_frame = None
		self.hover_annot = None

		# 创建菜单
		menubar = tk.Menu(self)
		filemenu = tk.Menu(menubar, tearoff=0)
		filemenu.add_command(label="加载 CSV", command=self.load_csv)
		filemenu.add_command(label="生成测试数据", command=self.generate_and_load)
		filemenu.add_separator()
		filemenu.add_command(label="退出", command=self._on_close)
		menubar.add_cascade(label="文件", menu=filemenu)
		self.config(menu=menubar)

		# 顶部：控制区
		top_frame = ttk.Frame(self)
		top_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

		# 左侧：数值列选择
		left_frame = ttk.LabelFrame(top_frame, text="数值列")
		left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)
		self.left_inner = ttk.Frame(left_frame)
		self.left_inner.pack()

		# 中间：模型与图表控制
		ctrl_frame = ttk.LabelFrame(top_frame, text="显示控制")
		ctrl_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

		ttk.Label(ctrl_frame, text="模型：", font=(FONT_FAMILY, FONT_SIZE, "bold")).pack(anchor=tk.W, pady=4)
		self.model_var = tk.StringVar(value=MODEL_DISPLAY[0])
		model_combo = ttk.Combobox(ctrl_frame, textvariable=self.model_var, values=MODEL_DISPLAY, state='readonly', width=22)
		model_combo.pack(fill=tk.X, pady=2)
		model_combo.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

		ttk.Label(ctrl_frame, text="X 轴缩放：", font=(FONT_FAMILY, FONT_SIZE, "bold")).pack(anchor=tk.W, pady=(8,4))
		self.scale_x = tk.StringVar(value='线性')
		x_scale_combo = ttk.Combobox(ctrl_frame, textvariable=self.scale_x, values=SCALE_DISPLAY, state='readonly', width=22)
		x_scale_combo.pack(fill=tk.X, pady=2)
		x_scale_combo.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

		ttk.Label(ctrl_frame, text="Y 轴缩放：", font=(FONT_FAMILY, FONT_SIZE, "bold")).pack(anchor=tk.W, pady=(8,4))
		self.scale_y = tk.StringVar(value='线性')
		y_scale_combo = ttk.Combobox(ctrl_frame, textvariable=self.scale_y, values=SCALE_DISPLAY, state='readonly', width=22)
		y_scale_combo.pack(fill=tk.X, pady=2)
		y_scale_combo.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

		ttk.Label(ctrl_frame, text="数据变换：", font=(FONT_FAMILY, FONT_SIZE, "bold")).pack(anchor=tk.W, pady=(8,4))
		self.transform_mode = tk.StringVar(value='CDF')
		transform_combo = ttk.Combobox(ctrl_frame, textvariable=self.transform_mode, values=['CDF', 'ln(-ln(1-CDF))'], state='readonly', width=22)
		transform_combo.pack(fill=tk.X, pady=2)
		transform_combo.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

		ttk.Separator(ctrl_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

		ttk.Button(ctrl_frame, text="添加列", command=self.add_selector).pack(fill=tk.X, pady=2)
		ttk.Button(ctrl_frame, text="移除列", command=self.remove_last).pack(fill=tk.X, pady=2)

		# 右侧：导出按钮
		export_frame = ttk.LabelFrame(top_frame, text="导出")
		export_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)
		ttk.Button(export_frame, text="导出图片\n(PNG/PDF)", command=self.export_image).pack(fill=tk.X, pady=2)
		ttk.Button(export_frame, text="导出参数\n(CSV)", command=self.export_parameters).pack(fill=tk.X, pady=2)

		# 中部：图表 + 统计结果
		middle_frame = ttk.Frame(self)
		middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

		# 绘图区
		plot_frame = ttk.LabelFrame(middle_frame, text="图表")
		plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
		self.canvas_frame = ttk.Frame(plot_frame)
		self.canvas_frame.pack(fill=tk.BOTH, expand=True)

		# 统计结果区
		stats_frame = ttk.LabelFrame(middle_frame, text="拟合结果")
		stats_frame.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4, ipadx=4)

		# 统计文本（可选中复制）
		self.stats_text = tk.Text(stats_frame, width=40, height=25, wrap=tk.WORD, state=tk.DISABLED,
									font=(FONT_FAMILY, 9), bg='#f0f0f0')
		scrollbar = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=self.stats_text.yview)
		self.stats_text.config(yscrollcommand=scrollbar.set)

		self.stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

		# 鼠标滚轮支持
		self.stats_text.bind("<MouseWheel>", self._on_mousewheel)
		self.stats_text.bind("<Button-4>", self._on_mousewheel)  # Linux 上滚
		self.stats_text.bind("<Button-5>", self._on_mousewheel)  # Linux 下滚

		self.max_series = MAX_SERIES
		self.add_selector()

		# 如果传入了 DataFrame，直接加载
		if dataframe is not None:
			self.after(100, lambda: self.load_dataframe(dataframe))

	def _on_close(self):
		"""关闭窗口"""
		if self._standalone:
			self._tk_root.destroy()
		else:
			self.destroy()

	def generate_and_load(self):
		path = os.path.join(os.path.dirname(__file__), 'test_weibull.csv')
		generate_test_data(path)
		self.load_csv(path)

	def load_dataframe(self, df):
		"""直接接收 pandas DataFrame，供外部程序调用"""
		if not isinstance(df, pd.DataFrame):
			raise TypeError("参数必须是 pandas DataFrame")
		self.data = df
		self.columns = list(df.columns)

		# 检测分组列
		group_candidates = ['group', 'Group', 'GROUP', '组', '分组']
		self.group_column = None
		for gc in group_candidates:
			if gc in self.columns:
				self.group_column = gc
				break

		if self.group_column:
			self.value_columns = [c for c in self.columns if c not in ['PART_ID', 'part_id', self.group_column]]
		else:
			self.value_columns = [c for c in self.columns if c not in ['PART_ID', 'part_id']]

		# 更新选择器
		for s in self.selectors:
			s.combo['values'] = self.value_columns
			if self.value_columns:
				s.combo.current(0)

		self.fit_results.clear()
		self.update_plot()

	def load_csv(self, path=None):
		if path is None:
			path = filedialog.askopenfilename(filetypes=[('CSV 文件', '*.csv'), ('所有文件', '*.*')])
			if not path:
				return
		try:
			df = pd.read_csv(path)
		except Exception as e:
			messagebox.showerror("加载错误", str(e), parent=self)
			return

		self.data = df
		self.columns = list(df.columns)

		# 检测分组列
		group_candidates = ['group', 'Group', 'GROUP', '组', '分组']
		self.group_column = None
		for gc in group_candidates:
			if gc in self.columns:
				self.group_column = gc
				break

		if self.group_column:
			self.value_columns = [c for c in self.columns if c not in ['PART_ID', 'part_id', self.group_column]]
		else:
			self.value_columns = [c for c in self.columns if c not in ['PART_ID', 'part_id']]

		# 更新选择器
		for s in self.selectors:
			s.combo['values'] = self.value_columns
			if self.value_columns:
				s.combo.current(0)

		self.fit_results.clear()
		self.update_plot()

	def add_selector(self):
		if len(self.selectors) >= self.max_series:
			messagebox.showinfo("已达上限", f"最多支持 {self.max_series} 列", parent=self)
			return
		idx = len(self.selectors)
		sel = SeriesSelector(self.left_inner, self.value_columns, idx, remove_callback=self._remove_selector)
		sel.pack(fill=tk.X, pady=2)
		self.selectors.append(sel)
		self.update_plot()

	def remove_last(self):
		if not self.selectors:
			return
		sel = self.selectors.pop()
		sel.destroy()
		self.update_plot()

	def _remove_selector(self, sel):
		if sel in self.selectors:
			self.selectors.remove(sel)
			sel.destroy()
			self.update_plot()

	def update_plot(self):
		if self.data is None or not self.selectors:
			return
		
		self.current_model = MODEL_KEY_MAP.get(self.model_var.get(), 'Weibull')
		model = self.models[self.current_model]
		
		# Create figure
		if self.figure:
			plt.close(self.figure)
		
		self.figure = Figure(figsize=(10, 6), dpi=100)
		ax = self.figure.add_subplot(111)
		
		# Collect all groups
		if self.group_column:
			groups = sorted(self.data[self.group_column].unique())
		else:
			groups = ['All']
		
		# Color mapping
		group_colors = {g: COLORS[i % len(COLORS)] for i, g in enumerate(groups)}
		
		stats_texts = []
		y_all = []
		x_all = []
		
		# Plot data for each selected column
		for col_idx, sel in enumerate(self.selectors):
			col = sel.get_selection()
			if not col or col not in self.data.columns:
				continue
			
			# Plot by group
			if self.group_column:
				for group in groups:
					mask = self.data[self.group_column] == group
					samples = self.data[mask][col].dropna().values
					
					if len(samples) < 3:
						continue
					
					try:
						popt, pcov, r2, xs, cdf = model.fit(samples)
					except Exception as e:
						stats_texts.append((col_idx, col, group, f"拟合错误：{str(e)[:50]}"))
						continue
					
					self.fit_results[(col, group)] = (model.name, popt, r2, xs, cdf)
					
					# Transform y based on mode
					if self.transform_mode.get() == 'CDF':
						y = cdf
						ytitle = 'CDF'
					else:
						y = np.log(-np.log(np.maximum(1 - cdf, 1e-10)))
						ytitle = 'ln(-ln(1-CDF))'
					
					y_all.extend(y)
					x_all.extend(xs)
					
					# Plot sample points
					label = f'{col} - {group}' if self.group_column else col
					ax.scatter(xs, y, alpha=0.6, s=40, color=group_colors[group], label=label, edgecolor='none')
					
					# Plot theoretical curve
					xfine = np.linspace(xs.min(), xs.max() * 1.1, 200)
					yc = model.cdf(xfine, popt)
					
					if self.transform_mode.get() != 'CDF':
						yc = np.log(-np.log(np.maximum(1 - yc, 1e-10)))
					
					ax.plot(xfine, yc, color=group_colors[group], linestyle='-', alpha=0.8, linewidth=2)
					
					# Prepare stats
					param_names = model.get_param_names()
					param_str = ', '.join([f'{pn}={p:.4g}' for pn, p in zip(param_names, popt)])
					stats_texts.append((col_idx, col, group, f'R²={r2:.4f}\n{param_str}'))
			else:
				# No group column, treat all as one group
				samples = self.data[col].dropna().values
				if len(samples) < 3:
					continue
				
				try:
					popt, pcov, r2, xs, cdf = model.fit(samples)
				except Exception as e:
					stats_texts.append((col_idx, col, 'All', f"拟合错误：{str(e)[:50]}"))
					continue
				
				self.fit_results[(col, 'All')] = (model.name, popt, r2, xs, cdf)
				
				if self.transform_mode.get() == 'CDF':
					y = cdf
					ytitle = 'CDF'
				else:
					y = np.log(-np.log(np.maximum(1 - cdf, 1e-10)))
					ytitle = 'ln(-ln(1-CDF))'
				
				y_all.extend(y)
				x_all.extend(xs)
				
				ax.scatter(xs, y, alpha=0.6, s=40, color=group_colors['All'], label=col, edgecolor='none')
				
				xfine = np.linspace(xs.min(), xs.max() * 1.1, 200)
				yc = model.cdf(xfine, popt)
				if self.transform_mode.get() != 'CDF':
					yc = np.log(-np.log(np.maximum(1 - yc, 1e-10)))
				ax.plot(xfine, yc, color=group_colors['All'], linestyle='-', alpha=0.8, linewidth=2)
				
				param_names = model.get_param_names()
				param_str = ', '.join([f'{pn}={p:.4g}' for pn, p in zip(param_names, popt)])
				stats_texts.append((col_idx, col, 'All', f'R²={r2:.4f}\n{param_str}'))
		
		# 配置坐标轴
		ax.set_xlabel('X 值', fontsize=12)
		ax.set_ylabel(ytitle, fontsize=12)
		ax.set_title(f'{self.current_model} 分布拟合', fontsize=14, fontweight='bold')
		ax.set_xscale(SCALE_MAP.get(self.scale_x.get(), self.scale_x.get()))
		ax.set_yscale(SCALE_MAP.get(self.scale_y.get(), self.scale_y.get()))
		ax.legend(loc='best', fontsize=9, framealpha=0.9)
		ax.grid(True, alpha=0.3)
		
		self.figure.tight_layout()
		
		# Embed in tkinter - manage canvas and toolbar properly
		if self.canvas:
			self.canvas.get_tk_widget().destroy()
		if self.toolbar:
			self.toolbar.destroy()
			self.toolbar = None
		
		self.canvas = FigureCanvasTkAgg(self.figure, master=self.canvas_frame)
		self.canvas.draw()
		self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
		
		# Add toolbar below canvas
		try:
			if not self.toolbar_frame:
				self.toolbar_frame = ttk.Frame(self.canvas_frame)
				self.toolbar_frame.pack(fill=tk.X, padx=4, pady=2, side=tk.BOTTOM)
			self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
			self.toolbar.update()
		except:
			pass
		
		# Enable hover interaction
		self._setup_hover()
		
		# Update stats display
		self._update_stats_text(stats_texts)

	def _setup_hover(self):
		"""Setup hover to show point information"""
		if not self.canvas:
			return
		
		self.hover_annot = None
		
		def on_motion(event):
			if event.inaxes is None:
				if self.hover_annot:
					self.hover_annot.remove()
					self.hover_annot = None
					self.canvas.draw_idle()
				return
			
			ax = event.inaxes
			# Find closest data point
			min_dist = float('inf')
			closest_text = None
			
			for container in ax.containers:
				if hasattr(container, 'get_offsets'):  # PathCollection (scatter)
					offsets = container.get_offsets()
					if len(offsets) > 0:
						dist = np.linalg.norm(offsets - [event.xdata, event.ydata], axis=1)
						if np.min(dist) < min_dist:
							min_dist = np.min(dist)
							idx = np.argmin(dist)
							closest_text = f'({offsets[idx][0]:.4g}, {offsets[idx][1]:.4g})'
			
			if self.hover_annot:
				self.hover_annot.remove()
				self.hover_annot = None
			
			if closest_text and min_dist < 0.02 * (ax.get_xlim()[1] - ax.get_xlim()[0]):
				self.hover_annot = ax.annotate(closest_text, xy=(event.xdata, event.ydata),
					xytext=(10, 10), textcoords='offset points',
					bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
					arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
				self.canvas.draw_idle()
		
		self.canvas.mpl_connect('motion_notify_event', on_motion)

	def _update_stats_text(self, stats_texts):
		"""Update the statistics display panel with selectable text"""
		self.stats_text.config(state=tk.NORMAL)
		self.stats_text.delete(1.0, tk.END)
		
		if not stats_texts:
			self.stats_text.insert(tk.END, "无数据显示")
			self.stats_text.config(state=tk.DISABLED)
			return
		
		# Group by column
		by_column = {}
		for col_idx, col, group, text in stats_texts:
			if col not in by_column:
				by_column[col] = []
			by_column[col].append((group, text))
		
		# Insert text with formatting
		for col in by_column:
			self.stats_text.insert(tk.END, f"\n{col}\n" + "="*40 + "\n")
			
			for group, text in by_column[col]:
				self.stats_text.insert(tk.END, f"{group}:\n{text}\n\n")
		
		self.stats_text.config(state=tk.DISABLED)

	def _on_mousewheel(self, event):
		"""Handle mouse wheel scrolling for stats text"""
		if event.num == 5 or event.delta < 0:
			self.stats_text.yview_scroll(1, "units")
		elif event.num == 4 or event.delta > 0:
			self.stats_text.yview_scroll(-1, "units")

	def export_image(self):
		"""导出图片为 PNG 或 PDF"""
		if self.figure is None:
			messagebox.showwarning("导出", "没有可导出的图表", parent=self)
			return

		file_path = filedialog.asksaveasfilename(
			defaultextension=".png",
			filetypes=[("PNG 文件", "*.png"), ("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
			parent=self,
		)
		if file_path:
			try:
				self.figure.savefig(file_path, dpi=300, bbox_inches='tight')
				messagebox.showinfo("导出", f"图表已保存至：\n{file_path}", parent=self)
			except Exception as e:
				messagebox.showerror("导出错误", str(e), parent=self)

	def export_parameters(self):
		"""导出拟合参数为 CSV"""
		if not self.fit_results:
			messagebox.showwarning("导出", "没有可导出的拟合结果", parent=self)
			return

		file_path = filedialog.asksaveasfilename(
			defaultextension=".csv",
			filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
			parent=self,
		)
		if file_path:
			try:
				rows = []
				for (col, group), (model_name, params, r2, xs, cdf) in sorted(self.fit_results.items()):
					model = self.models[model_name]
					param_names = model.get_param_names()
					row = {
						'Column': col,
						'Group': group,
						'Model': model_name,
						'R_squared': f'{r2:.6f}',
						'Sample_Count': len(xs),
					}
					for pn, pv in zip(param_names, params):
						row[pn.replace(' ', '_')] = f'{pv:.6g}'
					rows.append(row)

				df_export = pd.DataFrame(rows)
				df_export.to_csv(file_path, index=False)
				messagebox.showinfo("导出", f"参数已保存至：\n{file_path}", parent=self)
			except Exception as e:
				messagebox.showerror("导出错误", str(e), parent=self)

if __name__ == '__main__':
	app = App()
	app._tk_root.mainloop()

