# M2: Ray Dashboard API 开发进度

**收件人:** 团队全员
**发件人:** @backend-engineer
**日期:** 2026-03-26
**状态:** 进行中

---

## 进度更新

M2 Ray Dashboard API 开发已启动，基础框架已完成。

### 已完成

| 组件 | 状态 | 位置 |
|------|------|------|
| RayAPIClient 封装 | 完成 | `src/algo_studio/core/ray_dashboard_client.py` |
| RayAPICompat 版本兼容 | 完成 | `src/algo_studio/core/ray_compat.py` |
| FastAPI 路由 | 完成 | `src/algo_studio/api/routes/cluster.py` |
| SSE 端点 | 完成 | `src/algo_studio/api/routes/cluster.py` (需安装 sse-starlette) |
| 熔断降级机制 | 完成 | `RayAPIClient` 内置 |
| main.py 更新 | 完成 | 集成 cluster 路由 |

### API 端点

```
GET  /api/cluster/status          # 集群综合状态
GET  /api/cluster/nodes           # 节点列表
GET  /api/cluster/nodes/{node_id} # 节点详情
GET  /api/cluster/actors          # Actor 列表
GET  /api/cluster/actors/{actor_id} # Actor 详情
GET  /api/cluster/tasks           # Task 列表
GET  /api/cluster/jobs            # Job 列表
GET  /api/cluster/health          # 健康检查
POST /api/cluster/cache/invalidate # 缓存清除
GET  /api/cluster/circuit-breaker # 熔断器状态
GET  /api/cluster/events          # SSE 实时事件流
```

### 依赖更新

- 添加 `sse-starlette>=1.6.0` 到 requirements.txt 和 pyproject.toml

### 待集成

- [ ] 与 AI Scheduling 对接 (M3)
- [ ] 单元测试

### 依赖关系

- M2 不依赖 M1，可独立进行
- M3 (Fast Path) 依赖 M2 的节点状态 API

---

**下一步计划:**
1. 安装 sse-starlette 依赖
2. 与 AI Scheduling 团队对接接口
3. 编写单元测试