# Phase 3.3 操作手册与文档完善计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 完善项目文档，编写算法工程师操作手册，确保项目可部署、可操作

**Architecture:** 分为三个子系统：1) 算法挂载部署手册 2) Web Console 用户手册 3) Git 提交与文档整理

**Tech Stack:** Markdown文档, Python示例代码, Shell脚本

---

## 文件结构

### 需要创建的文件

| 文件 | 职责 |
|------|------|
| `docs/ALGORITHM_DEPLOYMENT.md` | 算法挂载与部署完整手册 |
| `docs/USER_MANUAL.md` | Web Console 用户操作手册 |
| `docs/QUICK_START.md` | 快速开始指南 |
| `scripts/setup_algorithm.sh` | 算法一键部署脚本 |
| `examples/algorithms/simple_classifier/` | 示例算法完整代码 |

### 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `docs/superpowers/schedule/schedule.md` | 更新 Phase 3.2 状态，添加 Phase 3.3 计划 |
| `src/algo_studio/core/algorithm.py` | 确保接口与文档一致 |

---

## Task 1: 创建快速开始指南

**Files:**
- Create: `docs/QUICK_START.md`

- [ ] **Step 1: 创建快速开始文档**

```markdown
# AlgoStudio 快速开始指南

## 5分钟快速体验

### 1. 启动集群
```bash
# Head 节点
ray stop && ray start --head --port=6379 --object-store-memory=5368709120

# 启动 API
cd ~/Code/Dev/AlgoStudio
PYTHONPATH=src .venv/bin/python -m uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000
```

### 2. 访问 Web Console
打开浏览器访问 http://localhost:3000

> 注意：Web Console 运行在 3000 端口，API 服务运行在 8000 端口

### 3. 查看集群状态
在 Web Console 的「主机监控」页面查看所有节点状态。

### 4. 提交训练任务
1. 进入「任务管理」页面
2. 点击「新建任务」
3. 选择算法、配置参数
4. 提交训练任务
5. 实时观察训练进度

## 下一步
- [算法部署手册](ALGORITHM_DEPLOYMENT.md) - 了解如何部署自己的算法
- [用户手册](USER_MANUAL.md) - 完整功能介绍
```

- [ ] **Step 2: Commit**

```bash
git add docs/QUICK_START.md
git commit -m "docs: add quick start guide"
```

---

## Task 2: 创建算法部署手册

**Files:**
- Create: `docs/ALGORITHM_DEPLOYMENT.md`

- [ ] **Step 1: 编写算法接口规范章节**

```markdown
# 算法挂载与部署手册

## 1. 算法接口规范

AlgoStudio 平台使用 Duck Typing 算法接口，任何实现以下方法的类都可以被平台调度：

### 1.1 必须实现的方法

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `train(data_path, config, progress_callback)` | `TrainResult` | 训练模型 |
| `infer(inputs)` | `InferenceResult` | 模型推理 |
| `verify(test_data)` | `VerificationResult` | 模型验证 |
| `get_metadata()` | `AlgorithmMetadata` | 算法元信息 |

### 1.2 数据类定义

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class TrainResult:
    success: bool
    model_path: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@dataclass
class InferenceResult:
    success: bool
    outputs: Optional[List[Dict[str, Any]]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None

@dataclass
class VerificationResult:
    success: bool
    passed: bool
    metrics: Optional[Dict[str, Any]] = None
    details: Optional[str] = None

@dataclass
class AlgorithmMetadata:
    name: str
    version: str
    task_type: str  # 如 "object_detection", "classification"
    deployment: str  # "edge" 或 "cloud"
    expected_fps: Optional[int] = None
```

### 1.3 进度回调接口

训练过程中可通过 `progress_callback` 报告进度（这是 AlgoStudio 扩展的参数，平台会传递）：

```python
class ProgressCallback:
    def update(self, current: int, total: int, description: str = ""):
        """更新进度

        Args:
            current: 当前进度值
            total: 总进度值
            description: 进度描述（如 "Epoch 3/10"）
        """
        pass

    def set_description(self, description: str):
        """设置进度描述"""
        pass
```

**注意**: `progress_callback` 是 AlgoStudio 平台扩展的参数。虽然 `AlgorithmInterface` 基类未定义此参数，但平台实际调用时会传递该参数。算法实现中应接受此参数以支持进度报告。

## 2. 算法目录结构

