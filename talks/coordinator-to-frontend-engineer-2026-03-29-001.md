# Bug Fix Task: Host Status Display (P1)

**From:** Coordinator
**To:** @frontend-engineer
**Date:** 2026-03-29
**Priority:** P1

---

## Task

Fix Bug 1 in `docs/superpowers/test/ISSUE_BUGS_2026-03-29.md`

### Problem
Frontend /hosts page shows all nodes as "offline" but backend returns status `idle`.

### Root Cause
State value mismatch between frontend and backend:

| Component | Status Values |
|-----------|---------------|
| Backend API (ray_client.py) | `idle`, `busy`, `offline` |
| Frontend (hosts/page.tsx) | `online`, `offline` |

### Fix Required
Modify `src/frontend/src/app/(main)/hosts/page.tsx`:
- Change `status === 'online'` to `status === 'idle'`
- Keep `status === 'offline'` unchanged
- Optionally add mapping: `idle` -> Online, `busy` -> Busy

### Files to Modify
- `src/frontend/src/app/(main)/hosts/page.tsx`

### Verification
After fix, nodes with `idle` status should display as "Online" in the hosts page.

---

Please acknowledge receipt and proceed with the fix.
