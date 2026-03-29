# from: @coordinator
# to: @backend-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 1

## 任务: 存储抽象层 Phase 1 准备

### 背景
评审团决策：Repository Pattern + Abstract Base Class
Phase 1: 创建 SnapshotStoreInterface + InMemorySnapshotStore

### 具体任务

1. **研究现有代码结构**
   - 查看 `src/algo_studio/core/deploy/rollback.py` 中的 DeploymentSnapshotStore
   - 查看 `src/algo_studio/core/quota_manager.py` 中的 QuotaStoreInterface 作为参考
   - 确认 async/await 使用模式

2. **设计 SnapshotStoreInterface**
   ```python
   from abc import ABC, abstractmethod
   from typing import Optional, List
   from datetime import datetime

   class SnapshotStoreInterface(ABC):
       @abstractmethod
       async def save_snapshot(self, task_id: str, snapshot_data: dict) -> bool:
           pass

       @abstractmethod
       async def get_snapshot(self, task_id: str) -> Optional[dict]:
           pass

       @abstractmethod
       async def list_snapshots(self, limit: int = 10) -> List[dict]:
           pass

       @abstractmethod
       async def delete_snapshot(self, task_id: str) -> bool:
           pass
   ```

3. **创建初步接口定义文件**
   - 放在 `src/algo_studio/core/interfaces/snapshot_store.py`
   - 包含 SnapshotStoreInterface ABC

### 输出
完成后在 `talks/backend-to-coordinator-round1-2026-03-28.md` 汇报：
- 现有 DeploymentSnapshotStore 分析
- 接口设计草案
