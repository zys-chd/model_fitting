@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   分布拟合测试工具 - 一键打包脚本
echo ============================================
echo.

:: 检查虚拟环境
if not exist ".venv_pack\Scripts\python.exe" (
    echo [1/4] 创建虚拟环境...
    python -m venv .venv_pack
    echo.
)

:: 安装依赖
echo [2/4] 安装/更新依赖...
.venv_pack\Scripts\python.exe -m pip install -r model_fitting\requirements.txt --upgrade
echo.

:: 清理旧构建
echo [3/4] 清理旧构建...
if exist "build"   rmdir /s /q build
if exist "dist"    rmdir /s /q dist
if exist "test_app.spec" del /f test_app.spec
echo.

:: 打包
echo [4/4] 开始打包...
.venv_pack\Scripts\python.exe -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name "分布拟合测试工具" ^
    --icon "mf.ico" ^
    --add-data "model_fitting\VERSION;." ^
    --add-data "model_fitting\model_fitting.ico;." ^
    --add-data "model_fitting\model_fitting.png;." ^
    --add-data "test_weibull.csv;." ^
    --add-data "fitting_template.csv;." ^
    --hidden-import "scipy" ^
    --hidden-import "PIL" ^
    --hidden-import "openpyxl" ^
    --clean ^
    --splash "model_fitting.png" ^
    test_app.py

echo.
echo ============================================
echo   打包完成！输出在 dist\ 目录
echo ============================================
pause
