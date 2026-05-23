"""
独立运行入口
用法: python run.py  （在 model_fitting/ 目录下）
     或: python -m model_fitting.run  （在父目录）
"""
import sys
import os

# 确保包根目录在 sys.path 中（支持直接 python run.py）
_pkg_dir = os.path.dirname(__file__)
_parent_dir = os.path.dirname(_pkg_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from model_fitting import App

if __name__ == '__main__':
    app = App()
    app._tk_root.mainloop()
