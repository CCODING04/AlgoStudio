# Phase 2.3 反馈

## Hosts/Deploy 页面

### 设计评估

设计文档整体质量较高，具有以下优点：
- 完整的 ASCII mockups，清晰展示 UI 布局
- 组件清单详细，职责划分明确
- 状态管理方案合理（React Query + Zustand）
- SSE 实时更新架构设计合理

但存在以下问题需要确认：

### 实现建议

**1. API 端点存在性确认**
以下端点在当前后端可能不存在，需要 @backend-engineer 确认：
- `GET /api/hosts/{id}/history` - 部署历史
- `GET /api/hosts/{id}/stream` - SSE 实时状态
- `GET /api/hosts/{id}/logs` - SSE 日志流
- `POST /api/deploy` - 部署触发
- `GET /api/algorithms` - 算法列表

**2. xterm.js 导入路径**
文档中使用 `@xterm/xterm`，但正确包名是 `xterm` 或 `@xterm/js`。需要确认实际使用的包。

**3. SSE 重连机制**
`useHostSSE` 依赖浏览器自动重连，建议添加手动重连计数和退避策略，避免无限重试。

**4. LogViewer SSE 清理**
代码中 `eventSource.onerror` 设置错误后没有关闭连接，建议添加 `onerror` 处理关闭连接。

### 依赖关系

**后端 API 依赖（按优先级）：**

| 优先级 | 端点 | 前端组件 | 备注 |
|--------|------|----------|------|
| P0 | `GET /api/hosts` | HostCard | 已存在 |
| P0 | `POST /api/deploy` | DeployProgress | 关键路径 |
| P1 | `GET /api/hosts/{id}/stream` | useHostSSE | 实时监控 |
| P1 | `GET /api/algorithms` | AlgorithmSelect | 部署向导 |
| P2 | `GET /api/hosts/{id}/history` | HistoryTable | Week 5 下旬 |
| P2 | `GET /api/hosts/{id}/logs` | LogViewer | Week 5 下旬 |

**建议：** Week 5 上半月优先实现 Host List + Deploy Wizard，这些功能依赖较少的端点。History/Logs 功能可以 Week 5 下半月或 Week 6 再开始。

### 甘特图调整建议

当前甘特图顺序合理，但建议拆分：
- **Week 5 上半月（2-3天）：** Host List Page 基础功能
- **Week 5 上半月（2-3天）：** Deploy Wizard 基础功能
- **Week 5 下半月（2天）：** Deploy Progress + SSE 集成
- **Week 6（3-4天）：** History Page + LogViewer

**关键路径：** Deploy Wizard 依赖 `GET /api/algorithms` 和 `POST /api/deploy`，需要后端优先实现。

### 其他

**1. 路由冲突风险**
文档中 `app/api/proxy/hosts/[hostId]/stream/route.ts` 作为 SSE 代理，但如果 Next.js 同时有 `app/api/hosts/[hostId]/stream/route.ts`，会产生路由冲突。建议统一命名。

**2. `useAlgorithms` Hook 未定义**
Deploy Page 使用了 `useAlgorithms` hook，但文档中未提供实现。需要补充或在实现时与 @coordinator 确认接口。

**3. 建议建立前端-后端接口确认机制**
Phase 2.3 涉及多个新 API 端点，建议在实现前与 @backend-engineer 对齐接口 Schema（Request/Response 格式），避免返工。
