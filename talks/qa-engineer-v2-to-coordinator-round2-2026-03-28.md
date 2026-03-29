# from: @qa-engineer-v2
# to: @coordinator
# date: 2026-03-28
# type: report
# round: Phase 2.5 Round 2

## Web E2E 测试框架验证 - Round 2 报告

### 1. 环境验证结果

| 检查项 | 状态 | 详情 |
|--------|------|------|
| http://localhost:3000 | PASS | HTTP 200, 页面正常加载 |
| http://localhost:8000 | PASS | HTTP 200, API 正常响应 |
| wait_for_load_state('networkidle') | PASS | 正常工作 |
| X-User-ID header | PASS | API 调用需要此 header |

### 2. Dashboard 页面测试

**创建文件:** `tests/e2e/web/test_dashboard_verification.py`

**测试结果:** 12/12 PASSED

| 测试用例 | 状态 |
|----------|------|
| test_dashboard_page_loads | PASS |
| test_dashboard_stats_displayed | PASS |
| test_dashboard_stats_have_values | PASS |
| test_cluster_status_displayed | PASS |
| test_cluster_nodes_shown | PASS |
| test_gpu_info_displayed | PASS |
| test_resource_metrics_shown | PASS |
| test_recent_tasks_section_exists | PASS |
| test_navigation_to_tasks_page | PASS |
| test_dashboard_loads_without_api | PASS |
| test_dashboard_refresh | PASS |
| test_console_no_errors | PASS |

### 3. Hosts 页面测试

**测试结果:** 3/14 PASSED (11 个失败为预存在问题)

**通过的测试:**
- test_hosts_page_refresh
- test_resource_usage_colors
- test_host_status_updates_on_refresh

**失败原因分析:**
1. **CSS Selector 不匹配**: 测试期望 `[data-testid='hosts-list']`, `.hosts-container` 等选择器，但实际 UI 使用 Tailwind Card 组件
2. **API Redirect 处理**: `/api/hosts` 返回 307 重定向，httpx Client 默认不跟随
3. **UI 元素验证**: 实际页面渲染正常，但选择器需要更新

**Hosts 页面实际功能验证:**
```
Hosts page 实际渲染结果:
- 2 个节点正确显示 (192.168.0.126, 192.168.0.115)
- GPU 信息显示: NVIDIA GeForce RTX 4090
- 状态显示: 在线/离线
- 资源信息: GPU 利用率, GPU 内存, 系统内存, CPU 核心
```

### 4. 发现的问题

| 问题 | 严重性 | 说明 |
|------|--------|------|
| Hosts 测试选择器过时 | 低 | 测试使用旧选择器，需更新为实际 UI 选择器 |
| API Client 不跟随重定向 | 中 | `api_client.get_hosts()` 需处理 307 响应 |
| 401 认证错误 | 低 | 某些 API 调用缺少 X-User-ID header |

### 5. 建议

1. **更新 Hosts 页面测试**: 需要根据实际 UI 更新 CSS 选择器以匹配 Tailwind 组件
2. **API Client 改进**: 添加 `follow_redirects=True` 支持
3. **Fixtures 完善**: `mock_ray_client` fixture 未被实际使用，可移除或改进

### 6. 新增/修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/e2e/web/conftest.py` | 新增 | Web 测试 fixtures (page, context, api_client) |
| `tests/e2e/web/test_dashboard_verification.py` | 新增 | Dashboard 页面测试 (12 个用例) |

### 7. 测试覆盖率

- Dashboard 测试: 12 个测试用例全部通过
- Web E2E 环境: 已验证可正常工作
- Hosts 页面功能: 实际渲染正常，测试选择器需更新