# AlgoStudio Web Console 问题修复计划

**日期**: 2026-03-31
**状态**: 待规划
**优先级**: P0

---

## 问题概述

当前 Web Console 存在以下关键问题需要修复：

| # | 问题 | 影响 | 优先级 |
|---|------|------|---------|
| 1 | Datasets 功能无法选择服务器上的实际文件夹 | 无法使用已有数据集 | P0 |
| 2 | Deploy 创建 Worker 失败 | 无法部署算法到 Worker 节点 | P0 |
| 3 | 待处理任务无法正常分发 | 任务卡在 pending 状态 | P1 |

---

## 问题 1: Datasets 文件夹选择

### 用户需求

用户希望将 `/mnt/VtrixDataset/data/` 下已有的实际文件夹（COCO、CIFAR10 等）作为可选择的数据集，而不是手动输入路径。

### 当前实现

- 已有 `DatasetForm` 组件用于创建/编辑数据集
- 已有 `DatasetSelector` 组件用于在 TaskWizard 中选择数据集
- **问题**: 没有后端 API 来扫描服务器上的实际目录

### 技术方案

#### 方案 A: 新增目录浏览 API（推荐）

**后端 API**:
```python
# GET /api/datasets/browse
# Query params: path (可选，默认 /mnt/VtrixDataset/data/)
# Response: { "folders": ["cifar10", "coco", "imagenet", ...] }

# GET /api/datasets/browse?path=/custom/path
# Response: { "folders": ["train", "val", "test"], "exists": true }
```

**前端修改**:
1. 新增 `DatasetBrowser` 组件 - 展示服务器目录下的文件夹列表
2. 修改 `DatasetForm` - 添加"浏览服务器"按钮，点击后弹出文件夹选择对话框
3. 修改 `DatasetSelector` - 当数据集列表为空时，显示服务器目录下的文件夹

#### 方案 B: CLI 同步脚本

预先扫描 `/mnt/VtrixDataset/data/` 下的文件夹，自动创建数据集记录。

**优点**: 简单
**缺点**: 不是实时同步，新增文件夹需要手动运行脚本

### 实现步骤

1. [ ] 后端: 新增 `/api/datasets/browse` API
2. [ ] 前端: 新增 `DatasetBrowser` 组件
3. [ ] 前端: 修改 `DatasetForm` 集成文件夹浏览功能
4. [ ] 前端: 修改 `DatasetSelector` 空状态提示

---

## 问题 2: Deploy 创建 Worker 失败

### 错误信息

```
Failed to create deploy worker
```

### 可能原因分析

| # | 可能原因 | 排查方法 |
|---|---------|---------|
| 1 | Worker 节点未连接到 Ray 集群 | `ray status` 查看节点列表 |
| 2 | SSH 认证失败 | 检查 credential_store 中的 SSH 配置 |
| 3 | 目标目录权限问题 | 检查 `/home/admin10/Code/AlgoStudio` 目录权限 |
| 4 | 后端 API 错误 | 查看 FastAPI 日志 |
| 5 | Worker 上没有必要的依赖 | 检查 Worker Python 环境 |

### 排查清单

```bash
# 1. 检查 Ray 集群状态
ray status

# 2. 检查 Worker 节点是否在线
curl http://localhost:8000/api/hosts

# 3. 检查 Deploy API 响应
curl -X POST http://localhost:8000/api/deploy/worker \
  -H "Content-Type: application/json" \
  -d '{"node_ip": "192.168.0.115", ...}'

# 4. 检查 Worker SSH 连接
ssh admin10@192.168.0.115 "echo ok"
```

### 实现步骤

1. [ ] 排查: 确定错误根本原因
2. [ ] 修复: 根据错误原因实施修复
3. [ ] 测试: 验证 Deploy 功能正常工作

---

## 问题 3: 待处理任务分发

### 当前状态

- 已在任务详情页添加"立即分发"按钮
- 调用 `dispatchTask(taskId)` API

### 可能问题

| # | 可能原因 | 排查方法 |
|---|---------|---------|
| 1 | `dispatchTask` API 未正确实现调度逻辑 | 检查 `dispatchTask` 函数实现 |
| 2 | 调度器队列为空 | 检查 Redis/队列状态 |
| 3 | 没有可用的 Worker 节点 | 检查集群节点状态 |
| 4 | 任务分发后节点分配没有更新 | 检查 API 响应和前端更新逻辑 |

### 排查清单

```bash
# 1. 检查待处理任务列表
curl http://localhost:8000/api/tasks?status=pending

# 2. 测试手动分发
curl -X POST http://localhost:8000/api/tasks/{task_id}/dispatch

# 3. 检查任务详情
curl http://localhost:8000/api/tasks/{task_id}
```

### 实现步骤

1. [ ] 排查: 确认 dispatchTask API 是否正确实现
2. [ ] 修复: 根据错误原因实施修复
3. [ ] 测试: 验证任务可以正常分发到节点

---

## 依赖关系

```
问题 2 (Deploy)     问题 3 (任务分发)
      ↓                    ↓
┌─────────────────┬─────────────────┐
│   Worker 节点需要正常连接集群    │
└─────────────────────────────────┘
                    ↓
         问题 1 (Datasets) - 可独立实现
```

---

## 建议实施顺序

1. **问题 2 (Deploy)** - 如果 Worker 无法部署，整个平台无法工作
2. **问题 3 (任务分发)** - 依赖 Worker 节点正常
3. **问题 1 (Datasets)** - 可独立实现，提高用户体验

---

## 待用户确认

1. `/mnt/VtrixDataset/data/` 目录是否在 Head 节点 (`192.168.0.126`) 上？
2. Worker 节点 (`192.168.0.115`) 的 SSH 认证是如何配置的？
3. 是否需要支持 CIFAR10/COCO 以外的其它数据集路径？
