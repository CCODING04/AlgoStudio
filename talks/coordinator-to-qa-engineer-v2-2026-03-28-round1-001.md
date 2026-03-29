# Task: Run Full rollback.py Test Suite and Report Coverage

## Context

Phase 3 Testing Improvement - Round 1/8

After @test-engineer fixes the failing test, you need to run the full test suite and report coverage metrics.

## Prerequisites

Wait for @test-engineer to complete the fix (they will notify via talks/).

## Tasks

1. **Run full rollback test suite:**
   ```bash
   cd /home/admin02/Code/Dev/AlgoStudio && PYTHONPATH=src pytest tests/unit/core/test_rollback.py -v --tb=short
   ```

2. **Run coverage analysis:**
   ```bash
   cd /home/admin02/Code/Dev/AlgoStudio && PYTHONPATH=src pytest tests/unit/core/test_rollback.py --cov=src/algo_studio/core/deploy/rollback --cov-report=term-missing --cov-report=html:htmlcov
   ```

3. **Check coverage report:**
   ```bash
   cat htmlcov/index.html | grep -A5 "rollback"
   ```

4. **Report results:**
   - Total tests passed/failed
   - Current coverage percentage
   - Lines not covered (if any)

## Output Format

Report to: `talks/qa-engineer-v2-to-coordinator-2026-03-28-round1-001.md`

```
# Round 1 Coverage Report

## Test Results
- Total: X passed, Y failed

## Coverage
- rollback.py: XX%

## Uncovered Lines
- Line X-Y: [description]
```

## Timing

Run this after @test-engineer notifies you that the fix is complete.
