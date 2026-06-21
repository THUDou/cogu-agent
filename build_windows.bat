@echo off
chcp 65001 >nul
echo ============================================
echo   COGU Loong Windows Build Script
echo   Version 1.4.0
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

echo [1/7] Installing dependencies...
pip install pyinstaller httpx pydantic openai rich textual sqlite-fts4 pyyaml watchfiles anyio tiktoken fastapi "uvicorn[standard]" sse-starlette cryptography llama-cpp-python --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [2/7] Installing COGU package...
pip install -e . --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install COGU package
    pause
    exit /b 1
)

echo [3/7] Setting up Pangu venv (transformers 4.53.2)...
if not exist "pangu-env\Scripts\python.exe" (
    python -m venv pangu-env
    pangu-env\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu124 --quiet
    pangu-env\Scripts\python.exe -m pip install transformers==4.53.2 accelerate sentencepiece safetensors --quiet
)

echo [4/7] Building Studio UI (React)...
if exist "studio-ui\package.json" (
    cd studio-ui
    where npm >nul 2>nul && (
        npm install --prefer-offline
        npm run build
    )
    cd ..
)

echo [5/7] Building EXE with PyInstaller...
pyinstaller COGU-Loong.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed
    pause
    exit /b 1
)

echo [6/7] Organizing dist directory...
if not exist "dist\COGU-Loong" mkdir "dist\COGU-Loong"
if exist "dist\COGU-Loong.exe" (
    move /y "dist\COGU-Loong.exe" "dist\COGU-Loong\COGU-Loong.exe" >nul
)
xcopy /E /I /Y "pangu-env" "dist\COGU-Loong\pangu-env" >nul 2>nul
xcopy /E /I /Y "pangu-model" "dist\COGU-Loong\pangu-model" >nul 2>nul
if exist "studio-ui\dist" (
    xcopy /E /I /Y "studio-ui\dist" "dist\COGU-Loong\studio-ui" >nul 2>nul
)
copy /Y "start-cogu.bat" "dist\COGU-Loong\" >nul 2>nul
copy /Y "quick-start.bat" "dist\COGU-Loong\" >nul 2>nul

echo [7/7] Build complete!
echo.
echo   Output: dist\COGU-Loong\
echo   EXE:    dist\COGU-Loong\COGU-Loong.exe
echo   CLI:    python -m cogu
echo   TUI:    python -m cogu.tui
echo.
echo To create installer, run Inno Setup on installer-simple.iss
echo.

pause
