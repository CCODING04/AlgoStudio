# Phase 3.5 R5 任务派发: 算法同步脚本扩展

**From:** Coordinator
**Date:** 2026-03-29
**To:** @devops-engineer
**Topic:** R5 Sprint 2-3 算法同步脚本扩展

---

## 任务背景

Phase 3.5 第 5 轮迭代 (R5)，Sprint 2-3 阶段。

### 功能 2: Dashboard 部署功能 - 算法同步扩展

**参考**: `talks/devops-engineer-to-coordinator-2026-03-29-001.md`

---

## 任务清单

### Task 1: 算法同步脚本扩展

**问题**: 当前部署只启动 Ray Worker，不同步算法代码到 Worker 节点

**要求**:
1. 扩展 `scripts/ssh_deploy.py` 支持算法目录同步
2. 同步方式:
   - 共享存储路径 (JuiceFS/NAS) - 推荐
   - 或 rsync 算法目录到节点
3. 确保集群内算法版本一致

### Task 2: 部署时同步算法

**要求**:
1. 部署 Worker 时同步指定算法
2. 记录同步状态到部署结果
3. 验证同步完成

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/devops-engineer-to-coordinator-2026-03-29-004.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30