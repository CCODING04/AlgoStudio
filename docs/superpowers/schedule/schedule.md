# AlgoStudio 实施计划甘特图

**项目：** AlgoStudio 平台能力拓展
**总工期：** 10-12 周
**最后更新：** 2026-03-26
**项目状态：** ✅ M0-M5 全部完成，5轮优化循环完成，评分 100/100

---

## 甘特图

```
周次    │ W1 │ W2 │ W3 │ W4 │ W5 │ W6 │ W7 │ W8 │ W9 │ W10│ W11│ W12│
────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
M0 接口 │████│    │    │    │    │    │    │    │    │    │    │    │
M1 存储 │    │████│████│    │    │    │    │    │    │    │    │    │
M2 API  │    │    │    │████│████│    │    │    │    │    │    │    │
M3 Fast │    │    │    │████│████│████│████│    │    │    │    │    │
M4 Deep │    │    │    │    │    │    │████│████│████│    │    │    │
M5 测试 │    │    │    │    │    │    │    │    │    │████│    │    │
```

---

## 里程碑详情

### M0: 接口定义 (Week 1)
| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 定义 Ray API 返回格式 | Coordinator | 已完成 | - |
| 定义节点状态数据结构 | Coordinator | 已完成 | - |
| 定义任务调度接口 | Coordinator | 已完成 | - |

### M1: Dataset Storage (Week 1-3)
| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 安装 Docker (Head) | Infrastructure | ✅ 已完成 | - |
| 配置 Worker NAS 挂载 | Infrastructure | ✅ 已完成 | - |
| 部署 Redis (6380) | Infrastructure | ✅ 已完成 | Docker |
| 配置 JuiceFS | Infrastructure | ✅ 已完成 | Redis+NAS |
| DVC 集成 | Infrastructure | ✅ 已完成 | JuiceFS |

### M2: Ray Dashboard API (Week 2-5)
| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| RayAPIClient 封装 | Backend | ✅ 已完成 | - |
| FastAPI 路由实现 | Backend | ✅ 已完成 | - |
| SSE 端点实现 | Backend | ✅ 已完成 | - |
| 熔断降级机制 | Backend | ✅ 已完成 | - |
| 节点状态 API | Backend | ✅ 已完成 | - |

### M3: Platform Agentic Fast Path (Week 2-7)
| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| TaskAnalyzer 算法 | AI Scheduling | ✅ 已完成 | - |
| NodeScorer 算法 | AI Scheduling | ✅ 已完成 | - |
| Fast Path 规则引擎 | AI Scheduling | ✅ 已完成 | 节点状态API |
| SafetyValidator | AI Scheduling | ✅ 已完成 | - |
| Memory Layer | AI Scheduling | ✅ 已完成 | Redis (可选SQLite) |

### M4: Deep Path LLM (Week 7-9)
| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| Claude API 集成 | AI Scheduling | ✅ 已完成 | Fast Path |
| Function Calling | AI Scheduling | ✅ 已完成 | Claude API |
| 成本估算 | AI Scheduling | ✅ 已完成 | Claude API |

### M5: 集成测试 (Week 10)
| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| Dataset Storage 测试 | QA | ✅ 已完成 | M1 |
| Ray API 测试 | QA | ✅ 已完成 | M2 |
| Agentic 测试 | QA | ✅ 已完成 | M3-M4 |
| 集成测试 | QA | ✅ 已完成 | All |
| **5轮优化循环** | QA | ✅ 已完成 | - |

---

## 角色任务分配

| 角色 | Subagent | 当前任务 | 状态 |
|------|----------|----------|------|
| 协调员 | `@coordinator` | M0 接口定义 | 已完成 |
| 基础设施工程师 | `@infrastructure-engineer` | M1 部署 | ✅ 基本完成 |
| 后端工程师 | `@backend-engineer` | M2 API | ✅ 已完成 |
| AI调度工程师 | `@ai-scheduling-engineer` | M3-M4 全部完成 | ✅ 已完成 |
| 测试工程师 | `@qa-engineer` | M5 测试 + 5轮优化 | ✅ 已完成 |
| Devops工程师 | `@devops-engineer` | Round 3 P0 安全修复 | ✅ S6 已完成 |

---

## 进度更新日志

