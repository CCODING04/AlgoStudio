# from: @coordinator
# to: @performance-engineer
# date: 2026-03-28
# type: task
# round: Phase 3 Round 4

## 任务: test_hosts_status_redirect_follow 性能优化

### 当前状态
- `test_hosts_status_redirect_follow` 耗时 1.09s，是其他测试的 100 倍
- 该测试使用 `client.follow_redirects=True`，可能涉及多次 HTTP 请求

### 具体任务

1. **分析慢的原因**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/test_hosts_api.py::TestHostsAPI::test_hosts_status_redirect_follow -v --tb=long 2>&1
   ```

2. **优化方向**
   - 验证是否需要跟随重定向
   - 优化重定向处理逻辑
   - 减少不必要的 HTTP 请求

3. **验证优化效果**
   - 优化后测试时间应 < 0.1s
   - 确保功能正确性不受影响

### 目标
- 测试时间从 1.09s 优化至 < 0.1s

### 输出
完成后在 `talks/performance-engineer-to-coordinator-round4-2026-03-28.md` 汇报：
- 慢的原因分析
- 优化措施
- 优化后的测试时间
