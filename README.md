# AlgoStudio

AI 算法平台，支持算法自我迭代进化和多机调度训练。

## 特性

- **Ray 集群调度** - 多机 GPU 训练自动调度
- **算法仓库** - 统一的算法接口规范和版本管理
- **任务管理** - 训练/推理/验证任务提交和追踪
- **主机监控** - CPU/GPU/内存/磁盘状态监控
- **AI 集成** - Multi-Agent 自动迭代进化（Phase 2）
- **Git 协作** - 演进日志和实验记录版本化管理（Phase 2）

## 快速开始

### 环境变量配置

复制 `env.example` 为 `env` 并填入必要配置：

```bash
cp env.example env
# 编辑 env 文件填入 GITHUB_TOKEN_ID
```

**env 文件格式：**
```
GITHUB_TOKEN_ID=your_github_token_here
```

> ⚠️ **注意**: `env` 文件包含敏感信息，已被 `.gitignore` 忽略，请勿提交到 git！

### 环境隔离（重要！）

**使用 uv 隔离部署，不污染系统环境：**

```bash
# 创建独立 Python 环境（使用 uv）
uv venv algo-studio-env
source algo-studio-env/bin/activate

# uv 会创建 .venv 目录，通过 symlink 链接系统 Python
# 方便打包、迁移、不污染原系统环境
```

### 安装

```bash
# 激活环境后安装
uv pip install -e .

# 或者安装依赖
uv pip install -r requirements.txt
```

### 启动 Ray 集群

```bash
# Head 节点
./scripts/setup_ray_cluster.sh head

# Worker 节点
HEAD_IP=192.168.0.100 ./scripts/setup_ray_cluster.sh worker
```

### 启动 API 服务

```bash
# 设置 PYTHONPATH 以便找到 src 模块
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# 启动服务
uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000
```

### 使用 CLI

```bash
# 提交训练任务
algo task submit --type train --algo yolo --version v1.0.0 --config '{"epochs": 100}'

# 列出任务
algo task list

# 查看任务状态
algo task status task-001
```

## Web Console (Phase 2)

### 安装依赖
```bash
pip install -r requirements-web.txt
```

### 启动 Web Console
```bash
# 首先启动 API 服务器
PYTHONPATH="$(pwd)/src" python -m uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000 &

# 然后启动 Web Console
PYTHONPATH="$(pwd)/src" python -m algo_studio.web.app --host 0.0.0.0 --port 7860
```

### 访问
打开浏览器访问 http://localhost:7860

页面说明：
- **仪表盘** — 任务统计和集群概览
- **任务列表** — 查看和筛选所有任务
- **主机监控** — 实时 CPU/GPU/内存状态

## 项目结构

```
algo-studio/
├── src/algo_studio/
│   ├── api/           # FastAPI 路由
│   ├── core/          # 核心逻辑（算法接口、任务调度、Ray 客户端）
│   ├── cli/           # CLI 工具
│   └── monitor/       # 主机监控
├── tests/             # 测试
├── scripts/           # 集群初始化脚本
└── docs/              # 文档
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 启动 API（开发模式）
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
uvicorn algo_studio.api.main:app --reload
```

## License

MIT
