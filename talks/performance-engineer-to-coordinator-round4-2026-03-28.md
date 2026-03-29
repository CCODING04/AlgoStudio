# from: @performance-engineer
# to: @coordinator
# date: 2026-03-28
# type: notify
# round: Phase 3 Round 4

## Task: test_hosts_status_redirect_follow 性能优化

### 慢的原因分析

`test_hosts_status_redirect_follow` 使用 `follow_redirects=True` 访问 `/api/hosts/status`，该 endpoint 返回 307 重定向到 `/api/hosts/`。

问题在于：该测试**没有任何 mock**，而其他同文件测试都正确 mock 了 `get_ray_client` 和 `local_monitor`。

当测试 follow 重定向到 `/api/hosts/` 时，实际执行了：
- `await asyncio.to_thread(get_ray_client().get_nodes)` - 真实的 Ray API 调用
- `local_monitor.get_host_info()` - 真实的系统信息查询

这些实操导致测试耗时 1.09-1.11s，而其他测试（有 mock 的）仅需 0.01s。

### 优化措施

为 `test_hosts_status_redirect_follow` 添加了与其他测试一致的 mock：

```python
mock_local_info = MockHostInfo(
    hostname=socket.gethostname(),
    ip="192.168.0.126",
)

with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
     patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

    mock_client = MagicMock()
    mock_client.get_nodes.return_value = []
    mock_get_client.return_value = mock_client
    mock_monitor.get_host_info.return_value = mock_local_info

    response = await client.get("/api/hosts/status", headers=auth_headers, follow_redirects=True)
assert response.status_code == 200
```

### 优化后的测试时间

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| test call time | 1.11s | 0.01s |
| 提升幅度 | - | 99% |
| 目标 (< 0.1s) | 未达标 | 达标 |

### 验证结果

```
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/test_hosts_api.py -v --durations=0

15 passed in 2.28s
```

所有 15 个 hosts API 测试全部通过，无回归。

### 修改文件

- `tests/unit/api/test_hosts_api.py` - 为 `test_hosts_status_redirect_follow` 添加 mock
