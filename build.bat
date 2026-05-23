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
.venv_pack\Scripts\python.exe -m pip install -q numpy scipy pandas matplotlib pyinstaller
echo.

:: 清理旧构建
echo [3/3] 开始打包...
if exist "build" rmdir /s /q build
if exist "dist"  rmdir /s /q dist

.venv_pack\Scripts\python.exe -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name model_fitting ^
    --add-data "VERSION;." ^
    --clean ^
    app.py

echo.
echo ============================================
if exist "dist\model_fitting.exe" (
    echo   打包成功!
    for %%A in ("dist\model_fitting.exe") do echo   文件大小: %%~zA 字节
    echo   位置: dist\model_fitting.exe
) else (
    echo   打包失败，请检查上方错误信息
)
echo ============================================
pause
