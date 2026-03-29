# Round 1 Architecture Review

## Score: 6/10

## Issues Found

| ID | Severity | Issue | Suggestion |
|----|----------|-------|------------|
| 1 | CRITICAL | `team_membership.py` lines 35, 39: `Mapped[User]` and `Mapped[Team]` type hints reference classes not imported at runtime. `User` and `Team` are only under `TYPE_CHECKING` guard but used in runtime type annotations. This will cause `NameError` at import time. | Add `if TYPE_CHECKING:` imports for `User` and `Team`, or use string annotations (`Mapped["User"]`, `Mapped["Team"]`). |
| 2 | HIGH | `wfq_scheduler.py` line 468: VFT is calculated but never stored with the task or tracked persistently. `FairSchedulingDecision.virtual_finish_time` is set but not persisted to any audit/log store. No visibility into WFQ fairness decisions. | Add VFT to task metadata or create a `SchedulingDecisionLog` model to track fairness metrics. |
| 3 | HIGH | `wfq_scheduler.py` line 514: `len(self.queue.tenant_queues)` is used as denominator. When no tenants exist, this returns 0, causing division by zero (mitigated by `max(..., 1)`). However, when only 1 tenant exists, allocation_share becomes 100%, which may not be intended. | Review fair share logic - consider using configured guaranteed minimums rather than count-based division. |
| 4 | HIGH | `wfq_scheduler.py` line 349: `self.queue = GlobalSchedulerQueue(quota_manager)` is created synchronously in `__init__`, but `GlobalSchedulerQueue` methods (`enqueue`, `dequeue`, `requeue`) are all async. If `WFQScheduler` is instantiated without `async`, this may cause issues with event loop context. | Ensure `WFQScheduler` is only instantiated within async context or provide async factory method. |
| 5 | MEDIUM | `deploy.py` lines 46-86: Response models (`DeployProgressResponse`, `DeployWorkerResponse`, `DeployListResponse`) are plain Python classes, not Pydantic models. FastAPI cannot generate OpenAPI docs or validate responses automatically. | Convert to Pydantic models using `BaseModel` for proper FastAPI integration. |
| 6 | MEDIUM | `deploy.py` lines 38-39: Global module-level instances (`_progress_store`, `_deployer`) bypass FastAPI dependency injection lifecycle. If these have connection state (Redis, SSH), they may become stale or leak. | Use FastAPI's `Depends()` with lifespan context managers for proper initialization/cleanup. |
| 7 | MEDIUM | `audit.py` line 78: Custom `created_at` field instead of using `TimestampMixin`. This model should use the same mixin as other models for consistency. | Replace with `TimestampMixin` to inherit `created_at` and `updated_at` (though `updated_at` should remain immutable for audit logs - override to not update). |
| 8 | MEDIUM | Organization/Team quota fields (`max_teams`, `max_users`, `max_gpu_hours_per_day`, `max_members`) are defined but quota **usage** is not tracked. No mechanism to check if organization has reached its limits before allowing new team/user creation. | Add quota consumption tracking or integrate with `QuotaManager` for limit enforcement. |
| 9 | LOW | `deploy.py` line 35: Router prefix `/api/deploy` may conflict with global API prefix if mounted at `/api` elsewhere. Standard practice is to mount at `/deploy` and let the root router add `/api`. | Verify router mounting in `main.py` to ensure no double-prefix (`/api/api/deploy`). |

## Recommendations

### Immediate Fixes Required
1. Fix `team_membership.py` type annotations before any runtime usage
2. Add Pydantic response models to `deploy.py` for API documentation

### Integration Points Missing
1. **WFQScheduler -> Ray**: No integration with `TaskManager` or Ray cluster for actual task dispatch
2. **QuotaManager -> Organization/Team**: Quota limits defined but not enforced during entity creation
3. **Audit -> All Models**: No ORM event hooks to auto-create audit logs on model changes

### Design Observations
1. **Good**: WFQ formula implementation follows standard academic approach (Virtual Finish Time = weight_sum/tenant_weight + resources/allocation_share)
2. **Good**: Hierarchical queue structure (Global -> Tenant -> User) is sound
3. **Good**: Deployment SSE polling with heartbeat and reconnection support is well-designed
4. **Concern**: Reservation system in `ReservationManager` uses in-memory storage (`self.reservations`) - not durable across restarts

