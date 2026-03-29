# 如何写好一份 AGENTS.md

> 这份文档指导 AI agent（如 Claude Code）为项目编写高质量的 `AGENTS.md`。
> 
> `AGENTS.md` 是 agent 的"行为宪法"——每次启动时读取，确保它知道**自己是谁、要做什么、怎么做事**。

---

## 一、核心原则

### 为什么需要 AGENTS.md？

AI agent 没有持久记忆。每次新会话，它都是"从零醒来"。`AGENTS.md` 是它快速理解项目的唯一锚点。

没有它 → agent 瞎猜 → 犯错 → 流程混乱  
有它 → agent 有章可循 → 行为一致 → 产出稳定

### 好的 AGENTS.md 是什么样的？

| 特征 | 说明 |
|------|------|
| **具体** | 不说"保持代码质量"，而是"每个函数必须有 docstring" |
| **可执行** | 每条规则都能被检查（是/否），不是模糊建议 |
| **分优先级** | 核心约束在前，参考信息在后 |
| **精简** | 控制在 200 行以内，太长没人读 |
| **动态** | 项目状态变化时更新（当前在做什么、下一步是什么） |

---

## 二、推荐结构

```markdown
# AGENTS.md — [项目名称]

## 0. 项目概览（2-3 句话）
> 这个项目是什么、解决什么问题、技术栈是什么

## 1. 当前状态（最重要！）
> - 当前在做什么阶段/任务
> - 上次停在哪里
> - 下一步要做什么
> - 已知的阻塞/问题

## 2. 项目结构
> 关键目录和文件的作用，让 agent 知道去哪找东西

## 3. 开发协议（行为规则）
> agent 必须遵守的流程和约束

## 4. 接口约定
> 模块之间的边界、API 契约、数据格式

## 5. 常用命令
> 启动、测试、部署等常用操作

## 6. 参考文档
> 其他详细文档的索引（不要在这里写全文，给链接就行）
```

---

## 三、每个部分怎么写

### 0. 项目概览

**一句话定义** + **核心功能** + **技术栈**

```markdown
## 0. 项目概览

AlgoStudio 是一个 AI 算法训练平台，支持多机 GPU 调度和算法版本管理。
核心能力：Ray 集群调度、算法仓库、任务管理、主机监控。

技术栈：Python / FastAPI / Ray / Redis / Docker
```

❌ 不要写成：
> "AlgoStudio 是一个革命性的下一代智能算法训练平台，致力于打造算法研发的全生命周期管理..."

---

### 1. 当前状态（动态更新）

**这是最重要的部分！** 每次完成一个阶段任务后，更新这里。

```markdown
## 1. 当前状态

- **当前阶段**：M1 实施中（Dataset Storage 部署）
- **上次进度**：Redis 容器已在 Head 节点部署完成，Worker 节点 NAS 挂载待配置
- **下一步**：
  1. 配置 Worker 节点挂载 //192.168.1.70/VtrixDataset
  2. 部署 JuiceFS 客户端
  3. 运行 `tests/test_dataset.py` 验证存储连通性
- **已知问题**：
  - Worker 节点 `/data` 分区不存在，需先创建
  - Redis 端口 6379 被系统占用，已改用 6380
```

💡 **关键**：这个部分必须由 agent 在每次重大进展后**主动更新**，否则就失去了意义。

---

### 2. 项目结构

列出**关键目录**及其用途，不需要每个文件都列。

```markdown
## 2. 项目结构

```
algo_studio/
├── src/algo_studio/
│   ├── api/          # FastAPI 路由（REST 接口）
│   ├── core/         # 核心逻辑（算法接口、任务调度、Ray 客户端）
│   ├── cli/          # 命令行工具
│   └── monitor/      # 主机监控
├── algorithms/       # 算法实现（每个算法一个目录 + metadata.json）
├── tests/            # 测试（按模块分子目录）
├── scripts/          # 部署脚本
├── docs/
│   └── superpowers/  # 研究报告、设计文档、计划
│       ├── research/ # 调研报告
│       ├── plans/    # 实施计划
│       ├── specs/    # 设计规格
│       └── schedule/ # 进度跟踪
└── talks/            # Agent 间沟通记录
```

**关键约定**：
- 算法必须包含 `metadata.json`（定义输入输出格式）
- 所有新功能需要在 `docs/superpowers/plans/` 下有实施计划
- Agent 间沟通使用 `talks/` 目录
```

