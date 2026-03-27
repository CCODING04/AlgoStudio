# 任务分配：配额系统 Round 2 实现

**from:** @coordinator
**to:** @ai-scheduling-engineer
**date:** 2026-03-27
**type:** task
**priority:** P1
**ref:** round1-review

---

## 任务背景

Round 1 架构评审提出以下改进建议：

### 建议改进

1. **并发更新缺少乐观锁**
   - 问题: `increment_usage` 使用原子 UPDATE 但无版本控制
   - 建议: 添加 `version` 字段实现乐观锁

2. **继承验证可以更严格**
   - 建议: 添加 `validate_inheritance()` 方法

3. **权重计算依赖存储**
   - 问题: `_get_priority_score` 直接调用存储
   - 建议: 考虑缓存或批量获取优化

## 任务内容

1. 实现乐观锁 (version 字段)
2. 添加继承验证方法
3. 优化权重计算性能
4. 补充 QuotaManager 单元测试

## 输入

- Round 1 评审报告: `docs/superpowers/schedule/round1-review.md`
- QuotaManager 设计: `docs/superpowers/design/quota-manager-design.md`

## 输出

- 更新的 QuotaManager 实现
- 补充的单元测试

## 截止日期

Week 2 结束前 (2026-03-28)

## 状态

- [x] 任务已接收
- [x] 乐观锁实现
- [x] 继承验证方法
- [x] 性能优化
- [x] 单元测试
