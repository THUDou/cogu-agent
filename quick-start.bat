@echo off
chcp 65001 >nul
echo ============================================
echo   COGU AGENT - 快速启动
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

echo [1/4] 检查依赖...
pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo [2/4] 安装依赖...
    pip install -e .
)

echo [3/4] 检查配置...
if not exist ".cogu" (
    mkdir ".cogu"
)

echo.
echo ============================================
echo   启动方式选择：
echo   1. 启动后端 API 服务
echo   2. 启动桌面应用 (需要 pywebview)
echo   3. 启动 TUI 终端界面
echo   4. 配置 API Key
echo   5. 仅安装依赖
echo ============================================
echo.
set /p choice="请选择 (1-5): "

if "%choice%"=="1" (
    echo.
    echo [4/4] 启动后端 API 服务...
    python start_server.py
) else if "%choice%"=="2" (
    echo.
    echo [4/4] 启动桌面应用...
    python -m cogu.desktop.loong
) else if "%choice%"=="3" (
    echo.
    echo [4/4] 启动 TUI 界面...
    cogu tui
) else if "%choice%"=="4" (
    echo.
    echo 配置 DeepSeek API Key...
    set /p apikey="请输入您的 DeepSeek API Key: "
    cogu config set deepseek %apikey%
    echo.
    echo API Key 已配置！
    pause
) else if "%choice%"=="5" (
    echo.
    echo 安装完整依赖...
    pip install -e .[comm,s3,server]
    echo.
    echo 依赖安装完成！
    pause
) else (
    echo 无效选择！
    pause
)
