# 添加自定义分布模型

按照以下 3 步即可新增一个拟合模型，全程无需改动 GUI 代码。

## 第 1 步：创建模型文件

在 `models/` 目录下新建一个 Python 文件（如 `my_model.py`），继承 `DistributionModel` 并实现以下方法：

```python
"""MyModel 分布模型"""
import numpy as np
from scipy.optimize import curve_fit

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class MyModel(DistributionModel):
    """自定义分布拟合模型"""

    KEY = "MyModel"  # 唯一内部标识，用于注册

    def __init__(self):
        super().__init__(self.KEY)

    # ---------- 必须实现的方法 ----------

    def fit(self, samples):
        """
        拟合模型到样本数据。

        参数:
            samples: array-like，原始样本数据

        返回:
            (params, pcov, r_squared, xs, cdf)
            - params:  拟合参数 tuple，与 get_param_names() 顺序一致
            - pcov:    协方差矩阵 (curve_fit 返回)
            - r_squared: R² 决定系数
            - xs:      排序后的样本值 (x 轴)
            - cdf:     经验 CDF 值 (y 轴)，由 prepare_cdf_data() 计算
        """
        x = np.asarray(samples)
        # 如有必要，过滤无效值（如 x <= 0）
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足")

        # 基类提供：排序 + 中位秩经验 CDF
        xs, cdf = self.prepare_cdf_data(x)

        # 设置初始猜测值
        p0 = (1.0, np.mean(xs))

        # 用 scipy.optimize.curve_fit 拟合
        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=p0, maxfev=10000)
        except Exception:
            raise RuntimeError("MyModel 拟合失败")

        # 计算 R²
        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)

        # 保存结果（可选）
        self.params = popt
        self.pcov = pcov
        self.r_squared = r_squared

        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, a, b):
        """内部 CDF 函数（供 curve_fit 调用），参数需与 fit() 中 p0 对应"""
        return 1 - np.exp(-(x / b) ** a)

    def cdf(self, x, params):
        """给定参数计算 x 处的 CDF 值（用于绘制拟合曲线）"""
        return self._cdf_func(x, *params)

    def get_formula(self):
        """返回 LaTeX 公式字符串（显示在 UI 公式区域）"""
        return r"F(x) = 1 - \exp\left(-\left(\frac{x}{b}\right)^{a}\right)"

    def get_param_names(self):
        """返回参数名列表，顺序与 fit() 返回的 params 一致"""
        return ["a (param1)", "b (param2)"]

    # ---------- 可选重写 ----------

    def get_description(self):
        """返回模型介绍文本（显示在"关于"菜单的详情弹窗中）"""
        return (
            "自定义模型的详细说明。\n\n"
            "参数：a — 参数1说明\n"
            "　　　b — 参数2说明\n\n"
            "适用场景描述。"
        )
```

### 方法说明

| 方法 | 必须 | 说明 |
|---|---|---|
| `fit(samples)` | ✅ | 核心拟合逻辑，返回 `(params, pcov, r², xs, cdf)` |
| `cdf(x, params)` | ✅ | 给定 x 和拟合参数，计算 CDF 值 |
| `get_formula()` | ✅ | 返回 LaTeX 公式，显示在 UI 中 |
| `get_param_names()` | ✅ | 参数名列表，用于统计树和导出 CSV |
| `get_description()` | ❌ | 模型介绍文本（可选） |

### 基类提供的工具方法

| 方法 | 说明 |
|---|---|
| `prepare_cdf_data(samples)` | 排序 + 中位秩经验 CDF：`(i-0.3)/(N+0.4)` |
| `compute_r_squared(y_true, y_pred)` | 标准 R² 计算 |

### 注意事项

- `_cdf_func` 的参数签名必须和 `fit()` 中 `curve_fit` 的 `p0` 元组一一对应
- `get_param_names()` 返回的列表顺序需与 `params` 一致
- 使用相对导入 `from .base import DistributionModel` 确保 PyInstaller 打包兼容
- 拟合失败时抛出 `RuntimeError`，GUI 会自动捕获并跳过该组数据

## 第 2 步：注册到模型中心

编辑 `models/__init__.py`，导入新模型并加入 `MODEL_INSTANCES` 字典：

```python
# 1. 在文件顶部添加导入（相对导入 + 绝对导入各一份）
try:
    from .my_model import MyModel
except ImportError:
    from my_model import MyModel

# 2. 在 MODEL_INSTANCES 字典中添加
MODEL_INSTANCES = {
    WeibullModel.KEY: WeibullModel(),
    # ... 其他已有模型 ...
    MyModel.KEY: MyModel(),          # ← 新增
}
```

## 第 3 步：注册到配置

编辑 `config.py`，在 `MODEL_KEYS` 列表和 `MODEL_DISPLAY` 列表中追加：

```python
MODEL_KEYS = [
    'Weibull', 'Weibull3P', 'Exponential', 'Lognormal', 'Normal',
    'Gamma', 'LogLogistic', 'Gumbel', 'BirnbaumSaunders',
    'MyModel',  # ← 新增（与 MyModel.KEY 一致）
]

MODEL_DISPLAY = [
    'Weibull-2P（威布尔两参数）',
    # ... 其他已有显示名 ...
    'MyModel（自定义分布）',  # ← 新增（显示在 GUI 下拉菜单中）
]
```

**注意：** `MODEL_KEYS`、`MODEL_DISPLAY`、`MODEL_KEY_MAP` 三者顺序必须一一对应。

## 验证

完成后运行程序，在"数据控制"面板的模型下拉框中应能看到新模型，选择后即可进行拟合。
