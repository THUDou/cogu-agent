@echo off
REM COGU Agent 一键启动脚本（Windows）
REM 功能：同时启动 Gateway (后端) + Studio UI (前端)

echo ===================================================
echo   COGU Agent 一键启动脚本
echo ===================================================
echo.

REM 检查 Python 是否可用
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

REM 检查 COGU 是否安装
python -c "import cogu" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未找到 COGU Agent，请先安装：
    echo   pip install -e .
    pause
    exit /b 1
)

REM 设置端口（可自定义）
set GATEWAY_PORT=8080
set STUDIO_PORT=5174

echo [1/4] 正在启动 Gateway (端口 %GATEWAY_PORT%)...
start "COGU Gateway" /MIN cmd /c "python -m cogu.cli.main serve --port %GATEWAY_PORT%"

REM 等待 Gateway 启动
echo [2/4] 等待 Gateway 启动...
timeout /t 3 /nobreak >nul

REM 检查端口是否可用
netstat -an | find ":%GATEWAY_PORT%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [✓] Gateway 已启动：http://127.0.0.1:%GATEWAY_PORT%
    echo      Swagger UI: http://127.0.0.1:%GATEWAY_PORT%/docs
) else (
    echo [警告] Gateway 可能未正常启动，请检查。
)

echo.
echo [3/4] 正在启动 Studio UI (端口 %STUDIO_PORT%)...
start "COGU Studio UI" cmd /c "python -m cogu.cli.main studio --port %STUDIO_PORT% --api-port %GATEWAY_PORT%"

REM 等待 Studio UI 启动
echo [4/4] 等待 Studio UI 启动...
timeout /t 5 /nobreak >nul

echo.
echo ========== 启动完成！==========
echo.
echo Gateway (后端):   http://127.0.0.1:%GATEWAY_PORT%
echo   - Swagger UI:  http://127.0.0.1:%GATEWAY_PORT%/docs
echo   - 健康检查:    http://127.0.0.1:%GATEWAY_PORT%/healthz
echo.
echo Studio UI (前端): http://localhost:%STUDIO_PORT%
echo.
echo [提示] 关闭此窗口不会停止服务，请手动关闭 Gateway/Studio UI 窗口。
echo.

REM 打开浏览器
start http://localhost:%STUDIO_PORT%

pause
