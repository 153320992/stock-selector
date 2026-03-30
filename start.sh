#!/bin/bash

# 智能选股系统 - 一键启动脚本（Mac/Unix版本）

echo "======================================"
echo "    智能选股系统 - 启动中..."
echo "======================================"
echo ""

# 检查Python版本
echo "[1/4] 检查Python环境..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✓ Python版本: $PYTHON_VERSION"
else
    echo "✗ 错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 检查是否在项目目录
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "✗ 错误: 请在stock-selector目录下运行此脚本"
    exit 1
fi

# 检查后端依赖
echo ""
echo "[2/4] 检查后端依赖..."
if python3 -c "import fastapi" 2>/dev/null; then
    echo "✓ 后端依赖已安装"
else
    echo "⚠ 后端依赖未安装，正在安装..."
    cd backend
    pip3 install -r requirements.txt -q
    if [ $? -eq 0 ]; then
        echo "✓ 后端依赖安装成功"
    else
        echo "✗ 后端依赖安装失败，请手动执行: pip3 install -r requirements.txt"
        exit 1
    fi
    cd ..
fi

# 检查端口是否被占用
echo ""
echo "[3/4] 检查端口..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠ 端口8000已被占用，请先停止占用该端口的进程"
    echo "  提示: 可以使用 'lsof -i :8000' 查看占用进程"
    read -p "是否继续启动？（y/n）: " continue_choice
    if [ "$continue_choice" != "y" ]; then
        exit 1
    fi
else
    echo "✓ 端口8000可用"
fi

if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠ 端口3000已被占用，请先停止占用该端口的进程"
    echo "  提示: 可以使用 'lsof -i :3000' 查看占用进程"
    read -p "是否继续启动？（y/n）: " continue_choice
    if [ "$continue_choice" != "y" ]; then
        exit 1
    fi
else
    echo "✓ 端口3000可用"
fi

# 启动服务
echo ""
echo "[4/4] 启动服务..."

# 启动后端
echo "启动后端服务..."
cd backend
nohup python3 main.py > ../backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../backend.pid
cd ..

# 等待后端启动
sleep 2

# 检查后端是否启动成功
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo "✓ 后端服务启动成功 (PID: $BACKEND_PID)"
else
    echo "✗ 后端服务启动失败，请查看 backend.log"
    exit 1
fi

# 启动前端
echo "启动前端服务..."
cd frontend
nohup python3 -m http.server 3000 > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../frontend.pid
cd ..

# 等待前端启动
sleep 1

# 检查前端是否启动成功
if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "✓ 前端服务启动成功 (PID: $FRONTEND_PID)"
else
    echo "✗ 前端服务启动失败，请查看 frontend.log"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "======================================"
echo "✓ 启动完成！"
echo "======================================"
echo ""
echo "访问地址: http://localhost:3000"
echo "后端API:  http://localhost:8000"
echo ""
echo "日志文件:"
echo "  - backend.log  (后端日志)"
echo "  - frontend.log (前端日志)"
echo ""
echo "停止服务: ./stop.sh"
echo ""

# 自动打开浏览器（Mac）
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2
    open http://localhost:3000
fi
