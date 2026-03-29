# Phase 3 Round 2 - SSH Rollback Mock Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development

**Goal:** Add mock tests for `RollbackService` SSH rollback methods to increase coverage from 38% to 70%+

**Architecture:** Mock `asyncssh.connect` to simulate SSH connections without requiring real network access

**Tech Stack:** pytest, unittest.mock, AsyncMock

---

## SSH Methods to Test

| Method | Command Executed | Test Focus |
|--------|-----------------|------------|
| `_rollback_ray()` | `ray stop` | SSH connection, command validation |
| `_rollback_code()` | `rm -f ~/.code_synced` | Code marker removal |
| `_rollback_deps()` | `rm -f ~/.deps_installed` | Deps marker removal |
| `_rollback_venv()` | `rm -rf ~/.venv-ray` | Venv directory removal |
| `_rollback_sudo()` | `sudo rm -f /etc/sudoers.d/admin02` | Sudoers file removal |
| `_rollback_connecting()` | `rm -f ~/.ssh/authorized_keys` | SSH keys revocation |

---

## Test Scenarios per SSH Method

### 1. Successful Execution
- Mock `asyncssh.connect` returns mock connection
- Mock `conn.run()` returns exit_status=0
- Verify command is executed

### 2. SSH Connection Failure (DisconnectError)
- Mock `asyncssh.connect` raises `DisconnectError`
- Verify graceful handling (logs warning, no exception)

### 3. SSH Channel Error (ChannelOpenError)
- Mock `asyncssh.connect` raises `ChannelOpenError`
- Verify graceful handling

### 4. Missing SSH Credentials
- Snapshot config has no password
- Verify method skips and returns early

### 5. Command Validation Failure
- If command doesn't pass `validate_rollback_command`, should skip

### 6. Command Non-Zero Exit Status
- Mock `conn.run()` returns non-zero exit_status
- Verify graceful handling

---

## Files to Modify

- **Test**: `tests/unit/core/test_rollback.py` - Add SSH mock test classes

---

## Task Checklist

- [ ] **Task 1: Add TestRollbackRay class with mocked SSH**
  - [ ] test_rollback_ray_success
  - [ ] test_rollback_ray_disconnect_error
  - [ ] test_rollback_ray_channel_error
  - [ ] test_rollback_ray_no_credentials

- [ ] **Task 2: Add TestRollbackCode class with mocked SSH**
  - [ ] test_rollback_code_success
  - [ ] test_rollback_code_disconnect_error
  - [ ] test_rollback_code_no_credentials

- [ ] **Task 3: Add TestRollbackDeps class with mocked SSH**
  - [ ] test_rollback_deps_success
  - [ ] test_rollback_deps_disconnect_error
  - [ ] test_rollback_deps_no_credentials

- [ ] **Task 4: Add TestRollbackVenv class with mocked SSH**
  - [ ] test_rollback_venv_success
  - [ ] test_rollback_venv_disconnect_error
  - [ ] test_rollback_venv_no_credentials

- [ ] **Task 5: Add TestRollbackSudo class with mocked SSH**
  - [ ] test_rollback_sudo_success
  - [ ] test_rollback_sudo_disconnect_error
  - [ ] test_rollback_sudo_no_credentials

- [ ] **Task 6: Add TestRollbackConnecting class with mocked SSH**
  - [ ] test_rollback_connecting_success
  - [ ] test_rollback_connecting_disconnect_error
  - [ ] test_rollback_connecting_no_credentials

- [ ] **Task 7: Run tests and verify coverage improvement**
  - [ ] Run pytest with coverage
  - [ ] Verify coverage > 70%
  - [ ] Report new test count

---

## Expected Output

- **New tests**: ~18-24 test cases
- **Coverage increase**: 38% → 70%+
- **Execution time**: < 5 seconds
- **New issues found**: (to be reported)
