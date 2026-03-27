# 任务分配：E2E 真实故障测试

**from:** @coordinator
**to:** @qa-engineer
**date:** 2026-03-27
**type:** task
**priority:** P1

---

## 任务背景

Round 3 评审发现 E2E 故障恢复测试全为 Mock-based，无法验证真实故障场景。

## 任务内容

### 1. 添加真实故障注入测试

在 `tests/e2e/cluster/test_real_failure.py` 中添加：
- 真实 Ray 节点故障检测
- 真实任务迁移验证
- 超时机制验证

### 2. 添加 SSE 真实连接测试

在 `tests/e2e/web/test_sse_real.py` 中添加：
- 真实 SSE 重连机制测试
- 真实长连接保活测试
- 真实断流处理测试

### 3. 允许 CI 环境跳过标记

为无法在 CI 运行的测试添加 `@pytest.mark.skip_ci` 标记。

## 输入

- E2E 测试: `tests/e2e/`
- SSE Mock: `tests/e2e/conftest.py`

## 输出

- 真实故障注入 E2E 测试
- 真实 SSE 连接测试

## 截止日期

Round 4 结束前

## 状态

- [x] 任务已接收
- [x] 真实故障注入测试
- [x] SSE 真实连接测试
- [x] CI 跳过标记

## 完成情况

### 1. 真实故障注入测试
- 文件: `tests/e2e/cluster/test_real_failure.py`
- 类: `TestRealRayNodeFailure`, `TestRealTimeoutMechanism`, `TestRealTaskMigration`
- 测试用例: 8个真实Ray集群故障检测测试
- 标记: `@pytest.mark.skip_ci` (类级别)

### 2. SSE 真实连接测试
- 文件: `tests/e2e/web/test_sse_real.py`
- 类: `TestRealSSEConnection`, `TestRealSSETaskProgress`, `TestRealSSEClientBehavior`
- 测试用例: 10个真实SSE连接测试
- 标记: `@pytest.mark.skip_ci` (类级别)

### 3. CI 跳过标记
- pytest marker `skip_ci` 已添加到 `tests/e2e/playwright.config.py`
- 现有 `test_sse_progress.py` 的 `TestSSEProgressUpdates` 已添加 `skip_ci` 标记
- 新测试文件默认带有 `skip_ci` 标记
