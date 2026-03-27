# 任务分配：性能监控 Round 2 完善

**from:** @coordinator
**to:** @performance-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0
**ref:** round1-review

---

## 任务背景

Round 1 性能评审发现以下问题需要修复：

### 必须修复

1. **GPU 内存百分比表达式重复乘 100**
   - 位置: `monitoring/prometheus/perf_rules.yml` 第 43 行
   - 问题: 表达式已是百分比，又乘以100导致显示值超出100%
   - 修复: 移除 `* 100`

2. **性能测试脚本缺失**
   - `tests/performance/` 仅有 baseline JSON
   - 实现 `test_api_load.py`, `test_sse_performance.py` 等

3. **CI/CD 未集成**
   - 添加 GitHub Actions workflow

### 建议改进

4. **JuiceFS exporter 缺失**
   - 考虑使用 node_exporter 自定义指标

5. **告警接收端未配置**
   - 配置 Grafana 告警接收端

## 任务内容

1. 修复 GPU 内存百分比表达式
2. 实现性能测试脚本
3. 集成 CI/CD
4. 配置 Grafana 告警

## 输入

- Round 1 评审报告: `docs/superpowers/schedule/round1-review.md`
- 性能计划: `docs/superpowers/team/performance-test-plan.md`

## 输出

- 修复后的 Prometheus 配置
- 性能测试脚本: `tests/performance/`
- GitHub Actions workflow

## 截止日期

Week 2 结束前 (2026-03-28)

## 状态

- [ ] 任务已接收
- [ ] GPU 表达式修复
- [ ] 测试脚本实现
- [ ] CI/CD 集成
