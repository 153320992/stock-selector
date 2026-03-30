#!/bin/bash

# 智能选股系统 - 一键停止脚本

echo "======================================"
echo "    智能选股系统 - 停止中..."
echo "======================================"
echo ""

# 停止后端
if [ -f "backend.pid" ]; then
    BACKEND_PID=$(cat backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID
        echo "✓ 后端服务已停止 (PID: $BACKEND_PID)"
    else
        echo "⚠ 后端服务未运行"
    fi
    rm -f backend.pid
else
    echo "⚠ 未找到后端PID文件"
fi

# 停止前端
if [ -f "frontend.pid" ]; then
    FRONTEND_PID=$(cat frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID
        echo "✓ 前端服务已停止 (PID: $FRONTEND_PID)"
    else
        echo "⚠ 前端服务未运行"
    fi
    rm -f frontend.pid
else
    echo "⚠ 未找到前端PID文件"
fi

# 额外清理：确保端口释放
echo ""
echo "清理端口..."

# 清理8000端口
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "清理端口8000..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
fi

# 清理3000端口
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "清理端口3000..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null
fi

echo ""
echo "======================================"
echo "✓ 所有服务已停止"
echo "======================================"
