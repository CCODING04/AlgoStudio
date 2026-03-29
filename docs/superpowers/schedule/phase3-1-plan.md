# Phase 3.1 实施计划

**项目：** AlgoStudio 平台能力拓展
**阶段：** Phase 3.1 - 辩论决策落地
**周期：** 8 轮迭代 (Round 1-8)
**最后更新：** 2026-03-28
**项目状态：** 🔄 启动中

---

## 评审团决策汇总

| 问题 | 推荐方案 | 评审一致性 | 实施优先级 |
|------|---------|-----------|-----------|
| Q1: Redis 高可用 | Sentinel (1主+1从+3节点) | 4/4 一致 | 中 |
| Q2: JuiceFS 缓存 | 固定 100GB | 4/4 一致 | 低 (配置) |
| Q3: 测试覆盖率 | 分阶段 80% | 4/4 一致 | 高 |
| Q4: 存储抽象层 | Repository Pattern + ABC | 4/4 一致 | 高 |

---

## 甘特图

```
Round   │ R1 │ R2 │ R3 │ R4 │ R5 │ R6 │ R7 │ R8 │
────────┼────┼────┼────┼────┼────┼────┼────┼────┤
Q2 配置  │████│    │    │    │    │    │    │    │
Q4 Phase1│    │████│████│    │    │    │    │    │
Q3 覆盖率│    │    │████│████│████│    │    │    │
Q1 部署  │    │    │    │    │████│████│    │    │
评审     │████│████│████│████│████│████│████│████│
```

---

## 任务详情

### Q2: JuiceFS 固定 100GB 缓存配置 (Round 1)

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 配置 JuiceFS 缓存为固定 100GB | @infrastructure | ✅ 完成 | - |
| 验证缓存配置生效 | @infrastructure | ✅ 完成 | Q2 配置 |
| 更新文档 | @infrastructure | ✅ 完成 | Q2 配置 |

**Q2 操作步骤:**
```bash
# 查看当前 JuiceFS 配置
juicefs config <MOUNT_POINT>

# 设置固定缓存大小 100GB
juicefs config --cache-size 102400 <MOUNT_POINT>

# 验证配置
juicefs config <MOUNT_POINT> | grep cache-size
```

### Q4: 存储抽象层重构 Phase 1 (Round 2-3)

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 创建 SnapshotStoreInterface ABC | @backend-engineer | 待分配 | - |
| 创建 InMemorySnapshotStore 实现 | @backend-engineer | 待分配 | SnapshotStoreInterface |
| 重构 RollbackService 使用接口注入 | @backend-engineer | 待分配 | InMemorySnapshotStore |
| 单元测试 (InMemorySnapshotStore) | @test-engineer | 待分配 | InMemorySnapshotStore |
| 评审 | @architect-alpha, @architect-beta | 待分配 | Phase 1 完成 |

**Q4 Phase 1 接口设计:**
```python
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime

class SnapshotStoreInterface(ABC):
    @abstractmethod
    async def save_snapshot(self, task_id: str, snapshot_data: dict) -> bool:
        pass

    @abstractmethod
    async def get_snapshot(self, task_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def list_snapshots(self, limit: int = 10) -> List[dict]:
        pass

    @abstractmethod
    async def delete_snapshot(self, task_id: str) -> bool:
        pass
```

### Q3: 测试覆盖率提升至 65% (Round 3-5)

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 分析当前覆盖率报告 | @test-engineer | 待分配 | - |
| api.routes 覆盖率 47% → 70% | @test-engineer | 待分配 | 分析完成 |
| core.scheduler.routing 覆盖率提升 | @test-engineer | 待分配 | api.routes |
| core.scheduler.scorers 覆盖率提升 | @test-engineer | 待分配 | routing |
| 启用分支覆盖 (branch=true) | @test-engineer | 待分配 | - |
| 验证 Phase 2.5 覆盖率目标 65% | @test-engineer | 待分配 | 上述任务 |
| 评审 | @architect-alpha, @architect-beta | 待分配 | Q3 完成 |

**分阶段覆盖率目标:**
| 阶段 | 目标 | 重点模块 |
|------|------|----------|
| Phase 2.5 | 65% | api.routes 47% → 70% |
| Phase 3.0 | 75% | 全模块 |
| Phase 3.1 | 80% | 核心算法 85%+ |

### Q1: Redis Sentinel 部署 (Round 5-6)

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 部署 Redis Sentinel (1主+1从+3节点) | @devops-engineer | 待分配 | Q3 完成 |
| 验证故障转移 | @devops-engineer | 待分配 | Sentinel 部署 |
| 更新连接字符串 | @backend-engineer | 待分配 | Sentinel 验证 |
| 单元测试 (Sentinel 模式) | @test-engineer | 待分配 | 连接字符串更新 |
| 评审 | @architect-alpha, @architect-beta | 待分配 | Q1 完成 |

---

## 评审团职责

### 评审团成员
- **@architect-alpha**: 系统架构评审
- **@architect-beta**: API/安全架构评审
- **@architect-gamma**: 调度/性能架构评审
- **@test-engineer**: 测试工程评审
- **@performance-engineer**: 性能基准评审

### 评审维度
| 维度 | 说明 |
|------|------|
| 可行性 | 技术实现难度 |
| 成本 | 实施成本（时间、资源） |
| 效益 | 解决问题的重要性 |
| 风险 | 实施风险高低 |
| 可维护性 | 长期维护成本 |

---

## Round 迭代流程

每轮遵循: **[开发 → 测试 → 评审] → Next Round**

### Round 评审标准
- 所有 P0 问题必须修复
- 覆盖率达标
- 性能基准不下降
- 安全问题不过夜

---

## Phase 3.1 Round 进度

| Round | 状态 | 主要任务 | 成果 |
|-------|------|----------|------|
| Round 1 | ✅ | Q2/Q3/Q4 准备 | 全部完成 |
| Round 2 | ✅ | Q4 实现 + Q3 asyncio 修复 | 10 snapshot tests + 510 passed |
| Round 3 | ✅ | Q4 Redis 实现 + algorithms.py 100% | algorithms 100%, RedisSnapshotStore 10/10 |
| Round 4 | ✅ | asyncio/集成测试修复 + Redis主从 | 534 unit + 91 integration passed |
| Round 5 | ✅ | Q4 Phase2 重构 + Sentinel 3节点 | Sentinel 运行中 + 待注册 router |
| Round 6 | ✅ | router注册 + Redis测试 + api.routes 62% | 92新测试通过 |
| Round 7 | ⚠️ | 全量测试验证 + Sentinel | 587 passed, 36 failed, 55% coverage |
| Round 8 | ✅ | API签名修复 + 测试隔离 | 623 passed, 0 failed |

---

## 进度更新日志

| 日期 | Round | 更新内容 | 执行者 |
|------|-------|---------|--------|
| 2026-03-28 | - | Phase 3.1 启动，辩论决策落地 | Coordinator |
| 2026-03-28 | R1 | Q2 JuiceFS 100GB 缓存配置完成 | @infrastructure |

---

## 遗留问题追踪

| ID | 问题 | 严重性 | 状态 |
|----|------|--------|------|
| P3-1 | SSH 方法未测试 | High | ✅ Round 2 已修复 |
| P3-2 | Redis 耦合 | Medium | 🔄 Phase 3.1 Q4 处理中 |
| P3-3 | Web E2E selectors 不匹配 | Medium | ✅ Round 3 已修复 |
| P3-4 | quota_manager 测试挂起 | High | ✅ Round 4 已修复 |
| P3-5 | redirect test 慢 | Medium | ✅ Round 4 已修复 |

---
