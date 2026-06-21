#!/usr/bin/env bash
# docx-craft environment readiness check
# Run at the start of each session before performing operations.
set -euo pipefail

READY=true

# Node.js + docx-js
if command -v node &>/dev/null && node -e "require('docx')" 2>/dev/null; then
    echo "[OK] Node.js + docx-js"
else
    echo "[FAIL] Node.js + docx-js not available"
    READY=false
fi

# Python + XML libs
PY="python3"
if ! command -v python3 &>/dev/null; then PY="python"; fi
if $PY -c "import defusedxml, lxml" 2>/dev/null; then
    echo "[OK] Python + defusedxml + lxml"
else
    echo "[FAIL] Python XML libraries not available"
    READY=false
fi

# Optional tools
command -v pandoc &>/dev/null && echo "[OK] pandoc" || echo "[OPTIONAL] pandoc not found"
command -v soffice &>/dev/null && echo "[OK] LibreOffice" || echo "[OPTIONAL] LibreOffice not found"

if $READY; then
    echo ""
    echo "STATUS: READY"
else
    echo ""
    echo "STATUS: NOT READY — run scripts/setup.sh to install dependencies"
    exit 1
fi
