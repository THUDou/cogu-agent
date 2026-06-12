@echo off
chcp 65001 >nul
echo ============================================
echo   COGU Loong Windows Build Script
echo   Version 0.9.1
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

echo [1/5] Installing dependencies...
pip install pyinstaller httpx pydantic openai rich textual sqlite-fts4 pyyaml watchfiles anyio tiktoken fastapi "uvicorn[standard]" sse-starlette --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [2/5] Installing COGU package...
pip install -e . --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install COGU package
    pause
    exit /b 1
)

echo [3/5] Building EXE with PyInstaller...
pyinstaller COGU-Loong.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed
    pause
    exit /b 1
)

echo [4/5] Organizing dist directory...
if not exist "dist\COGU-Loong" mkdir "dist\COGU-Loong"
if exist "dist\COGU-Loong.exe" (
    move /y "dist\COGU-Loong.exe" "dist\COGU-Loong\COGU-Loong.exe" >nul
)

echo [5/5] Build complete!
echo.
echo   Output: dist\COGU-Loong\COGU-Loong.exe
echo.
echo To create installer, run NSIS on installer.nsi
echo.

pause