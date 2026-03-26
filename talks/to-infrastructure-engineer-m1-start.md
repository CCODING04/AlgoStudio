# 消息: @infrastructure-engineer

**发送者:** @coordinator
**时间:** 2026-03-26
**主题:** M0 接口定义完成 - M1 可以开始了

---

## 状态更新

M0 (接口定义) 已完成。接口定义文档已保存到:

**`docs/superpowers/schedule/M0-interface-definition.md`**

---

## M1 启动准备

根据接口定义文档，Dataset Storage 模块需要提供以下接口供其他模块使用：

### 关键接口 (来自 M0 定义)

1. **数据集位置信息**
   - AI Scheduling 需要读取数据集所在的节点位置
   - 格式: `data_locality: Optional[str] = None  # 数据所在节点 hostname`

2. **存储后端配置**
   - Redis 端口: **6380** (避免与 Ray 6379 冲突)
   - JuiceFS 版本: **1.1.5**
   - NAS 路径: `//192.168.1.70/VtrixDataset`

### M1 任务清单 (来自 schedule.md)

| 任务 | 状态 | 依赖 |
|------|------|------|
| 安装 Docker (Head) | 待开始 | - |
| 配置 Worker NAS 挂载 | 待开始 | - |
| 部署 Redis 容器 (6380) | 待开始 | Docker |
| 配置 JuiceFS | 待开始 | Redis+NAS |
| DVC 集成 | 待开始 | JuiceFS |

---

## 下一步行动

请 @infrastructure-engineer 开始 M1 任务：

1. 首先安装 Docker (Head 节点)
2. 然后配置 Worker NAS 挂载
3. 部署 Redis 容器

---

## 接口文档参考

详细的接口定义请参考:
- `docs/superpowers/schedule/M0-interface-definition.md`
- `docs/superpowers/research/dataset-storage-report.md`

如有问题，请回复此消息或更新 `docs/superpowers/schedule/wait_to_decisions.md`

---

**@coordinator**
