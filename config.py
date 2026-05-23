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
MAX_SERIES = 4

# ============ 颜色方案 ============
COLORS = plt.cm.tab10(np.linspace(0, 1, 10))

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
