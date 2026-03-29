# Phase 2.3 反馈

## RBAC 权限系统

### 设计评估

**优点:**
- 层级结构 (Org -> Team -> User) 设计清晰，符合企业组织模型
- 权限继承模型完整，org:* / team:* / user:* 三层权限定义合理
- 任务资源权限矩阵 (Owner/Team Member/Org Member/Public) 定义明确
- AuditLog 设计全面，覆盖主要变更事件
- 数据库 Schema 完整，包含所有必要的索引

**待补充项:**
1. **User 模型关联**: 文档未展示 `User` 模型如何关联 Organization/Team。需确认:
   - User 是否直接关联 Organization 还是仅通过 Team 间接关联？
   - `user_id` 是否与现有认证系统 (HMAC) 兼容？

2. **默认角色定义**: 缺少新用户在创建时默认角色定义

3. **迁移路径**: 现有任务/数据如何迁移到新的组织结构

4. **超级管理员**: `is_superuser` 字段仅在 PermissionChecker 中检查，但未定义哪些用户有此权限

### 实现建议

**1. 模型实现顺序调整:**
```
Week 5 Day 1-2: User/Organization/Team 核心模型 (先于 TeamMembership)
Week 5 Day 3-4: TeamMembership API + PermissionChecker
Week 5 Day 5: 任务取消功能
Week 6 Day 1-2: 任务历史 API + AuditLog
Week 6 Day 3-4: 任务资源 API
Week 6 Day 5: 集成测试
```

**2. API 实现优先级的建议:**
- P0: Organization/Team CRUD (其他功能依赖)
- P0: PermissionChecker (任务取消/历史/资源都依赖)
- P1: 任务取消 + 历史 (前端页面需要)
- P2: 审计日志中间件 (可后续添加)

**3. 待决策项:**
- [ ] Organization 默认配额是否需要预设？
- [ ] DELETE /tasks/{id} 是软删除还是硬删除？
- [ ] 资源采集频率建议 10s 间隔
- [ ] 审计日志保留期建议 90 天

### 依赖关系

| 依赖方 | 依赖内容 | 状态 |
|--------|---------|------|
| @frontend-engineer | Hosts/Deploy 页面需 Organization/Team API | 待 Phase 2.3 完成 |
| @ai-scheduling-engineer | 配额系统可能需要关联 Team/Org | 可并行 |
| @test-engineer | 需要 25+ RBAC 测试用例覆盖新 API | Phase 2.3 后开始 |

**内部依赖:**
- `Organization/Team` 模型 → `TeamMembership` API → `PermissionChecker` 扩展
- `TaskHistory` 模型 → 任务取消时记录历史
- `AuditLog` → 权限变更审计 (可延后)

### 甘特图调整建议

当前甘特图 Week 5-6 合理，但建议:
1. **Phase 2.3 Day 1-2 预留缓冲** 给数据库迁移和模型验证
2. **审计日志中间件** 可移至 Phase 2.4 (Week 7-8)，当前 Phase 2.3 关注核心 RBAC

### 其他

1. **向后兼容性**: HMAC 认证 (`X-User-ID`, `X-User-Role`) 需要与新的 User 模型对齐。现有 `User` 模型需扩展支持 `org_id`

2. **并发安全**: `PermissionChecker._is_same_team()` 和 `_is_same_org()` 每次调用都查询数据库，建议添加缓存层

3. **测试覆盖**: 建议增加边界测试:
   - User 同时属于多个 Team 的权限计算
   - User 同时属于多个 Organization 的权限计算
   - 跨 Organization 任务访问拒绝

4. **资源清理**: 任务取消时 Ray Actor 清理需要与 `ray_client.cancel_task()` 配合，需确认 Ray 侧支持取消远程任务
