# Round 8 任务分配: 测试基础设施准备

**from:** @coordinator
**to:** @test-engineer
**date:** 2026-03-27
**type:** task
**priority:** P1
**迭代:** Round 8

---

## 任务背景

为 Phase 2.3 迭代开发准备测试基础设施。

## 任务内容

### 1. 确认测试框架就绪
- 运行现有测试确认无 regression: `PYTHONPATH=src pytest tests/ -v --tb=short`
- 确认 pytest-asyncio 配置正确

### 2. 准备 Deploy API 测试 Fixtures
- 创建 `tests/factories/deploy_factory.py`
- 提供 DeployProgress, DeployWorkerRequest 等测试数据

### 3. 确认 E2E 测试配置
- Playwright 配置就绪
- skip_ci marker 正确使用

## 输出

- 测试框架验证报告
- 新增测试 fixtures
- 测试运行结果

## 截止日期

Week 5 初期 (与 Round 8 开发并行)

## 状态

- [ ] 任务已接收
- [ ] 测试框架验证完成
- [ ] Deploy fixtures 创建
- [ ] 报告已提交

---

完成后在 `talks/test-engineer-to-coordinator-round8-2026-03-27.md` 报告