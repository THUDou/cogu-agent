#!/usr/bin/env bash
# docx-craft environment setup script
set -euo pipefail

echo "=== docx-craft Setup ==="

# Check Node.js
if command -v node &>/dev/null; then
    NODE_VER=$(node -v)
    echo "[OK] Node.js: $NODE_VER"
else
    echo "[MISSING] Node.js >= 18.0 is required"
    echo "  Install: https://nodejs.org/"
    exit 1
fi

# Check Python
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version)
    echo "[OK] Python: $PY_VER"
elif command -v python &>/dev/null; then
    PY_VER=$(python --version)
    echo "[OK] Python: $PY_VER"
else
    echo "[MISSING] Python >= 3.8 is required"
    exit 1
fi

# Install npm dependencies
echo ""
echo "Installing npm dependencies..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ -f package.json ]; then
    npm install --silent
    echo "[OK] npm dependencies installed"
else
    echo "[SKIP] No package.json found"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -q defusedxml lxml 2>/dev/null || pip3 install -q defusedxml lxml 2>/dev/null
echo "[OK] Python dependencies installed"

# Verify docx-js
echo ""
echo "Verifying docx-js..."
if node -e "require('docx')" 2>/dev/null; then
    echo "[OK] docx-js loaded successfully"
else
    echo "[FAIL] docx-js not available"
    exit 1
fi

# Verify Python XML libs
echo "Verifying Python XML libraries..."
if python3 -c "import defusedxml, lxml" 2>/dev/null || python -c "import defusedxml, lxml" 2>/dev/null; then
    echo "[OK] defusedxml + lxml available"
else
    echo "[FAIL] Python XML libraries not available"
    exit 1
fi

# Optional: pandoc
echo ""
if command -v pandoc &>/dev/null; then
    echo "[OK] pandoc: $(pandoc --version | head -1)"
else
    echo "[OPTIONAL] pandoc not found — document preview will use raw XML"
fi

# Optional: LibreOffice
if command -v soffice &>/dev/null; then
    echo "[OK] LibreOffice available"
else
    echo "[OPTIONAL] LibreOffice not found — .doc conversion and accept-changes unavailable"
fi

echo ""
echo "=== Setup Complete ==="
