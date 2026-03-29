# from: @coordinator
# to: @infrastructure-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 1

## 任务: JuiceFS 固定 100GB 缓存配置

### 背景
评审团辩论已完成，决策：固定 100GB 缓存。

### 具体任务

1. **配置 JuiceFS 缓存为固定 100GB**
   ```bash
   # 查看当前 JuiceFS 配置
   juicefs config <MOUNT_POINT>

   # 设置固定缓存大小 100GB (102400 MB)
   juicefs config --cache-size 102400 <MOUNT_POINT>

   # 验证配置
   juicefs config <MOUNT_POINT> | grep cache-size
   ```

2. **验证缓存配置生效**
   - 确认缓存大小为 100GB
   - 确认 `--free-space-ratio 0.1` 设置保留 10% 空闲空间

3. **更新文档**
   - 在 `docs/superpowers/schedule/phase3-1-plan.md` 更新任务状态

### 输出
完成后在 `talks/infrastructure-to-coordinator-round1-2026-03-28.md` 汇报：
- 配置结果
- 验证结果
