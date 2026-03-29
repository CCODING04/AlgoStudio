# from: @architect-beta
# to: @coordinator
# date: 2026-03-28
# type: review
# round: Phase 3.1 Round 3

## Phase 3.1 Round 3 评审: API/安全视角

### 评审对象

1. **RedisSnapshotStore** (`src/algo_studio/core/interfaces/redis_snapshot_store.py`)
2. **algorithms.py 测试覆盖** (`tests/unit/api/routes/test_algorithms.py`)

---

## 一、RedisSnapshotStore 评审

### 评分 (1-5)

| 维度 | 评分 | 说明 |
|------|------|------|
| 可行性 | 5 | 成熟技术，实现难度低 |
| 成本 | 4 | 参照现有 InMemory 实现，开发成本低 |
| 效益 | 4 | 解决部署回滚状态持久化问题 |
| 风险 | 3 | 存在索引-数据不一致风险 |
| 可维护性 | 4 | 代码清晰，错误处理完善 |

### 优点

1. **设计合理**: 遵循 SnapshotStoreInterface 接口契约，便于切换存储后端
2. **懒连接初始化**: `_get_redis()` 方法延迟创建连接，避免启动时依赖
3. **TTL 设计**: 7天自动过期，减少 Redis 存储压力
4. **Sorted Set 索引**: 使用时间戳作为分数，支持按时间排序
5. **原子操作**: 使用 pipeline 删除快照和索引

### 问题 (2个)

#### 问题 1: 索引-数据不一致 (中等风险)

**位置**: `redis_snapshot_store.py` 第 101-105 行

**描述**: 当快照因 TTL 过期自动删除时，`snapshot:index` Sorted Set 中的条目不会被清理。这会导致：

- `list_snapshots()` 返回已过期的 task_id
- 对已过期快照调用 `get_snapshot()` 返回 None
- 索引持续膨胀

**建议修复**:
```python
# 在 save_snapshot 时，如果 task_id 已存在于索引中，先删除旧快照
# 或者使用 Redis keyspace notifications 异步清理孤立索引
```

**影响**: 中等 - 列表可能返回无效引用，但不会导致数据丢失

#### 问题 2: 缺少 Redis 认证支持 (中等风险)

**位置**: `redis_snapshot_store.py` 第 74-78 行

**描述**: `_get_redis()` 方法不支持 Redis 密码认证。生产环境 Redis 通常需要认证。

**建议**: 添加可选密码参数：
```python
def __init__(self, redis_host="localhost", redis_port=6380,
             ttl_seconds=DEFAULT_TTL_SECONDS, redis_password: Optional[str] = None):
    ...
    self._redis_password = redis_password

async def _get_redis(self) -> redis.Redis:
    ...
    self._redis = redis.Redis(
        host=self._redis_host,
        port=self._redis_port,
        password=self._redis_password,  # 新增
        decode_responses=True,
    )
```

**影响**: 中等 - 当前环境可用，但无法部署到需要认证的 Redis

---

## 二、algorithms.py 测试覆盖评审

### 评分 (1-5)

| 维度 | 评分 | 说明 |
|------|------|------|
| 可行性 | 5 | 测试策略正确，覆盖全面 |
| 成本 | 4 | 14个测试用例，覆盖100%代码 |
| 效益 | 4 | 确保算法发现功能稳定 |
| 风险 | 2 | 路由未注册，无法实际使用 |
| 可维护性 | 5 | 测试结构清晰，易于扩展 |

### 优点

1. **覆盖率优秀**: 100% statement/branch 覆盖，超越60%目标
2. **边界测试完整**: 覆盖目录不存在、空目录、非目录项、无metadata.json、invalid JSON 等场景
3. **Mock 使用得当**: 使用 `unittest.mock.patch` 隔离依赖
4. **集成测试**: 使用真实 algorithms 目录验证端到端流程

### 问题 (2个)

#### 问题 1: 路由未注册 (高优先级)

**位置**: `src/algo_studio/api/main.py`

**描述**: algorithms router 未在 main.py 中注册。测试全部通过，但 API 端点实际无法访问。

**验证**:
```bash
$ curl http://localhost:8000/api/algorithms/
{"detail":"Not Found"}
```

**建议**: 在 `main.py` 添加：
```python
from algo_studio.api.routes import algorithms
app.include_router(algorithms.router)
```

**影响**: 高 - 功能存在但无法使用

#### 问题 2: metadata.json 缺少 schema 验证 (低优先级)

**位置**: `algorithms.py` 第 30-33 行

**描述**: `scan_algorithms()` 读取 metadata.json 但不验证必需字段。如果 metadata 缺少关键字段（如 name, version），返回的数据可能不完整。

**建议**: 添加可选的 schema 验证：
```python
required_fields = {"name", "version"}
if not required_fields.issubset(metadata.keys()):
    continue  # 或记录警告
```

**影响**: 低 - 现有算法 metadata 格式正确，风险可控

---

## 综合评分

| 模块 | 可行性 | 成本 | 效益 | 风险 | 可维护性 | 平均 |
|------|--------|------|------|------|----------|------|
| RedisSnapshotStore | 5 | 4 | 4 | 3 | 4 | 4.0 |
| algorithms.py 测试 | 5 | 4 | 4 | 2 | 5 | 4.0 |

---

## 修复优先级

1. **高**: algorithms router 未注册 - 阻塞功能使用
2. **中**: RedisSnapshotStore 索引孤立问题 - 数据一致性
3. **中**: RedisSnapshotStore 缺少密码认证 - 部署限制
4. **低**: metadata.json schema 验证 - 防御性增强

---

## 结论

**RedisSnapshotStore**: 实现质量良好，建议修复索引孤立问题后可用于生产。

**algorithms.py 测试**: 测试覆盖优秀，但需要先解决 router 注册问题才能使功能真正可用。

**通过评审，建议进入 Round 4**。