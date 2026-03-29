# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 6

## 任务: ray_dashboard_client.py 覆盖率提升

### 背景
评审建议：聚焦大模块才能快速提升覆盖率。
ray_dashboard_client.py 当前仅 29.7% 覆盖，是最大短板之一。

### 具体任务

**1. 分析 ray_dashboard_client.py**

查看 `src/algo_studio/core/ray_dashboard_client.py`：
- 主要类和方法
- 外部依赖（Ray API）

**2. 添加单元测试**

创建 `tests/unit/core/test_ray_dashboard_client.py`：
- 测试 RayDashboardClient 初始化
- 测试节点查询
- 测试任务列表
- 测试资源监控
- 使用 mock 隔离 Ray API

**3. 验证覆盖率**
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/core/test_ray_dashboard_client.py -v --cov=src.algo_studio.core.ray_dashboard_client --cov-report=term-missing
```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round6-2026-03-29.md` 汇报：
- 覆盖率提升结果
- 目标 60% 是否达成
