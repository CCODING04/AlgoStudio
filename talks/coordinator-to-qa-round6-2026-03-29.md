# from: @coordinator
# to: @qa-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 6

## 任务: deploy.py 覆盖率提升

### 背景
deploy.py 当前 67.1% 覆盖，还需覆盖约 67 行。

### 具体任务

**1. 分析 deploy.py**

查看 `src/algo_studio/api/routes/deploy.py`：
- 主要端点和方法
- 缺失的测试分支

**2. 添加单元测试**

创建 `tests/unit/api/routes/test_deploy_extended.py`：
- 测试部署状态转换
- 测试错误处理分支
- 测试边界条件

**3. 验证覆盖率**
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/routes/test_deploy*.py -v --cov=src.algo_studio.api.routes.deploy --cov-report=term-missing
```

### 输出
完成后在 `talks/qa-engineer-to-coordinator-round6-2026-03-29.md` 汇报：
- 覆盖率提升结果
