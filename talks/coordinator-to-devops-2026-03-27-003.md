# 任务分配：CI/CD P0 安全修复

**from:** @coordinator
**to:** @devops-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0

---

## 任务背景

Round 2 架构评审发现以下 P0 安全问题需要修复：

### S6: Secrets 硬编码在 workflow
- 位置: `.github/workflows/deploy.yml`
- 问题: IP 地址和配置直接写在 workflow 中
- 修复: 使用 GitHub secrets 管理敏感信息

## 任务内容

1. 将 Secrets 迁移到 GitHub Secrets
2. 移除硬编码的 IP 地址
3. 添加部署审批流程

## 输入

- Round 2 评审报告: `docs/superpowers/schedule/round2-review.md`
- CI/CD 配置: `.github/workflows/`

## 输出

- 修复后的 GitHub Actions workflows
- 安全性验证报告

## 截止日期

Round 3 结束前

## 状态

- [x] 任务已接收
- [x] Secrets 迁移
- [x] 部署审批流程