```
algorithms/
└── <algorithm_name>/
    └── <version>/
        ├── __init__.py      # 算法类定义
        ├── train.py          # 训练逻辑（可选）
        ├── infer.py          # 推理逻辑（可选）
        └── requirements.txt   # 依赖包
```

## 3. 示例：简单分类器

### 3.1 完整代码

创建 `examples/algorithms/simple_classifier/v1/__init__.py`：

```python
"""简单图像分类器示例"""
from typing import Any, Dict, List, Optional
import time

# 从 AlgoStudio 导入结果类
from algo_studio.core.algorithm import (
    TrainResult,
    InferenceResult,
    VerificationResult,
    AlgorithmMetadata
)

class SimpleClassifier:
    """简单分类器算法实现"""

    def __init__(self):
        self.model = None
        self.classes = ["cat", "dog", "bird"]

    def train(self, data_path: str, config: dict, progress_callback=None) -> TrainResult:
        """训练分类模型"""
        try:
            epochs = config.get("epochs", 10)
            batch_size = config.get("batch_size", 32)

            for epoch in range(epochs):
                # 模拟训练
                time.sleep(0.1)

                # 报告进度
                if progress_callback:
                    progress_callback.update(
                        current=epoch + 1,
                        total=epochs,
                        description=f"Epoch {epoch+1}/{epochs}"
                    )

            return TrainResult(
                success=True,
                model_path=f"{data_path}/model.pth",
                metrics={"accuracy": 0.95, "loss": 0.05}
            )
        except Exception as e:
            return TrainResult(success=False, error=str(e))

    def infer(self, inputs: List[Any]) -> InferenceResult:
        """推理预测"""
        try:
            outputs = []
            for inp in inputs:
                # 模拟推理
                outputs.append({
                    "class": self.classes[hash(inp) % 3],
                    "confidence": 0.9
                })

            return InferenceResult(
                success=True,
                outputs=outputs,
                latency_ms=10.5
            )
        except Exception as e:
            return InferenceResult(success=False, error=str(e))

    def verify(self, test_data: str) -> VerificationResult:
        """验证模型"""
        return VerificationResult(
            success=True,
            passed=True,
            metrics={"accuracy": 0.93},
            details="所有测试样本通过"
        )

    @staticmethod
    def get_metadata() -> AlgorithmMetadata:
        return AlgorithmMetadata(
            name="simple_classifier",
            version="v1",
            task_type="classification",
            deployment="cloud",
            expected_fps=100
        )
```

### 3.2 requirements.txt

```
torch
torchvision
```

## 4. 部署算法到平台

### 4.1 手动部署

1. 将算法代码复制到 `algorithms/` 目录
2. 确保目录结构正确
3. 重启 API 服务使算法生效

### 4.2 使用部署脚本

```bash
./scripts/setup_algorithm.sh <algorithm_name> <version> <source_path>

# 示例
./scripts/setup_algorithm.sh simple_classifier v1 ./examples/algorithms/simple_classifier/
```

## 5. 训练任务示例

### 5.1 通过 Web Console

1. 打开「任务管理」→「新建任务」
2. 选择算法：`simple_classifier:v1`
3. 任务类型：`train`
4. 数据路径：`/mnt/VtrixDataset/data/train`
5. 配置参数：
```json
{
  "epochs": 10,
  "batch_size": 32
}
```
6. 点击「提交」

### 5.2 通过 API

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "train",
    "algorithm_name": "simple_classifier",
    "algorithm_version": "v1",
    "data_path": "/mnt/VtrixDataset/data/train",
    "config": {"epochs": 10, "batch_size": 32}
  }'
```

## 6. 推理任务示例

### 6.1 提交推理任务

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "infer",
    "algorithm_name": "simple_classifier",
    "algorithm_version": "v1",
    "inputs": ["image1.jpg", "image2.jpg"]
  }'
```

## 7. 常见问题

### Q: 算法无法被平台识别？

检查：
1. 算法类是否实现了所有必需方法
2. `get_metadata()` 是否返回正确的 `AlgorithmMetadata`
3. API 服务是否已重启

### Q: 训练进度不更新？

检查：
1. `progress_callback` 是否正确传递
2. `progress_callback.update()` 是否被调用

## 8. 故障排除指南

详细故障排除见：[Sentinel 故障转移修复文档](../security/SENTINEL-FAILOVER-FIX.md)

### 8.1 Ray 集群问题

#### Q: Worker 无法连接到 Head 节点

```
Failed to connect to GCS at address 192.168.0.126:6379
```

