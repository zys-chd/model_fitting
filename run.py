"""
独立运行入口
用法: python run.py                          （空窗口）
     python run.py data.csv                  （加载 CSV）
     python -c "from run import launch; launch(csv_path='data.csv')"
"""
import sys
import os

# 确保包根目录在 sys.path 中（支持直接 python run.py）
_pkg_dir = os.path.dirname(__file__)
_parent_dir = os.path.dirname(_pkg_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from model_fitting.model_fitting_app import launch # type: ignore

if __name__ == "__main__":
    csv = sys.argv[1] if len(sys.argv) > 1 else None
    launch(csv_path=csv)