---

### 3. 开发协议（核心约束）

**这里是重点。** 写 agent 必须遵守的规则。每条规则要**具体、可检查**。

```markdown
## 3. 开发协议

### 开始工作前（必做）
1. 读 `docs/superpowers/schedule/schedule.md`，确认当前任务和进度
2. 读 `docs/superpowers/backlog/pending-decisions.md`，确认是否有阻塞决策
3. 在 `talks/` 目录创建进度更新文件

### 代码开发
4. 所有新模块必须有对应的测试文件 `tests/test_<module>.py`
5. 函数必须有 docstring，公共 API 必须有类型注解
6. 不直接修改已有接口的签名，需要先在 `docs/superpowers/schedule/` 中记录变更原因
7. 使用 `black` 格式化，`flake8` 检查

### 文档更新（必做）
8. 完成任务后，更新 `schedule.md` 中的任务状态（todo → done）
9. 如有技术决策，记录到 `docs/superpowers/backlog/pending-decisions.md`
10. 如有接口变更，更新 `docs/algorithm_interface_spec.md`

### 提交前
11. 运行 `pytest`，确保所有测试通过
12. 提交信息格式：`type: 简短描述`（如 `feat: 添加节点评分算法`）
```

#### 好的规则 vs 坏的规则

| ❌ 坏的 | ✅ 好的 |
|--------|--------|
| "保持代码质量" | "每个函数必须有 docstring 和类型注解" |
| "记得更新文档" | "完成后更新 schedule.md 中的任务状态为 done" |
| "测试要充分" | "新模块必须有 tests/test_<name>.py，覆盖率 > 80%" |
| "合理设计" | "不修改已有接口签名，需先在 schedule/ 记录变更原因" |

---

### 4. 接口约定

定义模块之间的边界，防止 agent 乱改。

```markdown
## 4. 接口约定

### 算法接口（所有算法必须遵守）
- 入口：`AlgoInterface` 基类（见 `docs/algorithm_interface_spec.md`）
- 必须实现：`train()`, `infer()`, `validate()` 三个方法
- 元数据：`metadata.json` 必须包含 `name`, `version`, `input_schema`, `output_schema`

### API 路由规范
- RESTful 风格，版本前缀 `/api/v1/`
- 响应格式：`{"code": 0, "data": ..., "message": "ok"}`
- 错误码定义见 `docs/api_error_codes.md`

### 模块边界
- `core/` 不依赖 `api/` 和 `monitor/`
- `api/` 可以调用 `core/`，但不能反过来
- `monitor/` 是独立模块，不依赖其他模块
```

---

### 5. 常用命令

减少 agent 猜测怎么运行项目。

```markdown
## 5. 常用命令

```bash
# 安装依赖
uv pip install -e .

# 启动 API 服务
PYTHONPATH="${PYTHONPATH}:$(pwd)/src" uvicorn algo_studio.api.main:app --reload

# 运行测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_scheduler/ -v

# 启动 Ray 集群
./scripts/setup_ray_cluster.sh head

# 提交任务
algo task submit --type train --algo yolo --version v1.0.0 --config '{"epochs": 100}'
```
```

---

### 6. 参考文档

不要在 AGENTS.md 里写完整文档，**给索引**。