| 日期 | 里程碑 | 更新内容 | 执行者 |
|------|--------|---------|--------|
| 2026-03-26 | - | 项目初始化 | Coordinator |
| 2026-03-26 | M0 | 接口定义文档完成，M1 通知已发送 | Coordinator |
| 2026-03-26 | M1 | 调查环境状态，发现 sudo 权限问题阻塞 | Infrastructure |
| 2026-03-26 | M1 | Docker已安装，Redis已启动6380，NAS已挂载，JuiceFS下载阻塞 | Coordinator |
| 2026-03-26 | M3 | Fast Path 完成：TaskAnalyzer, NodeScorer, FastPathScheduler, SafetyValidator, MemoryLayer | AI Scheduling |
| 2026-03-26 | M2 | RayAPIClient, FastAPI routes, SSE endpoints, 熔断降级全部完成 | Backend Engineer |
| 2026-03-26 | M1 | Docker/Redis/NAS 完成，JuiceFS 下载阻塞 | Coordinator |
| 2026-03-26 | M1 | JuiceFS 1.1.5 安装完成，algo-dataset 挂载到 /mnt/VtrixDataset | Coordinator |
| 2026-03-26 | M4 | Deep Path 完成：Claude API, Function Calling, 成本估算 | AI Scheduling |
| 2026-03-26 | M5 | 5轮优化循环完成：146测试通过，100/100评分 | QA Engineer |
| 2026-03-27 | Round 2 | 配额系统实现：乐观锁、继承验证、性能优化、单元测试 | AI Scheduling |
| 2026-03-27 | Round 3 | S6 安全修复：Secrets 迁移到 GitHub Secrets，生产部署审批流程 | Devops Engineer |
| 2026-03-27 | Round 3 | S7 (RedisQuotaStore) + G3 (decrement_usage 乐观锁) P0 修复完成 | AI Scheduling Engineer |
| 2026-03-28 | Phase 3 R1-R2 | rollback 覆盖率 38%→89%，E2E selectors 修复 | Test Engineer |
| 2026-03-28 | Phase 3 R3 | Web E2E selectors 修复，测试时间分析完成 | Test/Performance Engineer |
| 2026-03-28 | Phase 3 R4 | quota_manager 挂起修复 (cycle detection)，redirect test 优化 99% | Test/Performance Engineer |
| 2026-03-28 | Phase 3 R7 | pynvml 弃用警告处理 (nvidia-ml-py3), 510/510 测试通过 | Test Engineer |

---

## Phase 3 进度 (测试改进轮次)

### Phase 3 目标
1. rollback.py 覆盖率从 22% 提升至 70%+ ✅ (已达成 89%)
2. Web E2E 测试完善 ✅ (selectors 已修复)
3. 测试性能优化 (Round 4-8)

### Phase 3 Round 进度

| Round | 状态 | 主要成果 | 备注 |
|-------|------|----------|------|
| Round 1 | ✅ | rollback_id microsecond 修复 | 43 tests, 38% coverage |
| Round 2 | ✅ | SSH mock 测试增加 | 27 tests, 89% coverage |
| Round 3 | ✅ | Web E2E selectors 修复 | 14 tests fixed |
| Round 4 | ✅ | quota_manager 挂起修复，redirect test 优化 99% | 41/44 pass |
| Round 5 | ✅ | quota_manager 测试修复 (44/44 pass) | gpu_memory_gb, concurrent_tasks 修复 |
| Round 6 | ✅ | test_rollback.py 12 失败测试修复 (510/510 pass) | 路径模式、时间戳精度修复 |
| Round 7 | ✅ | pynvml 弃用警告处理 (nvidia-ml-py3) | PyTorch警告无法修(内部捆绑) |
| Round 8 | ✅ | Phase 3 收尾完成，510/510 测试通过，rollback 89% 覆盖率 | - |

### Phase 3 问题追踪

| ID | 问题 | 严重性 | 状态 |
|----|------|--------|------|
| P3-1 | SSH 方法未测试 | High | ✅ Round 2 已修复 |
| P3-2 | Redis 耦合 | Medium | 📋 后续任务: 存储抽象层重构 |
| P3-3 | Web E2E selectors 不匹配 | Medium | ✅ Round 3 已修复 |
| P3-4 | quota_manager 测试挂起 | High | ✅ Round 4 已修复 |
| P3-5 | redirect test 慢 (1.09s) | Medium | ✅ Round 4 已修复 |

---

## Phase 3.1 进度 (辩论决策落地)

### Phase 3.1 目标
1. Q2: JuiceFS 固定 100GB 缓存 ✅
2. Q4: 存储抽象层 Phase 1 ✅
3. Q3: 测试覆盖率 62% ⚠️ (目标 80%)
4. Q1: Redis Sentinel 部署 ✅

### Phase 3.2 目标 (2026-03-29)
1. 整体覆盖率 80%+ 🔄
2. audit.py 60%+ 🔄
3. tasks.py 60%+ 🔄
4. Sentinel 故障转移验证 🔄
5. 存储抽象层 Phase 2 🔄

### Phase 3.1 Round 进度

| Round | 状态 | 主要任务 | 成果 |
|-------|------|----------|------|
| Round 1 | ✅ | Q2 JuiceFS 配置 | 100GB 缓存已配置 |
| Round 2 | ✅ | Q4 接口设计 | SnapshotStoreInterface 创建 |
| Round 3 | ✅ | Q4 实现 | RedisSnapshotStore 10/10 |
| Round 4 | ✅ | asyncio 修复 | 534 unit + 91 integration passed |
| Round 5 | ✅ | Sentinel 部署 | 3 节点 Sentinel 运行中 |
| Round 6 | ✅ | router 注册 | algorithms 注册 + 62% 覆盖 |
| Round 7 | ✅ | 测试验证 | 587 passed, 36 failed |
| Round 8 | ✅ | 最终修复 | **623 passed, 0 failed** |

