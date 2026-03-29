# Test Coverage Research Report

**From:** @test-engineer
**To:** @coordinator
**Date:** 2026-03-28
**Subject:** 测试覆盖率目标研究 - 80% / 更高

---

## 1. 业界测试覆盖率标准

### 1.1 各语言/框架基准数据

| 类型 | 典型项目 | 推荐覆盖率 | 备注 |
|------|----------|------------|------|
| **Python 库/框架** | Django, FastAPI, SQLAlchemy | 85-95% | 核心模块追求 90%+ |
| **JavaScript/TypeScript** | React, Vue, Node.js | 80-90% | 前端 UI 组件难以达到 100% |
| **Java 企业应用** | Spring, Jakarta EE | 70-85% | 集成测试占比高 |
| **Go 项目** | Kubernetes, Terraform | 70-85% | 强调接口覆盖 |
| **ML/AI 平台** | Kubeflow, MLflow, Ray | 60-80% | GPU/Ray 集成难以 Mock |

### 1.2 覆盖率与软件质量关系

```
覆盖率与缺陷发现率关系（Google/BigTech 研究）:
- 0%:  基础基线
- 50%: 发现约 50% 缺陷
- 80%: 发现约 80% 缺陷
- 90%: 发现约 90% 缺陷
- 100%: 剩余 10% 缺陷多为并发/边界问题
```

**关键洞察:** 80% 覆盖率通常能覆盖大部分业务逻辑，但剩余 20% 往往包含边界条件和错误处理路径。

### 1.3 FastAPI 测试最佳实践

FastAPI 社区推荐:
- **单元测试:** 70-80% (核心业务逻辑)
- **API 集成测试:** 80%+ (路由、Pydantic 模型)
- **E2E 测试:** 关键路径覆盖，不追求高数值覆盖率

参考项目:
- **FastAPI 本身:** ~95% (自测)
- **SQLModel:** ~88%
- **Pydantic:** ~95%

---

## 2. ML/AI 平台测试特殊性

### 2.1 覆盖率挑战

| 挑战 | 说明 | 影响 |
|------|------|------|
| **Ray 集群依赖** | 任务调度需真实 Ray 环境 | 单元测试需要 Mock |
| **GPU 操作** | pynvml 无法在 CI 环境验证 | 依赖手工测试 |
| **异步任务** | SSE 进度更新、超时场景 | 需要集成测试 |
| **LLM 集成** | 外部 API 调用不稳定 | Mock 或 VCR 重放 |
| **分布式状态** | Actor 间通信 | 高复杂度测试场景 |

### 2.2 ML 平台推荐覆盖率

| 组件 | 推荐目标 | 理由 |
|------|----------|------|
| **调度算法** (WFQScheduler) | 85%+ | 核心差异化竞争力 |
| **Quota Manager** | 90%+ | 资源分配准确性 |
| **API Routes** | 80%+ | 用户-facing 接口 |
| **权限/RBAC** | 90%+ | 安全关键 |
| **Ray 集成层** | 70%+ | 集成测试为主 |
| **LLM Agent** | 60-70% | 外部依赖难以测试 |

---

## 3. AlgoStudio 当前覆盖率分析

### 3.1 整体数据

| 指标 | 当前值 | 目标值 | 差距 |
|------|--------|--------|------|
| **整体覆盖率** | 56.1% | 80% | -23.9% |
| **分支覆盖** | 0% | 50%+ | 未启用 |
| **测试文件数** | 48 | - | - |
| **覆盖代码行** | 3036/5412 | - | - |

### 3.2 包级别分析

| 包 | 当前 | 目标 | 优先级 | 差距 |
|-----|------|------|--------|------|
| `cli` | 0.0% | 60% | 低 | 新功能可 TDD |
| `web` | 0.0% | 50% | 低 | E2E 为主 |
| `web.pages` | 0.0% | 40% | 低 | Playwright E2E |
| `core.scheduler.routing` | 20.4% | 80% | **高** | 核心算法 |
| `core.scheduler.scorers` | 23.4% | 80% | **高** | 核心算法 |
| `monitor` | 31.9% | 70% | 中 | 监控逻辑 |
| `core.scheduler.agents.llm` | 34.6% | 60% | 中 | LLM 封装 |
| `core.scheduler.agents` | 34.9% | 70% | 中 | 调度决策 |
| `core` | 38.3% | 70% | 中 | 核心模块 |
| `api.routes` | 47.3% | 80% | **高** | 用户接口 |
| `db` | 48.6% | 80% | 中 | 数据层 |
| `api` | 51.5% | 80% | 中 | API 层 |

### 3.3 高覆盖率模块 (已达目标)

| 包 | 覆盖率 | 说明 |
|-----|--------|------|
| `core.auth` | 100.0% | 权限检查器 |
| `db.models` | 99.1% | ORM 模型 |
| `core.scheduler.memory` | 95.7% | 内存存储 |
| `core.scheduler.validators` | 90.7% | 资源验证 |
| `api.middleware` | 87.3% | 中间件 |
| `core.scheduler` | 84.5% | 调度器 |
| `core.quota` | 79.7% | 配额管理 |
| `core.scheduler.analyzers` | 79.5% | 分析器 |
| `core.deploy` | 78.0% | 部署逻辑 |

