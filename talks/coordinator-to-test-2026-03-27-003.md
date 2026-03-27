# 任务分配：RBAC/HMAC 安全测试

**from:** @coordinator
**to:** @test-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0

---

## 任务背景

Round 3 评审发现 RBAC/HMAC 安全功能完全没有测试覆盖。

## 任务内容

添加以下测试：

### 1. RBAC 中间件测试 `tests/unit/api/test_rbac.py`

```python
# 必须覆盖的测试
test_missing_signature_rejected
test_invalid_signature_rejected
test_expired_timestamp_rejected
test_valid_signature_accepted
test_replay_attack_prevention
test_role_based_access_control
test_permission_check_viewer
test_permission_check_developer
test_permission_check_admin
```

### 2. API 测试认证头配置

修复 `tests/unit/api/test_tasks_api.py` 中的认证头配置，使测试通过 RBAC 中间件。

### 3. SSH 安全测试

修复现有 SSH 测试或添加新测试验证：
- SSH key 认证流程
- 连接池原子操作

## 输入

- RBAC 中间件: `src/algo_studio/api/middleware/rbac.py`
- SSH 部署: `scripts/ssh_deploy.py`

## 输出

- `tests/unit/api/test_rbac.py` (25 tests)
- 修复的 `tests/unit/api/test_tasks_api.py` (16 tests)
- 更新的 `tests/integration/test_ssh_deploy.py` (14 tests)

## 截止日期

Round 4 结束前

## 状态

- [x] 任务已接收
- [x] RBAC 测试完成 (25 tests)
- [x] API 测试修复 (16 tests)
- [x] SSH 测试补充 (14 tests)

## 测试结果

```
======================== 55 passed, 2 warnings in 1.59s ========================
```

### RBAC 测试覆盖

1. Signature Verification:
   - `test_missing_signature_rejected` - 验证缺失签名被拒绝
   - `test_invalid_signature_rejected` - 验证无效签名被拒绝
   - `test_expired_timestamp_rejected` - 验证过期时间戳被拒绝
   - `test_valid_signature_accepted` - 验证有效签名被接受
   - `test_replay_attack_prevention` - 验证重放攻击防护
   - `test_missing_user_id_rejected` - 验证缺失用户ID被拒绝
   - `test_missing_timestamp_rejected` - 验证缺失时间戳被拒绝
   - `test_tampered_signature_rejected` - 验证篡改签名被拒绝
   - `test_wrong_secret_key_rejected` - 验证错误密钥被拒绝
   - `test_invalid_timestamp_format_rejected` - 验证无效时间戳格式被拒绝
   - `test_future_timestamp_rejected` - 验证未来时间戳被拒绝
   - `test_empty_signature_rejected` - 验证空签名被拒绝

2. Role-Based Access Control:
   - `test_role_based_access_control` - 验证基于角色的访问控制
   - `test_permission_check_viewer` - 验证 viewer 角色权限
   - `test_permission_check_developer` - 验证 developer 角色权限
   - `test_permission_check_admin` - 验证 admin 角色权限

3. Public Routes:
   - `test_health_endpoint_no_auth` - 验证 /health 无需认证
   - `test_root_endpoint_no_auth` - 验证 / 无需认证
   - `test_docs_endpoint_no_auth` - 验证 /docs 无需认证

4. Middleware Helpers:
   - `test_role_permissions_mapping` - 验证角色权限映射
   - `test_permission_enum_values` - 验证权限枚举值
   - `test_role_enum_values` - 验证角色枚举值
   - `test_public_routes_constant` - 验证公共路由常量
   - `test_max_timestamp_age` - 验证最大时间戳年龄

### API 测试修复

- 添加 `make_auth_headers()` 辅助函数生成有效的 HMAC 签名认证头
- 在所有 API 测试中使用 `auth_headers` fixture
- 修复响应格式以匹配实际 API (`items` 替代 `tasks`)

### SSH 安全测试补充

- `TestSSHConnectionPoolAtomic` - 连接池原子操作测试
  - `test_connection_pool_atomic_release_closed` - 关闭连接的原子释放
  - `test_connection_pool_atomic_release_valid` - 有效连接的原子释放
  - `test_connection_pool_concurrent_release` - 并发释放原子性
- `TestSSHKeyAuthentication` - SSH 密钥认证测试