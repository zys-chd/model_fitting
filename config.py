"""
全局配置常量
集中管理字体、颜色、缩放映射、模型注册信息等
"""
import matplotlib.pyplot as plt
import numpy as np

# ============ 字体与样式 ============
FONT_FAMILY = "微软雅黑"
FONT_SIZE = 10

# matplotlib 全局中文字体设置
plt.rcParams['font.family'] = 'Microsoft YaHei'
plt.rcParams['axes.unicode_minus'] = False

# ============ 系列数量限制 ============
MAX_SERIES = 8

# ============ 颜色方案 ============
COLORS = plt.cm.tab10(np.linspace(0, 1, 10))

# ============ 颜色调色板 ============
COLOR_PALETTES = {
    "tab10": {"name": "Tab10 (默认)", "colors": plt.cm.tab10(np.linspace(0, 1, 10))},
    "Set1":  {"name": "Set1 (鲜明)",  "colors": plt.cm.Set1(np.linspace(0, 1, 9))},
    "Set2":  {"name": "Set2 (柔和)",  "colors": plt.cm.Set2(np.linspace(0, 1, 8))},
    "Dark2": {"name": "Dark2 (深色)", "colors": plt.cm.Dark2(np.linspace(0, 1, 8))},
    "Paired": {"name": "Paired (配对)", "colors": plt.cm.Paired(np.linspace(0, 1, 12))},
    "Pastel1": {"name": "Pastel1 (粉彩)", "colors": plt.cm.Pastel1(np.linspace(0, 1, 9))},
    "Set3": {"name": "Set3 (Set3)", "colors": plt.cm.Set3(np.linspace(0, 1, 12))},
    "Accent": {"name": "Accent (强调)", "colors": plt.cm.Accent(np.linspace(0, 1, 8))},
}
COLOR_PALETTE_KEYS = list(COLOR_PALETTES.keys())

# 循环用的默认 marker/linestyle 序列
CYCLE_MARKERS = ['o', 's', '^', 'D', 'v', 'p', '*', 'X', 'h', '<', '>']
CYCLE_LINESTYLES = ['-', '--', ':', '-.']

# ============ 坐标轴缩放映射（显示名 -> matplotlib 内部名）============
SCALE_DISPLAY = ['线性', '对数']
SCALE_MAP = {'线性': 'linear', '对数': 'log'}

# ============ 数据变换选项 ============
TRANSFORM_OPTIONS = ['CDF', 'ln(-ln(1-CDF))']

# ============ 模型注册 ============
# 内部键列表（与 models/ 下各模块的 key 一致）
MODEL_KEYS = ['Weibull', 'Weibull3P', 'Exponential', 'Lognormal', 'Normal',
              'Gamma', 'LogLogistic', 'Gumbel', 'BirnbaumSaunders']

MODEL_DISPLAY = [
    'Weibull-2P（威布尔两参数）',
    'Weibull-3P（威布尔三参数）',
    'Exponential（指数分布）',
    'Lognormal（对数正态）',
    'Normal（正态）',
    'Gamma（伽马）',
    'Log-Logistic（对数逻辑）',
    'Gumbel（极值I型）',
    'Birnbaum-Saunders（疲劳寿命）',
]

# 双向映射
MODEL_DISPLAY_MAP = dict(zip(MODEL_KEYS, MODEL_DISPLAY))
MODEL_KEY_MAP = dict(zip(MODEL_DISPLAY, MODEL_KEYS))

# ============ 分组列候选名 ============
GROUP_CANDIDATES = ['group', 'Group', 'GROUP', '组', '分组']

# ============ ID 列候选名 ============
ID_CANDIDATES = ['PART_ID', 'part_id']

# ============ 列名后缀过滤 ============
# 若列名以这些后缀结尾，且存在同基名不同后缀的列组，可配置只保留 _shift 结尾的列
COLUMN_SUFFIX_CANDIDATES = ['_T0', '_After', '_shift']
# 默认关闭：需用户手动在界面中开启
FILTER_KEEP_SHIFT_ONLY_DEFAULT = False

# ============ 曲线显示默认值 ============
SHOW_FIT_CURVE_DEFAULT = True  # 加载数据后默认是否显示拟合曲线；散点始终默认显示