---

## 4. 推荐覆盖率目标

### 4.1 分阶段目标

| 阶段 | 目标 | 时间 | 重点模块 |
|------|------|------|----------|
| **Phase 2.5** | 65% | 1-2 周 | routing, scorers, api.routes |
| **Phase 3.0** | 75% | 2-4 周 | core, scheduler.agents, monitor |
| **Phase 3.1** | 80% | 4-8 周 | 全模块达标 |

### 4.2 按模块推荐

```python
# 推荐覆盖率目标配置 (.coveragerc)
[report]
precision = 1
show_missing = true
skip_covered = false

[html]
directory = htmlcov

[run]
branch = true  # 启用分支覆盖

# 按包目标 (coverage 6.0+ 支持 per-package 目标)
[coverage:paths]
source = src
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */node_modules/*
```

### 4.3 明确推荐意见

**针对 AlgoStudio 项目:**

1. **80% 是合理的长期目标**, 但不建议作为 Phase 2.5 的硬性要求
2. **优先保障核心算法模块** (routing, scorers, scheduler) 达到 80%+
3. **API Routes 应达到 80%** - 这是用户-facing 接口，稳定性重要
4. **LLM/Agent 模块 60-70% 即可** - 外部依赖多，强行追求高覆盖浪费
5. **CLI 和 Web 可接受 40-60%** - 这些更适合 E2E 测试
6. **分支覆盖应启用** - 当前 0% 说明未开启，无法发现边界问题

---

## 5. 分阶段提升建议

### Phase 2.5 行动项 (目标 65%)

1. **core.scheduler.routing: 20% -> 80%**
   - `test_router.py` 扩展测试用例
   - 覆盖边界条件: 空队列、满负载、并发路由

2. **core.scheduler.scorers: 23% -> 80%**
   - `test_node_scorer.py` 增加多维评分测试
   - Mock pynvml 避免环境依赖

3. **api.routes: 47% -> 70%**
   - `test_tasks_api.py` 增加错误路径测试
   - `test_hosts_api.py` 完善边界情况

### Phase 3.0 行动项 (目标 75%)

4. **core.scheduler.agents: 35% -> 70%**
   - Mock LLM provider
   - 测试调度决策树

5. **monitor: 32% -> 70%**
   - `test_node_monitor.py` Mock pynvml
   - 测试超时、错误恢复

6. **启用分支覆盖**
   - 修改 `.coveragerc` 启用 `branch = true`
   - 预期整体覆盖率下降 5-10%，但更反映真实情况

### Phase 3.1 行动项 (目标 80%)

7. **db: 49% -> 80%**
   - 集成测试覆盖迁移、事务

8. **core: 38% -> 70%**
   - task.py, ray_client.py 核心路径

---

## 6. 测试策略建议

### 6.1 测试金字塔

```
        /\
       /E2E\        <- 10% (关键路径)
      /------\
     /Integr. |     <- 30% (API + DB)
    /---------|-----
   /  Unit    |     <- 60% (算法、逻辑)
  /-----------|-------
```

### 6.2 Mock 策略

| 依赖 | Mock 方式 | 理由 |
|------|-----------|------|
| **Ray 集群** | `pytest-mock` + `ray.ClientStub` | CI 环境无集群 |
| **pynvml/GPU** | Mock 返回固定 GPU 信息 | GPU 不在 CI |
| **LLM API** | Fake Anthropic provider | 避免外部依赖 |
| **数据库** | SQLite in-memory | 快、可重复 |
| **Redis** |fakeredis | 避免外部服务 |

### 6.3 覆盖率工具配置

```ini
# .coveragerc
[run]
source = src
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */node_modules/*
    */algo_studio/api/main.py  # 简单路由聚合

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

---

## 7. 参考资料

1. **Google Testing Blog**: "Just Say No to More End-to-End Tests" - 测试金字塔
2. **FastAPI Testing Docs**: https://fastapi.tiangolo.com/tutorial/testing/
3. **Coverage.py Docs**: https://coverage.readthedocs.io/
4. **Ray Testing Guide**: https://docs.ray.io/en/latest/testing.html
5. **ML Platform Testing**: Netflix ML Platform testing strategies

---

## 8. 结论

**推荐目标:**
- **Phase 2.5 结束: 65%** (可达)
- **Phase 3.0 结束: 75%** (努力可达)
- **Phase 3.1 结束: 80%** (长期目标)

**80% 覆盖率是合理的**, 但应分阶段达成, 优先保障核心算法和 API Routes。CLI/Web 可接受较低覆盖率, 用 E2E 测试补充。

**关键行动:** 启用分支覆盖, 聚焦 routing/scorers 模块。
