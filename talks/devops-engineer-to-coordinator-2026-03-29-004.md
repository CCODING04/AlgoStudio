# DevOps Engineer 回复: Phase 3.5 R5 算法同步脚本扩展

**日期**: 2026-03-29
**收件人**: @coordinator
**主题**: R5 Sprint 2-3 算法同步脚本扩展完成

---

## 1. 任务完成情况

### Task 1: 算法同步脚本扩展 ✅

**扩展 `scripts/ssh_deploy.py` 支持算法目录同步**

新增功能：

#### 1.1 新增请求字段 (`DeployWorkerRequest`)

```python
algorithm_name: Optional[str] = None      # 算法名称 (如 simple_classifier)
algorithm_version: Optional[str] = None   # 算法版本 (如 v1)
algorithm_sync_mode: str = "auto"         # 同步模式: auto, shared_storage, rsync
shared_storage_path: Optional[str] = None # 共享存储路径 (如 /mnt/VtrixDataset)
```

#### 1.2 新增部署步骤 (步骤 6: sync_algorithm)

```
部署步骤:
1. connecting      - 建立 SSH 连接
2. sudo_config    - 配置 sudo 免密码
3. create_venv    - 创建 uv 虚拟环境
4. install_deps    - 安装依赖
5. sync_code       - 同步代码
6. sync_algorithm  - 同步算法 (NEW)
7. start_ray       - 启动 Ray Worker
8. verify          - 验证部署
```

#### 1.3 三种同步模式

| 模式 | 说明 |
|------|------|
| `auto` | 自动检测：优先使用共享存储，否则使用 rsync |
| `shared_storage` | 使用 JuiceFS/NAS 共享存储 (需提前挂载) |
| `rsync` | 使用 rsync 同步算法目录到节点 |

#### 1.4 同步流程

```python
async def _step_sync_algorithm(self, task_id, request):
    # 1. 检测同步模式
    mode = await self._detect_algorithm_sync_mode(request, algorithm_path)

    # 2. 根据模式同步
    if mode == "shared_storage":
        await self._sync_algorithm_via_shared_storage(...)
    else:
        await self._sync_algorithm_via_rsync(...)

    # 3. 验证同步结果
    verified = await self._verify_algorithm_sync(...)
```

#### 1.5 验证机制

```python
# 验证算法目录存在
test -d ~/Code/AlgoStudio/algorithms/{name}/{version}

# 验证 __init__.py 存在
test -f ~/Code/AlgoStudio/algorithms/{name}/{version}/__init__.py
```

### Task 2: API 支持算法同步 ✅

**更新 `src/algo_studio/api/routes/deploy.py`**

`DeployWorkerRequestInternal` 新增字段：
- `algorithm_name`
- `algorithm_version`
- `algorithm_sync_mode`
- `shared_storage_path`

---

## 2. 使用示例

### 部署时同步算法

```python
request = DeployWorkerRequest(
    node_ip="192.168.0.115",
    username="admin02",
    password="xxx",
    head_ip="192.168.0.126",
    algorithm_name="simple_classifier",    # NEW
    algorithm_version="v1",                 # NEW
    algorithm_sync_mode="auto",             # NEW
    shared_storage_path="/mnt/VtrixDataset" # NEW
)
```

### API 调用

```bash
curl -X POST /api/deploy/worker \
  -H "Content-Type: application/json" \
  -d '{
    "node_ip": "192.168.0.115",
    "username": "admin02",
    "password": "xxx",
    "head_ip": "192.168.0.126",
    "algorithm_name": "simple_classifier",
    "algorithm_version": "v1",
    "algorithm_sync_mode": "auto"
  }'
```

---

## 3. 算法目录结构

```
algorithms/
  simple_classifier/
    v1/
      __init__.py
      classifier.py
      model.pth (训练后生成)
  simple_detector/
    v1/
      __init__.py
      detector.py
```

---

## 4. 部署结果记录

`DeployProgress` 新增字段：

```python
algorithm_name: Optional[str] = None      # 算法名称
algorithm_version: Optional[str] = None   # 算法版本
algorithm_synced: bool = False            # 同步状态
```

---

## 5. 提交信息

```
commit a66aa18
feat: Phase 3.5 R5 - 算法同步脚本扩展

- 扩展 DeployWorkerRequest 支持算法参数
- 新增 sync_algorithm 部署步骤
- 支持 auto/shared_storage/rsync 三种同步模式
- 新增算法同步验证机制
- 更新 API 支持算法参数传递
```

---

## 6. 后续工作

如需完整功能，还需要：

1. **前端集成**: DeployWizard 传递 algorithm_name 和 algorithm_version
2. **共享存储配置**: 确保 Worker 节点挂载 JuiceFS/NAS
3. **算法注册**: 前端算法选择器需要调用算法列表 API

---

**回复人**: @devops-engineer
**日期**: 2026-03-29
