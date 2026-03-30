# 智能选股系统 - 部署说明

## 系统概述

这是一个基于 AKShare 的网页版选股软件，提供以下功能：
- 实时行情展示
- 多条件股票筛选
- 个股详情分析
- 策略回测

**数据来源：** 所有数据均来自 AKShare（真实数据，不造假）

## 技术栈

- **后端：** Python FastAPI + AKShare
- **前端：** Vue 3 + Element Plus + ECharts
- **部署：** 本地运行（Mac/Windows/Linux 通用）

## 快速开始（Mac笔记本）

### 1. 系统要求

- Python 3.8 或以上
- pip（Python包管理器）
- 浏览器（Chrome/Safari/Firefox）

### 2. 安装依赖

打开终端，进入项目目录：

```bash
cd stock-selector
```

安装后端依赖：

```bash
cd backend
pip3 install -r requirements.txt
cd ..
```

### 3. 启动服务

使用一键启动脚本：

```bash
chmod +x start.sh
./start.sh
```

或手动启动：

**启动后端（第一个终端窗口）：**
```bash
cd backend
python3 main.py
```

**启动前端（第二个终端窗口）：**
```bash
cd frontend
python3 -m http.server 3000
```

### 4. 访问系统

打开浏览器，访问：http://localhost:3000

### 5. 停止服务

在终端按 `Ctrl + C` 停止服务

## 功能说明

### 1. 市场概览
- 实时显示上证指数、深证成指、创业板指
- 显示涨停数、跌停数
- 热门板块资金流向

### 2. 股票筛选
- 按价格区间筛选
- 按涨跌幅筛选
- 按市盈率、市净率筛选
- 支持多条件组合筛选

### 3. 个股详情
- 股票基本信息（名称、行业、市值等）
- K线图展示（日线/周线/月线）
- 可缩放查看历史数据

### 4. 策略回测
- 预设4种选股策略：
  - 趋势跟踪策略
  - 突破形态策略
  - 价值低估策略
  - 量价配合策略
- 显示回测结果：总收益率、年化收益、最大回撤、夏普比率、胜率等
- 详细的交易记录

## 端口说明

- 前端端口：3000
- 后端端口：8000

如果端口被占用，可以修改：
- 后端端口：编辑 `backend/main.py` 最后一行的 `port=8000`
- 前端端口：启动时使用 `python3 -m http.server 你的端口`

## 常见问题

### 1. 无法访问页面
- 检查后端和前端服务是否都启动了
- 尝试访问 http://127.0.0.1:3000
- 检查防火墙设置

### 2. 数据加载失败
- 检查网络连接（AKShare需要联网）
- 检查后端日志是否有错误
- 尝试重启后端服务

### 3. Python依赖安装失败
- 尝试使用国内镜像源：
  ```bash
  pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

### 4. macOS权限问题
如果提示权限不足，请给脚本执行权限：
```bash
chmod +x start.sh
chmod +x stop.sh
```

## 文件结构

```
stock-selector/
├── README.md           # 本说明文档
├── start.sh            # 一键启动脚本
├── stop.sh             # 一键停止脚本
├── backend/            # 后端代码
│   ├── main.py         # FastAPI主程序
│   └── requirements.txt # Python依赖
└── frontend/           # 前端代码
    └── index.html      # 单页面应用
```

## 更新日志

### v1.0.0 (2026-03-17)
- 初始版本发布
- 支持实时行情、股票筛选、个股详情、策略回测
- 所有数据来自AKShare真实数据

## 技术支持

如有问题，请检查：
1. Python版本是否正确
2. 依赖是否完整安装
3. 网络连接是否正常
4. 端口是否被占用

---

**开发时间：** 2026-03-17  
**数据来源：** AKShare（开源免费）
