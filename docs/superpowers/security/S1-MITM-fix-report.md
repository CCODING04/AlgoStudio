# P0 安全修复验证报告

**修复日期:** 2026-03-27
**修复者:** @devops-engineer
**Phase:** Phase 2 Round 3

---

## S1: MITM 防护被禁用

### 问题描述
- **位置:** `scripts/ssh_deploy.py` - `known_hosts=[]`
- **严重性:** P0
- **问题:** 使用空列表禁用 SSH host key 验证，导致中间人攻击风险

### 修复方案
实现了 SSH key 认证替代方案：

1. **新增 `_get_ssh_client_keys()` 函数**
   - 加载 `~/.ssh/id_ed25519`, `id_rsa`, `id_ecdsa` 私钥
   - 用于 SSH key 认证

2. **新增 `_get_known_hosts()` 函数**
   - 返回 `~/.ssh/known_hosts` 路径
   - 用于 host key 验证

3. **修改所有 `asyncssh.connect()` 调用**
   - 移除 `known_hosts=[]`
   - 添加 `client_keys=...` 参数
   - 添加 `known_hosts=...` 参数

### 修复位置
- `scripts/ssh_deploy.py:149-189` - 新增 key 加载函数
- `scripts/ssh_deploy.py:218-233` - `SSHConnectionManager.connect()`
- `scripts/ssh_deploy.py:296-320` - `SSHConnectionManager._retry_or_fail()`
- `scripts/ssh_deploy.py:443-451` - `SSHConnectionPool.get_connection()`

### 验证结果
- [x] 语法检查通过
- [x] `known_hosts=[]` 已从所有 connect 调用中移除
- [x] SSH key 认证已实现
- [x] Host key 验证路径已配置

---

## S3: 连接池竞态条件

### 问题描述
- **位置:** `scripts/ssh_deploy.py` - `release_connection()`
- **严重性:** P0
- **问题:** `is_closed()` 检查在锁外，状态修改在锁内，导致竞态条件

### 修复方案
将 `release_connection()` 改为原子操作：

```python
async def release_connection(self, host: str, conn: asyncssh.Connection):
    async with self._lock:  # 整个操作在锁内
        if conn.is_closed():
            self._active_count -= 1
        elif len(self._available[host]) < self.max_per_host:
            self._available[host].append(conn)
        else:
            conn.close()
            self._active_count -= 1
```

### 修复位置
- `scripts/ssh_deploy.py:460-473` - `SSHConnectionPool.release_connection()`

### 验证结果
- [x] 语法检查通过
- [x] `is_closed()` 检查现在在锁内
- [x] 状态修改与检查原子化
- [x] 消除了检查与修改之间的窗口期

---

## 修复总结

| 问题 | 状态 | 验证 |
|------|------|------|
| S1: MITM 防护 | 已修复 | 通过 |
| S3: 连接池竞态 | 已修复 | 通过 |
| 语法检查 | 通过 | 通过 |

## 下一步
- [ ] 集成测试验证
- [ ] 部署到测试环境验证
