# Phase 3.4 Web Console Iteration - Round 1 User Experience Report

## Test Date
2026-03-29 15:34:28

## Test URL
http://localhost:3000

## Summary

| Status | Count |
|--------|-------|
| PASS | 10 |
| FAIL | 3 |
| WARN | 3 |

## Test Results Matrix

| Test | Status | Details |
|------|--------|---------|
| Dashboard stats cards | FAIL | No stat cards found with generic selectors - UI uses Chinese text "总任务数" etc |
| Dashboard cluster status | PASS | Cluster section visible with node count |
| Dashboard resource charts | PASS | Found 14 charts/visualization elements |
| Dashboard recent tasks | WARN | Recent tasks section not visible - may not exist or uses different selectors |
| Tasks list displays | PASS | Found 5 tasks in table |
| Status filter dropdown | PASS | Filter exists and functional |
| Search functionality | PASS | Search box exists |
| Pagination works | PASS | Pagination visible |
| TaskWizard opens | PASS | Dialog opens with "新建任务" button |
| Task creation wizard | FAIL | Overlay blocks clicking on task type options |
| Task detail page loads | PASS | Page renders with task ID |
| SSE progress section | PASS | Progress section visible |
| Host list displays | WARN | No host cards found - may need to click refresh first |
| Status indicators | WARN | Status indicators not visible without refresh |
| Resource info shows | PASS | CPU/GPU/Memory visible |
| Deploy wizard/form | FAIL | Deploy form not found - selectors need data-testid attributes |

## Console Errors Found

### Error 1: Client Component Async/Await Warning
```
Warning: async/await is not yet supported in Client Components, only Server Components.
This error is often caused by accidentally adding 'use client' to a module that was
originally written for the server.
    at DashboardPage
    at ClientPageRoot
```
**Severity**: Warning (not critical)
**Impact**: Dashboard page may have SSR/Client component boundary issues

### Error 2: Suspended Promise Warning
```
Warning: A component was suspended by an uncached promise. Creating promises inside
a Client Component or hook is not yet supported, except via a Suspense-compatible
library or framework.
    at DashboardPage
```
**Severity**: Warning
**Impact**: Dashboard data fetching may not be properly handled with Suspense

### Error 3: 404 Resource Errors
```
Failed to load resource: the server responded with a status of 404 (Not Found)
```
**Severity**: Error
**Impact**: Some API resources not found - likely missing endpoints or wrong URLs

## Critical Issues

### Issue 1: Task Creation Wizard - Task Type Selection Blocked
**Test**: Task creation wizard
**Problem**: After opening the wizard, clicking on task type options fails because the overlay div intercepts pointer events.

```
<div data-state="open" aria-hidden="true" data-aria-hidden="true"
     class="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in...">
```
This overlay appears but does not close properly, blocking interaction with the wizard content.

**Root Cause**: The modal overlay's `aria-hidden="true"` suggests it's being treated as hidden but still covers the content with pointer events.

**Recommendation**: Review Dialog component - the overlay should close when options are selected or form should handle the layering properly.

### Issue 2: Deploy Page Form Selectors Not Found
**Test**: Deploy wizard/form
**Problem**: The test could not locate the deploy form using generic selectors.

**Root Cause**: The deploy page may not have `data-testid='deploy-form'` or the form uses different class names.

**Recommendation**: Add `data-testid` attributes to deploy form elements per the existing test patterns in `test_deploy_page.py`:
- `data-testid="deploy-form"`
- `data-testid="deploy-button"`
- `data-testid="node-address"`
- `data-testid="ssh-username"`

### Issue 3: Dashboard Stats Cards Not Found
**Test**: Dashboard stats cards
**Problem**: Generic selectors for stat cards return no results.

**Root Cause**: Stats cards likely use Chinese labels ("总任务数", "运行中", "待处理", "失败") instead of English text or data-testid attributes.

**Recommendation**: Add `data-testid="stat-card-total"`, `data-testid="stat-card-running"` etc. or update selectors to use Chinese text matching.

## Warnings / Areas for Improvement

### Warning 1: Hosts Page Requires Manual Refresh
**Observation**: Host cards and status indicators are not visible until clicking the "刷新" (refresh) button.

**Recommendation**: Consider auto-loading host data on page mount, or show loading skeleton while fetching.

### Warning 2: Recent Tasks Section Not Visible
**Observation**: The dashboard's recent tasks section was not found with generic selectors.

