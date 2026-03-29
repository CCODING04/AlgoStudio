# AlgoStudio 快速开始指南

5 分钟快速体验 AlgoStudio AI 算法平台。

## 环境要求

- Python 3.10+
- Node.js 18+
- Ray 2.54.0
- NVIDIA GPU (可选,用于GPU训练)

## 第一步：环境准备

```bash
# 克隆代码
git clone https://github.com/CCODING04/AlgoStudio.git
cd AlgoStudio

# 创建 Python 虚拟环境 (使用 uv)
uv venv .venv
source .venv/bin/activate

# 安装项目依赖
uv pip install -e .

# 安装 PyTorch (如需GPU支持)
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

## 第二步：启动 Ray 集群

### 在 Head 节点启动 (192.168.0.126)

```bash
# 停止现有 Ray 实例 (如有必要)
ray stop

# 启动 Ray Head 节点
~/Code/Dev/AlgoStudio/.venv/bin/ray start --head --port=6379 --object-store-memory=5368709120

# 验证集群状态
ray status
```

### 在 Worker 节点加入 (192.168.0.115)

```bash
# 在 Worker 节点执行
cd ~/Code/AlgoStudio
source .venv-ray/bin/activate
bash scripts/join_cluster.sh 192.168.0.126
```

## 第三步：初始化数据库

```bash
# 初始化数据库表
cd /home/admin02/Code/Dev/AlgoStudio
PYTHONPATH=src .venv/bin/python << 'EOF'
from algo_studio.db.session import db
from algo_studio.db.models.base import Base
import asyncio

async def init_db():
    db.init()
    async with db._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully")

asyncio.run(init_db())
EOF
```

## 第四步：启动 API 服务

```bash
# 设置 API 认证密钥 (必须设置，否则 API 调用被拒绝)
export RBAC_SECRET_KEY='your-secret-key-here'

# 在 Head 节点新终端执行
cd /home/admin02/Code/Dev/AlgoStudio
PYTHONPATH=src .venv/bin/uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000
```

API 服务启动后验证:

```bash
curl http://localhost:8000/api/health
```

## 第四步：启动 Web Console

```bash
# 在 Head 节点另一个终端执行
cd /home/admin02/Code/Dev/AlgoStudio/src/frontend
npm install
npm run dev
```

## 第五步：访问 Web Console

打开浏览器访问: **http://localhost:3000**

Web Console 功能:
- **仪表盘** - 任务统计和集群概览
- **任务列表** - 查看和管理所有训练/推理/验证任务
- **主机监控** - 实时 CPU/GPU/内存/磁盘状态

## 第七步：提交训练任务

### 通过 Web Console 提交

1. 访问 http://localhost:3000
2. 点击「任务列表」
3. 点击「新建任务」
4. 选择任务类型、算法和配置
5. 提交任务

### 通过 API 提交

```bash
# 设置认证参数
USER_ID="test-user"
TIMESTAMP=$(date +%s)
SECRET="your-secret-key-here"
MSG="${USER_ID}:${TIMESTAMP}"
SIGNATURE=$(echo -n "$MSG" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

# 提交训练任务
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Signature: $SIGNATURE" \
  -H "X-User-Role: admin" \
  -d '{
    "task_type": "train",
    "algorithm_name": "simple_classifier",
    "algorithm_version": "v1",
    "config": {
      "epochs": 10,
      "batch_size": 32
    }
  }'

# 分发任务到 Ray 集群执行
# 注意：任务提交后需要手动分发
curl -X POST http://localhost:8000/api/tasks/<task_id>/dispatch \
  -H "X-User-ID: $USER_ID" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Signature: $SIGNATURE" \
  -H "X-User-Role: admin"
```

### 通过 CLI 提交

```bash
# 提交训练任务
algo task submit --type train --algo simple_classifier --version v1 --config '{"epochs": 10}'

# 查看任务列表
algo task list

# 查看任务状态
algo task status <task_id>
```

## 常用命令

### Ray 集群管理

```bash
# 查看集群状态
ray status

# 查看所有节点
ray nodes

# 停止 Ray
ray stop

# 重启 Ray Head
ray stop && ray start --head --port=6379 --object-store-memory=5368709120
```

### 查看任务进度

```bash
# 通过 API 查看任务详情
curl http://localhost:8000/api/tasks/<task_id>

# 通过 SSE 流式查看进度
curl -N http://localhost:8000/api/tasks/<task_id>/progress
```

### 查看主机状态

```bash
curl http://localhost:8000/api/hosts
```

## 算法目录结构

```
algorithms/
└── <algorithm_name>/
    └── <version>/
        ├── train.py      # 训练逻辑
        ├── infer.py      # 推理逻辑
        ├── verify.py     # 验证逻辑
        └── metadata.json # 算法元信息
```

## 常见问题

### Q: Ray 连接失败

确保 Head 节点 Ray 已启动:
```bash
ray status
```

### Q: Worker 节点无法加入

检查网络连通性和 Head 节点 6379 端口是否开放。

### Q: GPU 不可用

确保 Worker 节点已安装 nvidia-driver 和 nvidia-container-runtime。

### Q: API 启动报错 "Task | None"

确保使用 Python 3.10+:
```bash
python --version  # 应显示 3.10.x
```

## 下一步

- 阅读 [完整文档](docs/superpowers/) 了解高级功能
- 查看 [集群部署指南](docs/cluster-deployment.md) 了解多节点部署
- 查看 [API 设计文档](docs/superpowers/research/backend-phase2-report.md) 了解 API 详情