## Conclusion: CONDITIONAL

The architecture is fundamentally sound for Phase 2.3 goals with proper RBAC hierarchy, fair scheduling foundation, and deployment automation. However, **two critical bugs must be fixed before this code can run**:

1. `team_membership.py` will fail at import time due to missing type imports
2. Response models in `deploy.py` prevent proper API documentation generation

The WFQ scheduler implementation is mathematically correct but lacks integration with the Ray execution layer - this appears to be intentional for this phase (scheduler core only, integration in later phases).

**Status**: Ready for Round 2 once Issues #1 and #5 are addressed.

---

## API/Security Review

**日期:** 2026-03-27
**评审人:** @architect-beta (Platform Architect)
**评审范围:** `src/algo_studio/api/routes/deploy.py` + E2E tests in `tests/e2e/`

### 一、API 设计评审

#### 1.1 一致性评估

| 方面 | deploy.py | tasks.py (参考) | 状态 |
|------|-----------|-----------------|------|
| Router 前缀 | `/api/deploy` | `/api/tasks` | OK |
| Response Model | 纯 Python 类 | Pydantic Model | **不一致** |
| 认证装饰器 | 导入但未应用 | `@require_permission` | **缺失** |
| SSE 端点模式 | `EventSourceResponse` | `EventSourceResponse` | OK |

**问题详情:**

1. **Response Model 类型不匹配**
   - `deploy.py` 使用纯 Python 类 (`DeployProgressResponse`, `DeployWorkerResponse`)
   - `tasks.py` 使用 Pydantic models (`TaskResponse`, `TaskCreateRequest`)
   - 应统一使用 Pydantic models 以获得自动验证和 OpenAPI schema 生成

2. **RBAC 装饰器未应用**
   ```python
   # deploy.py 第22行导入但未使用:
   from algo_studio.api.middleware.rbac import require_permission, Permission
   ```
   所有 `/api/deploy/*` 端点都缺少 `@require_permission` 装饰器

#### 1.2 API 端点设计

| 端点 | 方法 | 路径 | 认证 | 评分 |
|------|------|------|------|------|
| list_workers | GET | `/api/deploy/workers` | 缺失 | 6/10 |
| get_worker | GET | `/api/deploy/worker/{task_id}` | 缺失 | 6/10 |
| create_worker | POST | `/api/deploy/worker` | 缺失 | 5/10 |
| get_worker_progress | GET | `/api/deploy/worker/{task_id}/progress` | 缺失 | 6/10 |

### 二、安全评审

#### 2.1 严重问题 (P0)

| # | 问题 | 位置 | 风险 |
|---|------|------|------|
| 1 | **RBAC 装饰器未应用** | `deploy.py` 所有端点 | 未授权访问 |
| 2 | **SSH 密码通过请求体传递** | `POST /api/deploy/worker` | 敏感信息日志泄露 |
| 3 | **无 IP 地址格式验证** | `create_worker()` | 注入攻击 |

#### 2.2 中等问题 (P1)

| # | 问题 | 位置 | 建议 |
|---|------|------|------|
| 4 | `DeployWorkerRequest.password` 类型 | `scripts/ssh_deploy.py` | 应使用 `SecretStr` 类型 |
| 5 | Redis 连接异常处理 | `list_workers()` L127-136 | 暴露内部错误信息 |
| 6 | 全局可变状态 | `_progress_store`, `_deployer` | 线程安全问题 |

#### 2.3 安全改进建议

1. **必须添加 RBAC 装饰器:**
   ```python
   @router.post("/worker")
   @require_permission(Permission.DEPLOY_WORKER)
   async def create_worker(request: DeployWorkerRequest):
   ```

2. **输入验证加强:**
   - 添加 IP 地址正则验证 (不支持 IP 段/CIDR)
   - 端口范围检查 (1-65535)

3. **敏感信息处理:**
   - 密码不应出现在日志中
   - 考虑使用 SSH key file 替代 password