解决：
1. 检查 Head 节点 Ray 是否启动：`ray status`
2. 检查网络连通性：`ping 192.168.0.126`
3. 检查防火墙：`sudo ufw status`

#### Q: Python 版本不匹配

```
RuntimeError: Version mismatch
```

解决：
```bash
# 查看 Head 节点 Python 版本
~/.venv/bin/python --version
# 在 Worker 节点使用相同版本
PYTHON_BIN=/usr/bin/python3.10 bash scripts/join_cluster.sh 192.168.0.126
```

### 8.2 GPU 问题

#### Q: GPU 不可见

解决：
1. 检查 nvidia-smi：`nvidia-smi`
2. 检查 pynvml：`python -c "import pynvml; pynvml.nvmlInit()"`
3. 重新安装 GPU 驱动

### 8.3 任务问题

#### Q: 任务一直处于 pending 状态

可能原因：
1. 没有可用节点
2. 资源不足
3. 调度器配置问题

解决：
1. 检查节点状态：`ray status`
2. 查看调度日志
3. 检查 quota 配置
```

- [ ] **Step 2: 创建示例算法目录**

创建 `examples/algorithms/simple_classifier/v1/` 及完整代码

- [ ] **Step 3: Commit**

```bash
git add docs/ALGORITHM_DEPLOYMENT.md examples/algorithms/
git commit -m "docs: add algorithm deployment guide with example"
```

---

## Task 3: 创建 Web Console 用户手册

**Files:**
- Create: `docs/USER_MANUAL.md`

- [ ] **Step 1: 编写用户手册**

```markdown
# AlgoStudio Web Console 用户手册

## 1. 概述

AlgoStudio Web Console 是可视化集群管理界面，支持：
- 集群状态监控
- 任务提交与管理
- 主机资源查看
- 部署管理

访问地址：http://localhost:3000

> 注意：Web Console (Next.js) 运行在 3000 端口，API 服务运行在 8000 端口

## 2. 导航栏

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo] AlgoStudio    首页  |  任务  |  主机  |  部署      │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 首页 (Dashboard)
- 集群状态概览
- 近期任务
- 资源使用图表

### 2.2 任务管理 (Tasks)
- 查看所有任务
- 创建新任务
- 查看任务详情和日志

### 2.3 主机监控 (Hosts)
- 查看所有节点
- CPU/GPU/内存状态
- 节点详情

### 2.4 部署管理 (Deploy)
- 算法部署
- 部署历史
- 回滚操作

## 3. 任务管理

### 3.1 创建训练任务

1. 点击「新建任务」按钮
2. 填写任务信息：
   - **任务名称**：输入任务标识名
   - **任务类型**：选择 `train`/`infer`/`verify`
   - **算法**：选择已部署的算法
   - **数据路径**：数据集存储路径
   - **配置参数**：JSON 格式的训练参数

3. 点击「提交」

### 3.2 查看任务状态

任务列表显示：
| 状态 | 含义 |
|------|------|
| `pending` | 等待调度 |
| `running` | 正在执行 |
| `completed` | 已完成 |
| `failed` | 执行失败 |
| `cancelled` | 已取消 |

### 3.3 任务详情

点击任务查看：
- 基本信息（算法、数据路径、配置）
- 实时进度条
- 执行日志
- 性能指标

## 4. 主机监控

### 4.1 节点列表

显示所有节点：
- **Head**：主节点（蓝色标识）
- **Worker**：工作节点

### 4.2 资源信息

每个节点显示：
- CPU：型号、核心数、使用率
- GPU：型号、显存、使用率
- 内存：总容量、使用率
- 磁盘：使用率

## 5. 部署管理

### 5.1 部署算法

1. 点击「部署新算法」
2. 选择算法文件和配置
3. 确认部署
4. 等待部署完成

### 5.2 查看部署历史

- 列出所有历史部署
- 显示部署时间和状态
- 支持回滚到指定版本

## 6. 常见操作流程

### 6.1 完整训练流程

1. **准备数据**
   - 将训练数据放入 `/mnt/VtrixDataset/data/train`

2. **提交训练任务**
   - 进入「任务」→「新建任务」
   - 选择算法和参数
   - 提交训练

3. **监控进度**
   - 在任务列表查看进度
   - 点击任务查看详细日志

4. **获取结果**
   - 训练完成后查看模型路径
   - 使用模型进行推理

### 6.2 推理流程

1. **提交推理任务**
   - 选择算法
   - 输入待推理数据路径
   - 提交推理

