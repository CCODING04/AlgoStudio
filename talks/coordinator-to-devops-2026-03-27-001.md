# 任务分配：SSH 部署 Round 2 安全修复

**from:** @coordinator
**to:** @devops-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0
**ref:** round1-review

---

## 任务背景

Round 1 架构评审发现以下严重问题需要修复：

### 必须修复

1. **known_hosts=None - Man-in-the-Middle 风险**
   - 位置: `scripts/ssh_deploy.py` 第 218 行
   - 修复: 使用 `known_hosts=[]` 首次连接接受并保存密钥

2. **命令验证未启用**
   - 位置: `scripts/ssh_deploy.py`
   - 修复: 在 `_run_command()` 中调用 `validate_command()`

3. **锁逻辑 Bug**
   - 位置: 第 676-686 行
   - 问题: 锁已存在时立即返回而不等待部署完成
   - 修复: 等待锁释放后再返回已存在的 task_id

4. **密码内存加密**
   - 问题: 文档提到"内存加密"但代码直接使用明文
   - 建议: 实现 SSH key 认证或密码加密

5. **部署进度持久化**
   - 位置: `DeployProgressStore` 类
   - 问题: 重启后部署进度丢失
   - 建议: 使用 Redis 持久化

## 任务内容

1. 修复 SSH 部署脚本安全漏洞 (P0)
2. 实现部署进度持久化
3. 添加超时强制终止机制
4. 完善 CI/CD 配置 (GitHub Actions)

## 输入

- Round 1 评审报告: `docs/superpowers/schedule/round1-review.md`
- SSH 部署设计: `docs/superpowers/design/ssh-deployment-design.md`

## 输出

- 修复后的 `scripts/ssh_deploy.py`
- CI/CD 配置: `.github/workflows/`

## 截止日期

Week 2 结束前 (2026-03-28)

## 状态

- [x] 任务已接收
- [x] known_hosts 修复
- [x] 命令验证启用
- [x] 锁逻辑修复
- [x] 进度持久化 (Redis)
- [x] CI/CD 配置

## 完成时间

2026-03-27

## 修复详情

1. **known_hosts=[]** - 3处 `known_hosts=None` 已替换为 `known_hosts=[]`
2. **命令验证** - `_run_command()` 现在调用 `validate_command()`
3. **锁逻辑** - `deploy_worker()` 现在等待已有部署完成后再返回
4. **Redis 持久化** - `DeployProgressStore` 使用 Redis (localhost:6380) 持久化
5. **CI/CD** - 已有 test.yml，新增 deploy.yml
