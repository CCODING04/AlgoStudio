# Phase 2 QA 测试策略文档

**版本:** v1.0
**创建日期:** 2026-03-26
**角色:** QA Engineer
**状态:** 设计完成

---

## 1. 测试策略概述

### 1.1 测试目标

确保 AlgoStudio Phase 2 交付的系统满足以下质量标准：
- 功能完整性：所有模块按需交付
- 系统稳定性：E2E 流程正常运行
- 性能达标：API p95 < 100ms，SSE 并发 ≥ 100
- 缺陷可追溯：缺陷生命周期全程管理

### 1.2 测试分层模型

```
┌─────────────────────────────────────────────────────────────┐
│                    UAT 用户验收测试                           │
│         - 业务场景验证                                       │
│         - 用户体验评估                                       │
├─────────────────────────────────────────────────────────────┤
│                    E2E 端到端测试                             │
│         - SSH 部署流程 E2E                                   │
│         - Web Console E2E                                   │
│         - 多节点集群 E2E                                     │
├─────────────────────────────────────────────────────────────┤
│                    压力测试 (Stress Testing)                  │
│         - API 负载测试                                       │
│         - SSE 并发测试                                       │
│         - 数据库压力测试                                      │
├─────────────────────────────────────────────────────────────┤
│                    兼容性测试 (Compatibility Testing)         │
│         - 浏览器兼容性                                       │
│         - 多节点环境兼容性                                    │
│         - Python 版本兼容性                                  │
├─────────────────────────────────────────────────────────────┤
│                    集成测试 (Integration)                     │
│         - API 端点测试                                       │
│         - 模块间集成                                         │
├─────────────────────────────────────────────────────────────┤
│                    单元测试 (Unit)                           │
│         - @test-engineer 负责                               │
│         - pytest 覆盖率 ≥ 80%                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. E2E 测试策略

### 2.1 测试范围

| E2E 场景 | 测试目标 | 关键验证点 |
|----------|----------|------------|
| SSH 部署流程 | 验证 Worker 节点自动化部署 | 连接、依赖安装、Ray 重启 |
| Web Console | 验证前端功能完整性 | Dashboard、Tasks、Hosts、Deploy |
| 多节点集群 | 验证调度和任务执行 | 任务分发、GPU 分配、状态同步 |

### 2.2 E2E 测试方法

**工具选型:** Playwright (推荐) / Cypress

**原因:**
- Playwright 支持多浏览器、截图/视频录制
- Cypress 语法简洁，但多浏览器支持较弱
- 两者都支持 SSE 事件监听

**执行环境:**
- 测试环境：独立 Ray 集群 (192.168.0.126 head + 192.168.0.115 worker)
- CI 环境：GitHub Actions 集成

### 2.3 E2E 测试执行频率

| 阶段 | 频率 | 说明 |
|------|------|------|
| 开发中 | 每日 | 冒烟测试 + 关键路径 |
| 发布前 | 每次 PR | 完整 E2E 套件 |
| 回归 | 每周 | 完整 E2E 套件 |

---

## 3. 压力测试策略

### 3.1 测试目标

验证系统在高负载下的稳定性，参考性能指标：

| 类型 | 指标 | 目标 |
|------|------|------|
| API p95 响应 | < 100ms |
| SSE 并发 | ≥ 100 连接 |
| SQLite p99 | < 100ms |
| 训练启动 | < 30s |
| 调度延迟 p95 | < 100ms |
| 推理延迟 p99 | < 500ms |

### 3.2 工具选型

**Locust** - Python 原生，支持分布式负载

**替代方案:** wrk (高性能基准测试)、pytest-benchmark (单元级基准)

### 3.3 压力测试场景

| 场景 | 并发数 | 持续时间 | 验证指标 |
|------|--------|----------|----------|
| API 基础负载 | 50 | 5min | p95 < 100ms |
| API 峰值负载 | 200 | 2min | p99 < 200ms |
| SSE 并发 | 100 | 10min | 无断连 |
| 混合读写 | 100 | 5min | 数据库 p99 < 100ms |

### 3.4 @performance-engineer 协作

| 测试类型 | 负责人 | @qa-engineer 配合 |
|----------|--------|-------------------|
| 性能基准测试 | @performance | 提供测试场景 |
| 平台性能测试 | @performance | 验收测试 |
| 算法性能测试 | @performance | 端到端验证 |
| 数据性能测试 | @performance | JuiceFS 验收 |

---

## 4. 兼容性测试策略

### 4.1 浏览器兼容性

| 浏览器 | 版本 | 测试优先级 |
|--------|------|------------|
| Chrome | >= 120 | P0 |
| Firefox | >= 121 | P1 |
| Safari | >= 17 | P2 |
| Edge | >= 120 | P1 |

### 4.2 多节点环境兼容性

| 环境 | 配置 | 测试优先级 |
|------|------|------------|
| 单节点 | Head only | P0 |
| 双节点 | Head + 1 Worker | P0 |
| 多节点 | Head + 2+ Workers | P1 |

### 4.3 Python 版本兼容性

| 版本 | 状态 | 测试优先级 |
|------|------|------------|
| 3.10 | 生产环境 | P0 |
| 3.11 | 开发环境 | P1 |
| 3.12 | 规划中 | P2 |

---

## 5. UAT 测试策略

### 5.1 UAT 触发条件

- Phase 2.3 完成后 (Week 5-6)
- 所有 P0 缺陷已修复
- @performance-engineer 性能报告达标

### 5.2 UAT 测试用例设计

**业务场景:**

| 场景 | 操作步骤 | 预期结果 |
|------|----------|----------|
| 部署新 Worker | Deploy 页面 → 添加节点 → SSH 部署 | 节点成功加入集群 |
| 创建训练任务 | Tasks → 新建任务 → 选择算法 → 提交 | 任务成功调度 |
| 查看集群状态 | Dashboard → 刷新 | 显示准确节点/任务状态 |
| SSE 实时更新 | 打开 Dashboard → 提交任务 | 进度实时推送 |
| 配额管理 | 设置配额 → 提交超额任务 | 正确拒绝/排队 |

### 5.3 UAT 执行方式

- 手动测试为主
- 关键路径自动化辅助
- 测试结果记录到 `tests/reports/UAT_REPORT.md`

---

## 6. 测试工具配置

### 6.1 Playwright 配置

```bash
# 安装
uv pip install playwright
playwright install chromium

