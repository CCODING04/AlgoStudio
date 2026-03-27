# 任务分配：SSH 部署 P0 安全修复

**from:** @coordinator
**to:** @devops-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0

---

## 任务背景

Round 2 架构评审发现以下 P0 安全问题需要修复：

### S1: MITM 防护被禁用
- 位置: `scripts/ssh_deploy.py` - `known_hosts=[]`
- 修复: 使用 SSH key 认证或严格的 known_hosts 管理

### S3: 连接池竞态条件
- 位置: `scripts/ssh_deploy.py` - `release_connection()`
- 修复: 添加原子操作或锁保护

## 任务内容

1. 修复 `known_hosts=[]` 问题 - 实现 SSH key 认证
2. 修复连接池竞态条件 - 添加原子操作
3. 验证修复后的安全性

## 输入

- Round 2 评审报告: `docs/superpowers/schedule/round2-review.md`
- SSH 部署脚本: `scripts/ssh_deploy.py`

## 输出

- 修复后的 `scripts/ssh_deploy.py`
- 安全性验证报告

## 截止日期

Round 3 结束前

## 状态

- [x] 任务已接收
- [x] known_hosts 修复
- [x] 连接池竞态修复