2. **获取结果**
   - 查看推理输出
   - 下载结果文件
```

- [ ] **Step 2: Commit**

```bash
git add docs/USER_MANUAL.md
git commit -m "docs: add web console user manual"
```

---

## Task 4: 更新项目甘特图

**Files:**
- Modify: `docs/superpowers/schedule/schedule.md`

- [ ] **Step 1: 更新 Phase 3.2 状态并添加 Phase 3.3**

```markdown
## Phase 3.2 进度 (测试改进轮次)

### Phase 3.2 目标
1. 整体覆盖率 80%+ ✅ (已达 85%)
2. audit.py 60%+ ✅ (已达 96.55%)
3. tasks.py 60%+ ✅ (已达 86%)
4. Sentinel 故障转移验证 ✅ (自动 failover 成功)

### Phase 3.2 Round 进度

| Round | 状态 | 主要成果 |
|-------|------|----------|
| Round 1 | ✅ | tasks.py SSE测试, Sentinel配置 |
| Round 2 | ✅ | Scheduler 161 tests, MockTask修复 |
| Round 3 | ✅ | core/task.py 80%, core/ray_client.py 84% |
| Round 4 | ✅ | routing 100%, scorers 93% |
| Round 5 | ✅ | auth.py 100%, deep_path_agent 94% |
| Round 6 | ✅ | ray_dashboard 93%, deploy 77%, fast_scheduler 85% |
| Round 7 | ✅ | 核心代码覆盖率 85%, 975 tests PASS |
| Round 8 | ✅ | Sentinel 自动故障转移验证成功 |

---

## Phase 3.3: 操作手册与文档完善

### Phase 3.3 目标
1. 完善算法部署手册 ✅
2. 完善用户操作手册 ✅
3. Git 提交 Phase 3.2 成果
4. 示例算法完整可运行

### Phase 3.3 甘特图

```
周次    │ W1 │
────────┼────┤
文档完善 │████│
算法示例 │████│
Git提交  │████│
```

### Phase 3.3 任务

| 任务 | 状态 | 负责人 |
|------|------|--------|
| 快速开始指南 | ✅ | docs/QUICK_START.md |
| 算法部署手册 | ✅ | docs/ALGORITHM_DEPLOYMENT.md |
| 用户操作手册 | ✅ | docs/USER_MANUAL.md |
| 示例算法 | 🔄 | examples/algorithms/ |
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/schedule/schedule.md
git commit -m "docs: update schedule with Phase 3.2 completion and Phase 3.3 plan"
```

---

## Task 5: 创建示例算法完整代码

**Files:**
- Create: `examples/algorithms/simple_classifier/v1/`

- [ ] **Step 1: 创建示例算法**

```python
# examples/algorithms/simple_classifier/v1/__init__.py
"""简单图像分类器示例算法"""
# ... 完整代码 ...
```

- [ ] **Step 2: 创建 requirements.txt**

```
torch
torchvision
numpy
```

- [ ] **Step 3: 创建 README.md**

```markdown
# Simple Classifier 示例算法

## 使用方法

1. 部署到平台
2. 提交训练任务
3. 等待训练完成
4. 使用模型进行推理

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| epochs | int | 10 | 训练轮数 |
| batch_size | int | 32 | 批大小 |
| learning_rate | float | 0.001 | 学习率 |
```

- [ ] **Step 4: Commit**

```bash
git add examples/algorithms/simple_classifier/
git commit -m "feat: add simple_classifier example algorithm"
```

---

## Task 6: 提交 Phase 3.2 成果

- [ ] **Step 1: 检查所有修改**

```bash
git status
```

- [ ] **Step 2: 提交 Phase 3.2**

```bash
git add -A
git commit -m "feat: Phase 3.2 complete - 85% coverage, Sentinel HA verified

- 整体测试覆盖率从 55% 提升至 85%
- audit.py 覆盖率 96.55%
- tasks.py 覆盖率 86%
- Sentinel 自动故障转移验证成功
- 新增测试文件:
  - tests/unit/scheduler/test_wfq_scheduler.py
  - tests/unit/scheduler/test_agentic_scheduler.py
  - tests/unit/core/test_ray_dashboard_client.py
  - tests/unit/api/test_auth.py

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## 执行选项

**1. Subagent-Driven (recommended)** - 每个 Task 由独立 subagent 执行
**2. Inline Execution** - 当前 session 内批量执行

建议选择 Subagent-Driven，可以快速并行执行多个任务。
