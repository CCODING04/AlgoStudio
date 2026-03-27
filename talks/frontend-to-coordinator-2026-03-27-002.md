# Phase 2.3 Hosts/Deploy Pages Architecture - 设计完成

**from:** @frontend-engineer
**to:** @coordinator
**date:** 2026-03-27
**type:** notify
**ref:** Phase 2.3 Scope

---

## 任务状态：已完成

### Phase 2.3 - Hosts/Deploy 页面架构设计

## 完成内容

### 1. 架构设计文档

**文件位置:** `docs/superpowers/research/frontend-deploy-design.md`

包含以下内容：

| 章节 | 内容 |
|------|------|
| Page Layouts | 4个ASCII mockups (Host List, Deploy Wizard, Deploy Progress, History) |
| Component Inventory | 25+ 组件清单及文件路径 |
| State Management | React Query + Zustand + SSE 完整方案 |
| API Integration | 6个后端API端点定义 |
| Page Implementations | 3个页面的完整代码实现 |
| Component Details | HostCard, LogViewer, DeployProgress 详细代码 |
| Directory Structure | 完整 Next.js 项目结构 |
| Implementation Order | 6阶段实施计划 (Week 5-6) |

### 2. 页面设计概要

#### Host List Page (`/hosts`)
- 实时 GPU 状态显示 (温度、利用率、显存)
- 节点健康状态指示器 (Online/Offline/Error)
- 快速操作按钮 (Deploy, View Logs)
- SSE 实时更新

#### Deploy Page (`/deploy`)
- 3步骤部署向导 (Algorithm -> Host -> Config)
- 算法选择下拉框 (支持搜索)
- 目标主机选择
- 部署配置 (GPU内存限制、自动重启)

#### Deployment History (`/hosts/[hostId]/history`)
- Tab切换 (History / Logs)
- 历史部署表格 (时间、算法、状态)
- xterm.js 日志查看器 (自动滚动、下载)

### 3. 新增组件

| 组件 | 类型 | 说明 |
|------|------|------|
| `HostCard` | UI | 主机卡片，含GPU监控 |
| `HostFilters` | UI | 状态/GPU过滤器 |
| `GPUUtilization` | UI | GPU使用率进度条 |
| `ResourceBar` | UI | 内存/存储通用条 |
| `DeployWizard` | Container | 部署向导容器 |
| `AlgorithmSelect` | Form | 算法选择组件 |
| `HostSelect` | Form | 主机选择组件 |
| `DeployConfig` | Form | 部署配置组件 |
| `DeployProgress` | Modal | 部署进度弹窗 |
| `StepIndicator` | UI | 步骤指示器 |
| `HistoryTable` | Data | 历史记录表格 |
| `LogViewer` | Container | 日志查看器容器 |

### 4. State Management

```
React Query (Server State)
├── useHosts()           # 主机列表 (10s轮询)
├── useHost()            # 单主机详情 (5s轮询)
├── useHostHistory()     # 部署历史
└── useDeployToHost()    # 部署 mutation

Zustand (UI State)
├── useHostUIStore       # 过滤器、部署向导状态
└── useLogStore          # 日志缓冲区 (max 5000条)

Local State (SSE)
└── useHostSSE()         # 实时GPU/状态更新
```

### 5. API 依赖 (需要后端实现)

| Endpoint | Method | 说明 | Status |
|----------|--------|------|--------|
| `/api/hosts` | GET | 主机列表 | Available |
| `/api/hosts/{id}` | GET | 主机详情 | Available |
| `/api/hosts/{id}/history` | GET | 部署历史 | **Needed** |
| `/api/hosts/{id}/stream` | GET | SSE实时状态 | **Needed** |
| `/api/hosts/{id}/logs` | GET | SSE日志流 | **Needed** |
| `/api/deploy` | POST | 部署算法 | **Needed** |
| `/api/algorithms` | GET | 算法列表 | **Needed** |

## 产出物

| 产出 | 位置 |
|------|------|
| 架构设计文档 | `docs/superpowers/research/frontend-deploy-design.md` |
| 组件目录 | `src/components/hosts/*` |
| 组件目录 | `src/components/deploy/*` |
| 组件目录 | `src/components/logs/*` |
| Hooks | `src/hooks/use-hosts.ts`, `use-host-sse.ts` |
| Store | `src/lib/stores/ui-store.ts` |

## 下一步行动

1. **等待后端API**: 标记为 "Needed" 的6个端点需要 @backend-engineer 实现
2. **开始开发**: API就绪后按 Implementation Order 执行
3. **并行开发**: 后端实现与前端开发可并行进行

## 状态

- [x] Phase 2.3 架构设计完成
- [x] 文档已输出到 `docs/superpowers/research/frontend-deploy-design.md`
- [ ] 等待后端API接口
- [ ] 前端开发待启动

## 预估工期

Phase 2.3 前端开发: **6人日**
- Host List 页面: 2天
- Deploy Wizard: 2天
- History + Logs: 1.5天
- 集成测试: 0.5天
