# Phase 3.4 Web Console Iteration - Round 2 User Experience Report

## Test Date
2026-03-29

## Test Summary

| Status | Count | Change from R1 |
|--------|-------|----------------|
| PASS | 61 | +1 |
| FAIL | 22 | +6 |
| SKIP | 26 | -5 |

## Fixed Issues from Round 1

### 1. Dashboard Stats Cards - FIXED
**Status**: PASS

The stats cards now have proper `data-testid` attributes:
- `data-testid="stat-card-total"`
- `data-testid="stat-card-running"`
- `data-testid="stat-card-pending"`
- `data-testid="stat-card-failed"`

Verified via HTML inspection and `test_dashboard_verification.py` passes all 12 tests.

### 2. TaskWizard Modal Overlay - PARTIALLY FIXED
**Status**: PARTIAL

The z-index fix (`className="z-[60]"`) on `SelectContent` was applied but the test still fails because Radix UI's `SelectItem` components only render their `data-testid` attributes when the dropdown is **open**.

The test `test_task_type_options` fails because it looks for `[data-testid='task-type-train']` without first opening the dropdown.

### 3. Deploy Form data-testid - PARTIALLY FIXED
**Status**: PARTIAL

The following `data-testid` attributes exist in the code but do NOT propagate to the DOM due to Radix UI component behavior:
- `data-testid="deploy-algorithm-select"` (on Select component)
- `data-testid="deploy-node-select"` (on Select component)

The following ARE present in the DOM:
- `data-testid="deploy-form"` - PASS
- `data-testid="deploy-submit-button"` - PASS

## Remaining Issues

### Critical: SSE Still Returns 401 Unauthorized

**Test**: `test_sse_connection_establishment`
**Error**: `assert 401 == 200`

The SSE endpoint `/api/tasks/{task_id}/progress` still returns 401 Unauthorized. This is a backend authentication issue, not a frontend issue.

### Critical: Radix UI data-testid Not Propagating

Radix UI components (`Select`, `SelectContent`, `SelectItem`) do not automatically forward `data-*` attributes to their rendered DOM elements.

**Affected tests**:
- `test_task_type_options` - Cannot find `[data-testid='task-type-train']`
- `test_existing_deployed_nodes_shown` - Missing `deployed-nodes` data-testid
- `test_deploy_page_ssh_key_option` - SSH key option not found

**Solution Options**:
1. Use different selectors (text content, role attributes)
2. Add `data-testid` to wrapper elements instead of Radix components
3. Use Radix's `data-radix` attributes or aria-controls to locate elements

### Deploy Page Issues

| Test | Status | Issue |
|------|--------|-------|
| `test_deployed_node_shows_status` | FAIL | JSON decode error |
| `test_deployment_cancellable` | FAIL | Submit button disabled - can't proceed without algorithm selection |
| `test_deploy_page_ssh_key_option` | FAIL | SSH key selector not found |

### Hosts Page Issues

| Test | Status | Issue |
|------|--------|-------|
| `test_hosts_page_loads` | FAIL | "刷新" button not found |
| `test_hosts_list_shows_all_nodes` | FAIL | 307 redirect |
| Multiple others | FAIL | JSON decode errors |

This suggests the API is returning redirects instead of JSON for the hosts endpoints.

## USER_MANUAL Operations Verification

| Operation | Status | Notes |
|-----------|--------|-------|
| Dashboard stats cards | PASS | data-testid now present |
| Cluster status | PASS | Works correctly |
| Resource charts | PASS | Renders properly |
| Task list displays | PASS | Filters work |
| TaskWizard opens | PASS | Dialog opens |
| Task type selection | FAIL | Dropdown must be opened first |
| Task detail page | PASS | Page loads |
| SSE progress | FAIL | 401 Unauthorized |
| Host list | FAIL | API errors |
| Deploy wizard | PARTIAL | Some selectors work |

## Detailed Test Results

### Dashboard Verification Tests (12/12 PASS)

All dashboard tests pass:
- Stat cards with data-testid
- Cluster status section
- Resource charts
- Navigation elements

### Task Creation Tests (18/19 PASS, 1 FAIL)

The single failure is `test_task_type_options` which requires opening the dropdown before the data-testid becomes visible.

### Deploy Page Tests (6/15 PASS, 9 FAIL)

Passing tests:
- Page loads
- Wizard form present
- Step indicator works
- Navigation buttons exist
- Empty state shows

Failing tests:
- Algorithm dropdown selectors
- Node dropdown selectors
- Existing deployed nodes
- SSH key option
- Multiple deployment prevention

### SSE Progress Tests (0/3 PASS, 3 FAIL, 5 SKIP)

All failing due to 401 Unauthorized error from backend.

### Hosts Page Tests (4/12 PASS, 8 FAIL)

API returning 307 redirects instead of proper JSON responses.

## Recommendations for Round 3

### High Priority

1. **Fix Radix UI Test Selectors**
   - Instead of `[data-testid='task-type-train']`, use text-based selectors like `text=训练 (Train)`
   - Or click the `SelectTrigger` first, wait for dropdown to open, then look for items

2. **Fix SSE Authentication**
   - Backend needs to properly handle authentication for SSE endpoint
   - Check if `/api/tasks/{task_id}/progress` requires auth headers

3. **Add deployed-nodes data-testid**
   - Add explicit wrapper div with `data-testid="deployed-nodes"` around existing nodes list

### Medium Priority

4. **Fix Hosts API**
   - Investigate why `/api/hosts` returns 307 redirect
   - Check if authentication is required for hosts endpoint

5. **Add SSH Key UI**
   - If SSH key upload is a required feature, add proper UI elements
   - If not, update tests to not expect this feature

### Low Priority

6. **Update Test Scripts**
   - Update `test_task_type_options` to open dropdown before checking
   - Update deploy tests to handle disabled buttons properly

## Conclusion

Round 2 shows mixed results:
- **Improvements**: Dashboard stats cards work, TaskWizard overlay z-index fixed
- **Remaining**: Radix UI data-testid propagation, SSE auth, Hosts API issues

The core UI framework is solid, but there are integration issues with:
1. Backend authentication for SSE
2. API endpoints returning redirects instead of JSON
3. Test selectors needing adjustment for Radix UI behavior

---
*Report generated by Phase 3.4 Round 2 User Experience Test*