```markdown
## 6. 参考文档

| 文档 | 用途 | 何时读 |
|------|------|--------|
| `docs/superpowers/schedule/schedule.md` | 当前任务和进度 | 每次开始工作前 |
| `docs/superpowers/backlog/pending-decisions.md` | 待决策问题 | 需要做决策时 |
| `docs/algorithm_interface_spec.md` | 算法接口规范 | 开发算法时 |
| `docs/superpowers/team/TEAM_STRUCTURE.md` | 团队角色定义 | 理解分工时 |
| `README.md` | 项目安装和使用 | 首次了解项目时 |
```

---

## 四、针对 AlgoStudio 的特别建议

AlgoStudio 使用多 agent 角色扮演模式（架构师、基础设施、后端、AI调度、测试），建议：

### 1. 添加角色识别机制

```markdown
## 7. Agent 角色协议

当被指定为某个角色时，严格遵守该角色的职责边界：

| 角色 | 核心职责 | 只负责 |
|------|---------|--------|
| 架构师 | 技术决策、接口定义、进度协调 | 不写业务代码 |
| 基础设施 | NAS/JuiceFS/Redis/Docker | 不写应用逻辑 |
| 后端 | FastAPI 路由、RayAPIClient | 不碰调度算法 |
| AI调度 | TaskAnalyzer、NodeScorer、Prompt | 不碰基础设施 |
| 测试 | 测试用例、质量验证 | 不写功能代码 |

**规则**：不属于你职责范围的代码，发现问题后记录到 `talks/` 而不是直接修改。
```

### 2. 统一 Agent 沟通协议

```markdown
## 8. Agent 沟通协议

### 消息类型
- `talks/to-[role]-[context].md` — 指派任务给某角色
- `talks/to-team-[date].md` — 团队进度同步

### 必须包含的内容
每个沟通文件必须有：
- **From**: 发送方角色
- **To**: 接收方角色
- **Date**: 日期
- **Type**: task / update / decision / notify
- **Content**: 具体内容
- **Status**: pending / accepted / done
```

### 3. 状态跟踪简化

建议把 `schedule.md` 改成一个简单的看板：

```markdown
## 当前迭代：M1 - Dataset Storage

### Todo
- [ ] 配置 Worker NAS 挂载
- [ ] 部署 JuiceFS 客户端

### Doing
- [x] Redis 部署（Head 节点完成）
- [ ] 验证 Redis 连通性

### Done
- [x] 确认 NAS 地址 //192.168.1.70/VtrixDataset
- [x] Docker 安装（Head 节点）
```

---

## 五、写完之后

### 自我检查清单

写完 `AGENTS.md` 后，问自己：

- [ ] **一个新 agent 读完，能不能直接开始干活？**（不用再问人）
- [ ] **当前状态是否准确？**（反映真实进度，不是一个月前的）
- [ ] **规则是否可检查？**（每条规则都能判断是/否）
- [ ] **是否在 200 行以内？**（太长需要精简）
- [ ] **参考文档索引是否完整？**（关键文档都能找到）

### 持续维护

`AGENTS.md` 不是写一次就完了。建议：
- 每个阶段完成后更新"当前状态"
- 发现 agent 犯错时，把教训写成规则
- 定期精简过时的内容

---

## 六、模板（可直接复制）

```markdown
# AGENTS.md — [项目名称]

## 0. 项目概览
[一句话：这是什么、解决什么问题]
技术栈：[语言] / [框架] / [关键依赖]

## 1. 当前状态
- **当前阶段**：[阶段名称]
- **上次进度**：[完成了什么]
- **下一步**：
  1. [具体任务]
  2. [具体任务]
- **已知问题**：
  - [问题描述]

## 2. 项目结构
[关键目录和文件的用途]

## 3. 开发协议
### 开始工作前
1. [必做事项]

### 代码开发
2. [规则]

### 文档更新
3. [规则]

## 4. 接口约定
[模块边界、API 契约]

## 5. 常用命令
[启动、测试、部署命令]

## 6. 参考文档
| 文档 | 用途 |
|------|------|
| [路径] | [用途] |
```

---

*最后更新：2026-03-27*
*由 AlgoStudio 项目 agent 编写指南*
