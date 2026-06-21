#!/bin/bash
# COGU Agent 一键启动脚本（macOS/Linux）
# 功能：同时启动 Gateway (后端) + Studio UI (前端)

set -e

echo "=================================================="
echo "   COGU Agent 一键启动脚本"
echo "=================================================="
echo ""

# 检查 Python 是否可用
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[错误] 未找到 Python，请先安装 Python 3.11+"
    exit 1
fi

# 使用 python3 或 python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# 检查 COGU 是否安装
if ! $PYTHON_CMD -c "import cogu" 2>/dev/null; then
    echo "[错误] 未找到 COGU Agent，请先安装："
    echo "  pip install -e ."
    exit 1
fi

# 设置端口（可自定义）
GATEWAY_PORT=${1:-8080}
STUDIO_PORT=${2:-5174}

echo "[1/5] 正在启动 Gateway (端口 $GATEWAY_PORT)..."
$PYTHON_CMD -m cogu.cli.main serve --port $GATEWAY_PORT > /tmp/cogu-gateway.log 2>&1 &
GATEWAY_PID=$!
echo "      Gateway PID: $GATEWAY_PID"

# 等待 Gateway 启动
echo "[2/5] 等待 Gateway 启动..."
sleep 3

# 检查端口是否可用
if lsof -i :$GATEWAY_PORT > /dev/null 2>&1 || netstat -an | grep ":$GATEWAY_PORT " > /dev/null 2>&1; then
    echo "[✓] Gateway 已启动：http://127.0.0.1:$GATEWAY_PORT"
    echo "      Swagger UI: http://127.0.0.1:$GATEWAY_PORT/docs"
else
    echo "[警告] Gateway 可能未正常启动，请检查 /tmp/cogu-gateway.log"
fi

echo ""
echo "[3/5] 正在启动 Studio UI (端口 $STUDIO_PORT)..."
echo "      后端 API 端口: $GATEWAY_PORT"
$PYTHON_CMD -m cogu.cli.main studio --port $STUDIO_PORT --api-port $GATEWAY_PORT > /tmp/cogu-studio.log 2>&1 &
STUDIO_PID=$!
echo "      Studio UI PID: $STUDIO_PID"

# 等待 Studio UI 启动
echo "[4/5] 等待 Studio UI 启动..."
sleep 5

echo ""
echo "========= 启动完成！========="
echo ""
echo "Gateway (后端):   http://127.0.0.1:$GATEWAY_PORT"
echo "  - Swagger UI:  http://127.0.0.1:$GATEWAY_PORT/docs"
echo "  - 健康检查:    http://127.0.0.1:$GATEWAY_PORT/healthz"
echo ""
echo "Studio UI (前端): http://localhost:$STUDIO_PORT"
echo ""
echo "[提示] 关闭服务请运行："
echo "  kill $GATEWAY_PID $STUDIO_PID"
echo ""

# 打开浏览器
if command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open http://localhost:$STUDIO_PORT
elif command -v open &> /dev/null; then
    # macOS
    open http://localhost:$STUDIO_PORT
fi

# 保持脚本运行，显示日志
echo "[5/5] 显示 Gateway 日志 (Ctrl+C 退出查看 Studio UI 日志)..."
echo "=================================================="
tail -f /tmp/cogu-gateway.log
