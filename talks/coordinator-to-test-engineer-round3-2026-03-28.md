# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3 Round 3

## 任务: Web E2E Hosts 页面测试完善

### 当前状态
- Dashboard E2E 测试: 12 通过
- Hosts 页面测试: 存在 selector 不匹配问题

### 待完成问题
| ID | 问题 | 严重性 |
|----|------|--------|
| P3-Web-1 | Hosts 页面测试 selector 不匹配 | Medium |

### 具体任务

1. **分析 Hosts 页面实际 CSS selectors**
   - 检查 `src/algo_studio/web/pages/hosts.py` 实际使用的 CSS classes
   - 对比 `tests/e2e/web/test_hosts_page.py` 中的 selectors

2. **更新 Hosts 页面测试**
   - 修复 CSS selector 不匹配
   - 确保测试与实际 UI 对齐

3. **创建回复文件**
   完成后在 `talks/test-engineer-to-coordinator-round3-2026-03-28.md` 汇报：
   - 修复的测试数量
   - 更新的 selectors
   - 发现的新问题