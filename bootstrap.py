"""
模型拟合工具 — 启动入口（精简版）

C launcher 已完成所有依赖检查，此脚本仅负责启动主程序。
用法：python bootstrap.py [data.csv] [--legacy]
"""

import os
import sys

# 确保包可导入：<temp>/model_fitting/ 的父目录加到 sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


def main():
    csv_path = None
    use_legacy = False
    for a in sys.argv[1:]:
        if a == "--legacy":
            use_legacy = True
        elif not a.startswith("--"):
            csv_path = a

    try:
        if use_legacy:
            from model_fitting.model_fitting_app import launch
            launch(dataframe=None, csv_path=csv_path)
        else:
            from model_fitting.run import launch
            launch(dataframe=None, csv_path=csv_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