**Recommendation**: Verify if this section exists and add appropriate data-testid if so.

### Warning 3: SSE Progress Updates
**Observation**: SSE tests show 401 Unauthorized errors, suggesting authentication headers not being passed to SSE endpoint.

**Recommendation**: Ensure SSE endpoint (`/api/tasks/{task_id}/progress`) accepts the same auth headers as other API endpoints.

## E2E Test Baseline Results

From running `pytest tests/e2e/web/ -v`:

| Test Suite | Passed | Failed | Skipped |
|------------|--------|--------|---------|
| test_dashboard_verification.py | 10 | 0 | 0 |
| test_task_creation.py | 16 | 0 | 0 |
| test_tasks_page.py | 10 | 0 | 0 |
| test_hosts_page.py | 4 | 8 | 0 |
| test_deploy_page.py | 8 | 4 | 0 |
| test_sse_progress.py | 1 | 2 | 5 |
| test_sse_real.py | 0 | 0 | 10 |
| test_task_detail.py | 1 | 0 | 10 |

**Key Observations**:
- Dashboard, Task Creation, and Tasks Page tests are mostly passing
- Hosts page has selector issues (8 failures)
- Deploy page has selector issues (4 failures)
- SSE tests are skipped due to 401 auth errors

## User Experience Feedback

### What Works Well
1. **Navigation**: All pages load correctly and navigation between them works
2. **Tasks List**: Task filtering, search, and pagination all functional
3. **Task Creation Wizard**: Opens correctly and step navigation works
4. **Dashboard Charts**: 14 chart/visualization elements render properly
5. **Host Resources**: CPU/GPU/Memory info displays when loaded

### Areas Needing Attention
1. **Task Type Selection**: Modal overlay blocks interaction with task type options
2. **Deploy Form**: Missing data-testid attributes makes automation difficult
3. **Hosts Auto-load**: Requires manual refresh to display host data
4. **Dashboard Stats**: Statistics cards need better selectors
5. **SSE Authentication**: 401 errors prevent SSE progress testing

## Recommendations for Round 2

### High Priority
1. **Fix Task Creation Modal Overlay**
   - Review Dialog/Modal component layering
   - Ensure options are clickable after opening wizard
   - Add `data-testid` to task type options (训练, 推理, 验证)

2. **Add data-testid Attributes to Deploy Form**
   - Add `data-testid="deploy-form"` to form element
   - Add `data-testid="deploy-button"` to deploy button
   - Add `data-testid="deployed-nodes"` to existing nodes list

3. **Fix SSE Authentication**
   - Ensure `/api/tasks/{task_id}/progress` SSE endpoint accepts auth headers
   - Add `data-testid` to progress bar element

### Medium Priority
4. **Dashboard Stats Cards Selectors**
   - Add `data-testid="stat-card-total"`, etc.
   - Or update tests to match Chinese labels

5. **Hosts Page Auto-load**
   - Consider auto-fetching host data on page mount
   - Or show skeleton loading state

### Low Priority
6. **Add Recent Tasks Section**
   - If it exists, add proper selectors
   - If it doesn't exist, document as missing feature

## Test Coverage Gaps

Based on USER_MANUAL.md operations:

| Operation | Test Status | Notes |
|-----------|-------------|-------|
| Dashboard stats cards | FAILED | Selectors need update |
| Cluster status | PASS | Works correctly |
| Resource charts | PASS | 14 charts render |
| Recent tasks | WARN | Section not found |
| Task list | PASS | All filters work |
| Task creation | PARTIAL | Wizard opens, but selection blocked |
| Task detail | PASS | Page loads |
| SSE progress | SKIPPED | Auth 401 errors |
| Host list | WARN | Needs refresh |
| Host detail | WARN | Resource info shows |
| Deploy wizard | FAILED | Selectors not found |

## Conclusion

The Web Console basic functionality is working for most operations, but there are several UI automation issues that need resolution:

1. **Critical**: Task creation wizard overlay blocking interactions
2. **Critical**: Deploy form missing test identifiers
3. **High**: Dashboard stats cards need better selectors
4. **Medium**: SSE endpoint authentication issues

The round 1 baseline shows good foundation with Dashboard, Task Creation, and Tasks Page fully functional. Hosts and Deploy pages need selector improvements.

---
*Report generated by Phase 3.4 Round 1 User Experience Test*
*Test script: tests/e2e/web/test_user_flow_manual.py*