### 三、E2E 测试覆盖评审

#### 3.1 测试统计

| 测试文件 | 测试类 | 测试方法数 | 状态 |
|----------|--------|-----------|------|
| `test_rbac_e2e.py` | 5 | 15 | 完整 |
| `test_deploy_page.py` | 4 | 15 | 较完整 |
| `test_sse_progress.py` | 2 | 9 | 较完整 |
| `test_scheduling_e2e.py` | 4 | 14 | 完整 |
| `test_failure_recovery.py` | 1 | 5 | 较完整 |
| `test_sse_real.py` | 3 | 11 | 完整 |
| **总计** | **19** | **~69** | - |

**注:** 实际测试数量 (~69) 与声称的 51 E2E test cases 不符

#### 3.2 关键路径覆盖

| 关键路径 | 测试覆盖 | 评分 |
|----------|---------|------|
| Deploy workflow (成功) | `test_successful_node_deployment` | 7/10 |
| Deploy workflow (失败) | `test_ssh_connection_failure_handling` | 6/10 |
| RBAC - Team Lead 取消他人任务 | `test_team_lead_can_cancel_team_member_task` | 8/10 |
| RBAC - 普通用户不能取消他人任务 | `test_regular_user_cannot_cancel_other_user_task` | 8/10 |
| SSE 进度更新 | `test_sse_progress_updates` | 7/10 |
| 节点故障恢复 | `test_task_status_update_on_node_failure` | 6/10 |

#### 3.3 测试质量问题

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| 1 | `api_client` fixture 缺少 deploy 方法 | 无法直接测试 deploy API | 高 |
| 2 | 大量 `if xxx.count() > 0` 条件判断 | 测试脆弱，DOM 变化时误报 | 中 |
| 3 | CI 环境下默认跳过 | 无法在 CI 验证功能 | 高 |
| 4 | Mock 层级不一致 | 部分测试使用真实客户端 | 中 |

**`api_client` fixture 缺失方法:**
- `create_deployment()`
- `get_deployment()`
- `list_deployments()`
- `get_deployment_progress()`

#### 3.4 E2E 测试改进建议

1. **扩展 `api_client` fixture:**
   ```python
   def create_deployment(self, node_ip: str, username: str, password: str):
       return self.client.post("/api/deploy/worker", json={...})

   def get_deployment(self, task_id: str):
       return self.client.get(f"/api/deploy/worker/{task_id}")
   ```

2. **减少条件判断依赖:**
   - 使用 `data-testid` 属性替代 CSS 选择器
   - 添加 `assert` 而非 `if condition: assert`

3. **CI 兼容性:**
   - Mock server 应在 CI 中自动启动
   - 添加 `@pytest.mark.ci` 标记真实集群测试

### 四、综合评分

| 评审维度 | 评分 | 说明 |
|----------|------|------|
| API 设计一致性 | 65/100 | Response model 类型不统一，RBAC 缺失 |
| 安全性 | 60/100 | RBAC 未应用，输入验证不足 |
| E2E 测试覆盖 | 75/100 | 覆盖较全，但 fixture 不完整 |
| **综合评分** | **66.7/100** | 需要修复 P0 安全问题 |

### 五、必须修复项 (P0)

| # | 问题 | 负责人 | 截止日期 |
|---|------|--------|----------|
| 1 | 应用 `@require_permission` 到 deploy 所有端点 | @backend-engineer | 2026-03-28 |
| 2 | 添加 `api_client` fixture 的 deploy 方法 | @qa-engineer | 2026-03-28 |
| 3 | 修复 IP 地址格式验证 | @backend-engineer | 2026-03-28 |
| 4 | 统一 Response model 为 Pydantic | @backend-engineer | 2026-03-29 |

### 六、Phase 2.3 结论

**状态:** ⚠️ 需要修复 P0 问题后重新评审
**综合评分:** 66.7/100
**进入下一轮:** 否 (需先修复安全问题)

**主要风险:**
1. Deploy API 未受 RBAC 保护 - 任何人可部署 worker
2. E2E 测试无法覆盖 deploy API 关键路径
3. 与现有 API 模式不一致
