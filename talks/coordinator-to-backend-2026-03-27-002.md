# 任务分配：RBAC P0 安全修复

**from:** @coordinator
**to:** @backend-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0

---

## 任务背景

Round 2 架构评审发现以下 P0 安全问题需要修复：

### S4: 开发模式绕过认证
- 位置: `src/algo_studio/api/middleware/rbac.py`
- 问题: `if not user_id:` 分支允许匿名访问
- 修复: 删除开发模式代码，强制要求认证

### S5: Header 认证可被伪造
- 问题: X-User-ID/X-User-Role 可被客户端任意伪造
- 修复: 添加签名验证或 session 管理

## 任务内容

1. 删除 RBAC 开发模式绕过代码
2. 实现安全的用户认证机制
3. 添加权限验证中间件

## 输入

- Round 2 评审报告: `docs/superpowers/schedule/round2-review.md`
- RBAC 中间件: `src/algo_studio/api/middleware/rbac.py`

## 输出

- 修复后的 RBAC 中间件
- 安全性验证报告

## 截止日期

Round 3 结束前

## 状态

- [x] 任务已接收
- [x] 删除开发模式
- [x] 认证机制加固
- [x] 签名验证已实现
- [x] 安全性验证通过

## 修复详情

### S4: 开发模式绕过认证 - 已修复
- 删除了 `if not user_id:` 分支（原来的 lines 104-109）
- 现在无 `X-User-ID` 头部的请求会返回 401 Unauthorized

### S5: Header 认证可被伪造 - 已修复
- 添加了 HMAC-SHA256 签名验证机制
- 客户端必须提供 `X-Signature` 头：`HMAC-SHA256(user_id:timestamp, secret_key)`
- 添加了 `X-Timestamp` 头部防止重放攻击（最大 5 分钟）
- 使用 constant-time 比较防止时序攻击
- 未设置 `RBAC_SECRET_KEY` 时拒绝所有请求（fail-secure）

### 额外修复: PUBLIC_ROUTES bug
- 修复了 `_is_public_route()` 方法，`"/"` 不再错误匹配所有路径

## 验证结果

```
无认证头 -> 401 (正确)
有 X-User-ID 但无签名 -> 401 (正确)
有 X-User-ID 但过期 timestamp -> 401 (正确)
有 X-User-ID 但签名错误 -> 401 (正确)
有 X-User-ID + timestamp + 正确签名 -> 200 (正确)
Public routes (/, /health, /docs) -> 200 (正确)
```

## 需要的配置

生产环境需要设置环境变量：
```bash
export RBAC_SECRET_KEY="your-secret-key-here"
```

客户端调用示例：
```python
import hmac, hashlib, time

secret = os.environ['RBAC_SECRET_KEY']
user_id = 'testuser'
timestamp = str(int(time.time()))
message = f'{user_id}:{timestamp}'
signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

headers = {
    'X-User-ID': user_id,
    'X-Timestamp': timestamp,
    'X-Signature': signature
}
```