# 配置文件: playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
```

### 6.2 Locust 配置

```python
# locustfile.py
from locust import HttpUser, task, between

class AlgoStudioUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def get_tasks(self):
        self.client.get("/api/tasks")

    @task(2)
    def get_hosts(self):
        self.client.get("/api/hosts")

    @task(1)
    def create_task(self):
        self.client.post("/api/tasks", json={
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1"
        })
```

### 6.3 Allure 配置

```bash
# 安装
uv pip install allure-pytest

# 运行测试
pytest tests/ --alluredir=tests/reports/allure-results

# 生成报告
allure serve tests/reports/allure-results
```

---

## 7. 测试数据管理

### 7.1 测试数据策略

| 数据类型 | 来源 | 管理方式 |
|----------|------|----------|
| 算法测试数据 | `algorithms/simple_classifier/v1/` | Git 跟踪 |
| 测试任务 | 动态生成 | Mock |
| 集群状态 | 真实集群 | 快照保存 |
| 用户数据 | 测试租户 | 独立数据库 |

### 7.2 测试数据隔离

- CI 环境使用独立 SQLite 文件
- E2E 测试使用 mock 数据
- 压力测试使用合成数据

---

## 8. 测试环境管理

### 8.1 环境配置

| 环境 | 用途 | Ray 集群 |
|------|------|----------|
| 开发环境 | 本地开发 | 单节点 |
| 测试环境 | CI/E2E | 双节点 (126 + 115) |
| 预发布环境 | UAT | 完整集群 |
| 生产环境 | 用户使用 | 完整集群 |

### 8.2 环境切换

```bash
# 测试环境变量
export ALGO_STUDIO_ENV=test
export RAY_ADDRESS=192.168.0.126:6379
export API_BASE_URL=http://localhost:8000
```

---

## 9. 交付物清单

| 交付物 | 位置 | 截止日期 |
|--------|------|----------|
| E2E 测试用例 | `tests/e2e/` | Week 2 |
| 压力测试脚本 | `tests/stress/` | Week 4 |
| 缺陷报告模板 | `docs/superpowers/testing/DEFECT_TEMPLATE.md` | Week 1 |
| UAT 测试报告 | `tests/reports/UAT_REPORT.md` | Week 8 |

---

## 10. 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 多节点环境不稳定 | E2E 测试失败 | 环境预热 + 重试机制 |
| SSE 测试复杂 | 并发测试不可靠 | 使用 Playwright SSE 支持 |
| 性能指标不达标 | 发布延迟 | 提前与 @performance 同步 |
| 前端 UI 变更频繁 | E2E 维护成本高 | 使用 Page Object 模式 |

---

**文档状态:** 正式版
**下次评审:** Phase 2.1 完成后
