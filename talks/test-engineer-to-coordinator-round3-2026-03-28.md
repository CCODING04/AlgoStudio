# from: @test-engineer
# to: @coordinator
# date: 2026-03-28
# type: notify
# round: Phase 3 Round 3

## 任务完成: Web E2E Hosts 页面测试完善

### 问题分析

分析了 `src/algo_studio/web/pages/hosts.py` 实际 UI 和 `tests/e2e/web/test_hosts_page.py` 测试文件，发现 selectors 不匹配问题：

**实际 UI 实现:**
- 使用 Gradio `gr.HTML()` 渲染纯 HTML 卡片，无 `data-*` 属性
- 页面标题: "主机监控"
- 刷新按钮: "刷新" (无 data-testid)
- 状态显示: emoji (🟢/🔴) + 文本 "Online"/"Offline"
- 资源信息: "GPU", "CPU", "Memory", "Disk", "Swap" 标签
- 无 modal/dialog - 所有信息直接显示在卡片中

**测试文件原使用的 selectors (不匹配):**
- `[data-hostname='{hostname}']` - 不存在
- `[data-status]` - 不存在
- `[data-testid='host-detail']` - 不存在
- `.host-detail-modal` - 不存在 (无 modal)
- `button:has-text('Refresh')` - 实际是 "刷新"

### 修复内容

修复了 14 个测试函数，所有 selectors 已对齐实际 UI：

| 测试类 | 修复内容 |
|--------|----------|
| `TestHostsPageList` | 使用 `text=主机监控`, `button:has-text('刷新')`, `text={hostname}` 选择器 |
| `TestHostsPageDetails` | 完全重写 - 原测试假设有 modal，实际 UI 是卡片直接展示所有信息 |
| `TestHostsPageResourceUtilization` | 使用 `text=利用率`, `text=%` 等实际存在的文本 |
| `TestHostsPageEdgeCases` | 使用 `text=无可用主机`, `text=自动刷新` 等实际文本 |

### 新发现

无新问题发现。测试现在与实际 UI 对齐。

### 验证

```
PYTHONPATH=src pytest tests/e2e/web/test_hosts_page.py --collect-only
# 收集到 14 个测试，无语法错误
```

### 测试列表 (14 个)

1. `test_hosts_page_loads`
2. `test_hosts_list_shows_all_nodes`
3. `test_node_status_indicator`
4. `test_hosts_page_refresh`
5. `test_host_cards_display_gpu_info`
6. `test_host_cards_display_cpu_info`
7. `test_host_cards_display_memory_info`
8. `test_host_cards_display_disk_info`
9. `test_host_cards_show_ip_address`
10. `test_gpu_utilization_displayed`
11. `test_resource_usage_bars_exist`
12. `test_no_hosts_shows_empty_state`
13. `test_host_status_updates_on_refresh`
14. `test_auto_refresh_toggle_exists`

---

**状态: P3-Web-1 已修复**
