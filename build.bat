@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   模型拟合工具 - 一键打包脚本
echo ============================================
echo.

:: 检查虚拟环境
if not exist ".venv_pack\Scripts\python.exe" (
    echo [1/3] 创建虚拟环境...
    python -m venv .venv_pack
    echo.
)

:: 安装依赖
echo [2/3] 安装/更新依赖...
.venv_pack\Scripts\python.exe -m pip install -r requirements.txt --upgrade
echo.

:: 清理旧构建
echo [3/3] 开始打包...
if exist "build" rmdir /s /q build
if exist "dist"  rmdir /s /q dist
if exist "model_fiting.spec" del /f model_fiting.spec

.venv_pack\Scripts\python.exe -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name model_fiting ^
    --icon "model_fitting.ico" ^
    --add-data "VERSION:." ^
    --add-data "model_fitting.ico:." ^
    --add-data "model_fitting.png:." ^
    --clean ^
    --splash "model_fitting.png" ^
    model_fitting_app.py

echo.
echo ============================================
if exist "dist\model_fiting.exe" (
    echo   打包成功!
    for %%A in ("dist\model_fiting.exe") do echo   文件大小: %%~zA 字节
    echo   位置: dist\model_fiting.exe
) else (
    echo   打包失败，请检查上方错误信息
)
echo ============================================
pause