### Phase 3.1 评审团
- @architect-alpha: 系统架构评审
- @architect-beta: API/安全架构评审
- @architect-gamma: 调度/性能架构评审
- @test-engineer: 测试工程评审
- @performance-engineer: 性能基准评审

---

## Phase 3.2 进度 (覆盖率提升 + Sentinel HA)

### Phase 3.2 目标
| 目标 | 状态 |
|------|------|
| 整体覆盖率 80%+ | ✅ 达成 85% |
| audit.py 60%+ | ✅ 达成 96.55% |
| tasks.py 60%+ | ✅ 达成 86% |
| Sentinel 故障转移验证 | ✅ 自动 failover 成功 |
| Phase 2 存储抽象 | ✅ 完成 |

### Phase 3.2 Round 进度

| Round | 状态 | 主要成果 |
|-------|------|----------|
| R1 | ✅ | tasks.py SSE测试, Sentinel配置 |
| R2 | ✅ | Scheduler 161 tests, MockTask修复 |
| R3 | ✅ | core/task.py 80%, core/ray_client.py 84% |
| R4 | ✅ | routing 100%, scorers 93% |
| R5 | ✅ | auth.py 100%, deep_path_agent 94% |
| R6 | ✅ | ray_dashboard 93%, deploy 77%, fast_scheduler 85% |
| R7 | ✅ | 核心代码覆盖率 85%, 975 tests PASS |
| R8 | ✅ | **Sentinel 自动故障转移验证成功** |

### Phase 3.2 Sentinel 演练结果
- Master 故障检测: ~5s 内完成
- 自动故障转移: 成功 (Slave 晋升为 Master)
- 自动恢复: 成功 (原 Master 变为 Slave)
- Quorum: 3 Sentinels 可达

---

## Phase 3.3 进度 (操作手册与文档完善)

### Phase 3.3 目标
| 目标 | 状态 |
|------|------|
| 快速开始指南 | ✅ `docs/QUICK_START.md` |
| 算法部署手册 | ✅ `docs/ALGORITHM_DEPLOYMENT.md` |
| 用户操作手册 | ✅ `docs/USER_MANUAL.md` |
| 示例算法 | ✅ `examples/algorithms/simple_classifier/` |

### Phase 3.3 提交记录

| 日期 | Commit | 内容 |
|------|--------|------|
| 2026-03-29 | 080039a | docs: add quick start guide |
| 2026-03-29 | 53a8d3e | docs: add algorithm deployment guide and example |
| 2026-03-29 | 35f78b5 | docs: add web console user manual |

---

## Phase 3.4 进度 (Bug 修复迭代)

### Phase 3.4 问题追踪

| Bug | 问题 | 严重性 | 状态 | 负责人 |
|-----|------|--------|------|--------|
| Bug 1 | 主机状态显示不正确 (idle->offline) | P1 | ✅ Round 1 已修复 | @frontend-engineer |
| Bug 2 | 任务分发问题 (待确认) | P2 | ✅ 确认by design | @ai-scheduling-engineer |

### Phase 3.4 Round 进度

| Round | 状态 | 主要任务 | 成果 |
|-------|------|----------|------|
| Round 1 | ✅ | Bug 1: 前端状态显示修复 | 修复完成 |
| Round 2 | ✅ | Bug 2: 任务分发确认 | 确认by design |
| Round 3-5 | ✅ | 迭代优化完成 | 评分 90/100 |

---

## Phase 3.5 进度 (Web Console 功能增强)

### Phase 3.5 功能清单

| # | 功能 | 优先级 | Sprint | 状态 |
|---|------|--------|--------|------|
| 1 | 数据集管理界面 | P1 | Sprint 2-3 | 🔄 R2已完成基础CRUD，待R3详情页+Selector |
| 2 | Dashboard 部署功能 | P0 | Sprint 1 | ✅ R1已完成 |
| 3 | 节点标签显示 | P1 | Sprint 2-3 | 待开始 |
| 4 | 任务节点分配 | P1 | Sprint 2-3 | 待开始 |

### Phase 3.5 Round 进度

| Round | 状态 | Sprint | 主要任务 | 成果 |
|-------|------|--------|----------|------|
| R1 | ✅ 完成 | Sprint 1 | P0 Bug修复: DeployWizard版本、SSE进度、凭据API | 全部完成 (commit 883d147) |
| R2 | ✅ 完成 | Sprint 2 | 数据集前端: Types+Proxy Routes+DatasetTable+DatasetFilter+Datasets页面+DatasetForm | commit dcd95d7 |

