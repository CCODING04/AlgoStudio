# Round 4 评审报告

## 架构评审

| 维度 | 评分 | 说明 |
|------|------|------|
| 安全性 | 8/10 | HMAC-SHA256 实现正确，但 SSH host_key_verify 未显式设置 |
| 架构 | 9/10 | 模块化良好，状态机模式合理，职责分离清晰 |
| 可维护性 | 8/10 | 代码质量高，注释完善，测试覆盖较好 |

## 问题发现

### 1. SSH Host Key Verification 未显式配置 (Important)

**位置**: `scripts/ssh_deploy.py` 第 278-287 行

**问题**: 代码注释声称使用 `host_key_verify=True` 实现 MITM 防护，但 `asyncssh.connect()` 调用中未显式设置此参数。

```python
# 注释说 MITM 防护:
# host_key_verify=True 确保 MITM 防护
# 但实际调用中没有 host_key_verify 参数:
self._conn = await asyncssh.connect(
    self.host,
    username=self.username,
    password=self.password,
    client_keys=self._client_keys if self._client_keys else None,
    known_hosts=self._known_hosts if self._known_hosts else None,
    timeout=SSHDeployConfig.CONNECT_TIMEOUT,
)
```

**风险**: 如果 `~/.ssh/known_hosts` 不存在且 `client_keys` 可用，asyncssh 的默认行为可能不完全符合预期的严格验证。

**建议**: 显式设置 `host_key_verify=True` 以确保 MITM 防护:
```python
self._conn = await asyncssh.connect(
    ...
    host_key_verify=True,  # 显式启用 MITM 防护
)
```

### 2. SSH Connection Pool get_connection() 锁粒度问题 (Important)

**位置**: `scripts/ssh_deploy.py` 第 428-458 行

**问题**: `is_closed()` 检查和 `_active_count` 增量操作不在同一原子区域:
```python
async with self._lock:
    if self._available[host]:
        conn = self._available[host].pop(0)
        if not conn.is_closed():
            self._active_count += 1
            return conn
# ... 锁释放后执行新连接获取 ...
conn = await asyncssh.connect(...)  # 此时锁已释放
async with self._lock:
    self._active_count += 1  # _active_count 修改与获取操作不原子
```

**风险**: 多协程环境下可能导致 `_active_count` 与实际活跃连接数不一致。

**建议**: 重构以确保整个获取和计数操作在单个锁区域内完成。

### 3. RBAC Secret Key 运行时不可更新 (Suggestion)

**位置**: `src/algo_studio/api/middleware/rbac.py` 第 40 行

**问题**: `_rbac_secret_key` 在模块导入时读取环境变量，运行时无法更新:
```python
_rbac_secret_key = os.environ.get("RBAC_SECRET_KEY", "")
```

**影响**: 更改环境变量后需要重启服务才能生效。

**建议**: 如果需要动态密钥轮换，考虑使用函数获取或添加 reload 机制。

## 亮点

### HMAC-SHA256 实现 (正确)
- 使用 `hmac.new()` 和 `hashlib.sha256`
- 使用 `hmac.compare_digest()` 进行恒定时间比较 (防止时序攻击)
- 消息格式为 `f"{user_id}:{timestamp_str}"` 防止签名跨用户重用
- 5 分钟时间窗口配合 `abs()` 同时防止过去和未来的重放攻击

### SSH 连接池原子操作 (正确)
```python
async def release_connection(self, host: str, conn: asyncssh.Connection):
    async with self._lock:
        if conn.is_closed():
            self._active_count -= 1
        elif len(self._available[host]) < self.max_per_host:
            self._available[host].append(conn)
        else:
            conn.close()
            self._active_count -= 1
```
锁保护整个检查-修改流程，防止竞态条件。

### 命令验证白名单 (良好)
使用正则表达式白名单 + 危险模式黑名单的双重检查:
```python
ALLOWED_COMMANDS = [
    r"^ray\s+start\s+--address=.+",
    r"^rsync\s+-avz\s+--delete.*",
    ...
]
FORBIDDEN_PATTERNS = [
    r";\s*rm\s+-rf",
    r">\s*/dev/sd",
    ...
]
```

### 测试覆盖
- RBAC 测试: 22+ 个测试用例，覆盖签名验证、角色权限、时间戳验证
- SSH 测试: 使用 Mock 测试连接池原子性，验证危险命令过滤逻辑

## 建议

1. **立即修复**: 在 `asyncssh.connect()` 调用中添加 `host_key_verify=True` 显式参数
2. **重构锁区域**: 确保 `get_connection()` 中 `_active_count` 的修改与连接获取在同一原子区域内
3. **添加集成测试**: SSH 部署目前仅使用 Mock 测试，建议添加真实环境的冒烟测试 (标记为 `@pytest.mark.integration`)
4. **文档更新**: 更新 SSH 部署设计文档，说明 host_key_verify 配置

## 总结

Round 4 的 RBAC/HMAC 和 SSH 部署安全修复整体实现质量较高:
- HMAC-SHA256 实现完全正确
- SSH Key 认证 + 连接池原子操作设计合理
- 5 分钟重放攻击防护窗口适当
- 命令验证白名单机制有效

需要关注的是 SSH host_key_verify 显式配置缺失和连接池锁粒度问题，这两个问题虽不致命，但建议在下一迭代中修复以达到完整的安全合规。