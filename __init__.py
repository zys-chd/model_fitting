"""
model_fitting — 分布拟合工具包

用法:
    # 独立运行
    python run.py

    # 嵌入其他 tkinter 程序
    from model_fitting import App
    app = App(parent=my_parent_window)
    app.load_csv("data.csv")

    # 直接传入 DataFrame
    from model_fitting import App
    app = App(dataframe=my_dataframe)
"""
from .model_fitting_app import Model_Fitting_App

__all__ = ['Model_Fitting_App']
