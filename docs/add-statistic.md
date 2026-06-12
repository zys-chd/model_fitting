# 添加自定义统计指标

按照以下 3 步即可新增一个统计指标，全程无需改动 UI 代码。
新增后会自动出现在统计树和导出表中，并可通过统计筛选 Combobox 控制显示/隐藏。

## 第 1 步：创建统计计算器

在 `services/stat_registry.py` 中新建一个继承 `StatCalculator` 的类：

```python
from .stat_registry import StatCalculator

class MyStatCalculator(StatCalculator):
    """我的自定义统计指标"""

    KEY: ClassVar[str] = "my_stat"           # 唯一标识
    DISPLAY_ORDER: ClassVar[int] = 50        # 排序权重，越小越靠前（参考: basic=10, fit_at_limit=90）

    def compute(self, samples: np.ndarray, **context) -> dict[str, Any]:
        """
        计算统计量。

        Parameters
        ----------
        samples : np.ndarray
            样本数据
        **context
            额外上下文，可包含:
            - model: DistributionModel    当前拟合模型
            - params: tuple               拟合参数
            - limit: float                当前 limit 值
            - quantile_low: float         自定义低分位数 (默认 5)
            - quantile_high: float        自定义高分位数 (默认 95)
            - fit_result: Any             拟合结果对象（视 Service 传入）

        Returns
        -------
        dict[str, Any]
            {显示名: 值}，如 {"我的指标": 1.23}
            返回空 dict {} 表示该指标在当前上下文中不适用。
        """
        s = np.asarray(samples)
        if len(s) == 0:
            return {}

        # === 在这里写你的计算逻辑 ===
        my_value = np.sum(s) / (len(s) + 1)

        return {"我的指标": float(my_value)}
```

**返回 dict 的 key 即为 UI 中显示的名称**，value 为数值。返回 `{}` 则该指标不显示。

## 第 2 步：注册到 STAT_REGISTRY

在同一个文件的 `STAT_REGISTRY` 字典中添加一行：

```python
STAT_REGISTRY: dict[str, StatCalculator] = {
    "basic": BasicStatsCalculator(),
    "fit_at_limit": FitAtLimitCalculator(),
    "my_stat": MyStatCalculator(),          # ← 新增这一行
}
```

`key` 必须与类的 `KEY` 一致。

## 第 3 步：测试

运行程序，加载数据并完成拟合后：

1. 统计树中会自动出现新的指标行
2. 统计筛选 Combobox 中会出现 ☑/☐ 切换项
3. 导出 Excel/CSV 时自动包含新列
4. "关于 → 统计信息计算方法" 中不会自动添加说明（需手动更新 `_show_stats_info`）

## context 可用参数速查

| 参数 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `model` | `DistributionModel` | 当前拟合模型 | `WeibullModel()` |
| `params` | `tuple` | 拟合参数 | `(beta, eta)` |
| `limit` | `float` | 当前 limit 值 | `0.1` |
| `quantile_low` | `float` | 自定义低分位数 | `5.0` |
| `quantile_high` | `float` | 自定义高分位数 | `95.0` |

所有 context 参数都是可选的，用 `.get()` 安全获取。

## 完整示例：添加几何均值

```python
class GeometricMeanCalculator(StatCalculator):
    """几何均值"""

    KEY: ClassVar[str] = "geometric_mean"
    DISPLAY_ORDER: ClassVar[int] = 30

    def compute(self, samples: np.ndarray, **context) -> dict[str, Any]:
        s = np.asarray(samples)
        if len(s) == 0:
            return {}
        # 几何均值 = (∏xᵢ)^(1/n), 要求所有值 > 0
        if np.any(s <= 0):
            return {}
        from scipy.stats import gmean
        return {"几何均值": float(gmean(s))}
```

然后在 `STAT_REGISTRY` 中加入 `"geometric_mean": GeometricMeanCalculator()` 即可。

## DISPLAY_ORDER 参考值

| 值 | 位置 | 现有指标 |
|----|------|---------|
| 10 | 最前 | 样本数、均值、标准差、中位数、分位数、极值、偏度、CV |
| 30 | 基础后 | （自定义区域） |
| 50 | 中间 | （自定义区域） |
| 90 | 拟合相关 | limit处F值 |
| 100+ | 最后 | — |
