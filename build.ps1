# ============================================
#  模型拟合工具 - PowerShell 一键打包脚本
# ============================================
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 读取版本号
$version = (Get-Content "VERSION" -Encoding UTF8).Trim()
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  模型拟合工具 v$version - 打包脚本" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境
$venvPython = ".venv_pack\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[1/4] 创建虚拟环境..." -ForegroundColor Yellow
    python -m venv .venv_pack
    Write-Host ""
}

# 安装依赖
Write-Host "[2/4] 安装/更新依赖..." -ForegroundColor Yellow
& $venvPython -m pip install -r requirements.txt --upgrade
Write-Host ""

# 清理旧构建
Write-Host "[3/4] 清理旧构建..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }
if (Test-Path "model_fiting.spec") { Remove-Item -Force "model_fiting.spec" }

# 打包
$exeName = "model_fiting_v$version"
Write-Host "[4/4] PyInstaller 打包 -> $exeName.exe" -ForegroundColor Yellow

& $venvPython -m PyInstaller `
    --onefile `
    --noconsole `
    --name $exeName `
    --icon "model_fitting.ico" `
    --add-data "VERSION;." `
    --add-data "model_fitting.ico;." `
    --add-data "model_fitting.png;." `
    --clean `
    --splash "model_fitting.png" `
    run.py

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
$distExe = "dist\$exeName.exe"
if (Test-Path $distExe) {
    $size = (Get-Item $distExe).Length
    Write-Host "  打包成功!" -ForegroundColor Green
    Write-Host "  文件: $distExe" -ForegroundColor Green
    Write-Host "  大小: $([math]::Round($size/1MB, 1)) MB" -ForegroundColor Green
} else {
    Write-Host "  打包失败，请检查上方错误信息" -ForegroundColor Red
}
Write-Host "============================================" -ForegroundColor Cyan
