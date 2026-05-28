"""
独立运行入口
用法: python run.py                          （空窗口 — 新版 MVP 架构）
     python run.py data.csv                  （加载 CSV）
     python -c "from run import launch; launch(csv_path='data.csv')"

新版使用 ui.AppWindow + presenter.FittingPresenter（MVP 架构）。
旧版 model_fitting_app.launch 仍可通过 --legacy 标志使用：
     python run.py --legacy data.csv
"""
import sys
import os

# 确保包根目录在 sys.path 中（支持直接 python run.py）
_pkg_dir = os.path.dirname(__file__)
_parent_dir = os.path.dirname(_pkg_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


def launch(dataframe=None, csv_path=None):
    """启动新版分布拟合工具（MVP 架构）"""
    from model_fitting.ui.app_window import AppWindow  # type: ignore
    app = AppWindow(dataframe=dataframe)
    if csv_path and dataframe is None:
        app.after(100, lambda: app._presenter.load_file(csv_path))
    app._tk_root.mainloop()
    return app


def launch_legacy(dataframe=None, csv_path=None):
    """启动旧版分布拟合工具（兼容）"""
    from model_fitting.model_fitting_app import launch as _legacy_launch  # type: ignore
    return _legacy_launch(dataframe=dataframe, csv_path=csv_path)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_legacy = "--legacy" in sys.argv

    csv = args[0] if args else None
    if use_legacy:
        launch_legacy(csv_path=csv)
    else:
        launch(csv_path=csv)
