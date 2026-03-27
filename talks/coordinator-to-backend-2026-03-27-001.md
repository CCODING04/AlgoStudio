# 任务分配：数据库 Round 2 实现

**from:** @coordinator
**to:** @backend-engineer
**date:** 2026-03-27
**type:** task
**priority:** P1
**ref:** round1-review

---

## 任务背景

Round 1 架构评审提出以下改进建议：

### 建议改进

1. **RBAC 实现细节**
   - 问题: RBAC 权限定义完整但实现细节缺失
   - 添加权限检查中间件设计

2. **Bcrypt cost factor**
   - 问题: 未指定 bcrypt 成本因子
   - 建议: 使用 cost=12

3. **分页游标模式**
   - 问题: 对大结果集使用 offset/limit
   - 建议: 使用游标分页

## 任务内容

1. 实现 RBAC 权限检查中间件
2. 配置 bcrypt cost=12
3. 实现游标分页
4. 完成数据库迁移

## 输入

- Round 1 评审报告: `docs/superpowers/schedule/round1-review.md`
- 数据库设计: `docs/superpowers/design/database-api-design.md`

## 输出

- RBAC 中间件实现
- 更新的数据库模型

## 截止日期

Week 2 结束前 (2026-03-28)

## 状态

- [x] 任务已接收
- [x] RBAC 中间件
- [x] Bcrypt 配置
- [x] 游标分页
