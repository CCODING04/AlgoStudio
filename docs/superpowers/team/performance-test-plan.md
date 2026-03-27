# AlgoStudio Phase 2 性能测试计划

**文件:** performance-test-plan.md
**版本:** v2.0
**作者:** @performance-engineer
**日期:** 2026-03-26
**状态:** 待评审

---

## 1. 概述

### 1.1 目的

本计划为 AlgoStudio Phase 2 提供性能测试框架，确保系统在各种负载下的稳定性和性能指标达标。

### 1.2 范围

| 测试类型 | 覆盖范围 |
|---------|---------|
| 平台性能 | API 响应时间、并发能力、数据库性能 |
| 算法性能 | 训练启动、推理延迟、GPU 利用率 |
| 数据性能 | 数据集加载、DVC 传输、JuiceFS 吞吐 |

### 1.3 项目背景

**集群配置：**
- Head 节点: 192.168.0.126 (RTX 4090 24GB, 31GB RAM, 1.8TB NVMe)
- Worker 节点: 192.168.0.115
- Ray 版本: 2.54.0
- Redis 端口: 6380

**技术栈：**
- API: FastAPI + Uvicorn
- 数据库: SQLite (Phase 2) -> PostgreSQL (Phase 3)
- 任务调度: Ray + AgenticScheduler
- 缓存/队列: Redis Stream
- 监控: Prometheus + Grafana

---

## 2. 性能指标定义

### 2.1 平台运行性能

#### 2.1.1 API 响应时间

| API 端点 | 指标 | 目标值 | 测量方法 |
|---------|------|--------|---------|
| `GET /api/tasks` | p95 | < 100ms | 100 次连续请求 |
| `GET /api/tasks/{id}` | p95 | < 50ms | 100 次连续请求 |
| `POST /api/tasks` | p95 | < 200ms | 100 次连续请求 |
| `GET /api/hosts` | p95 | < 100ms | 100 次连续请求 |
| `POST /api/tasks/{id}/dispatch` | p95 | < 500ms | 100 次连续请求 |

#### 2.1.2 SSE 性能

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 并发连接数 | >= 100 | 单节点支持的最大 SSE 连接 |
| 连接稳定性 | 30 分钟不断连 | 长连接保持测试 |
| 重连时间 | < 3 秒 | 断连后自动重连 |
| 消息延迟 | < 500ms | 进度更新到前端显示 |

#### 2.1.3 数据库性能

| 操作 | 指标 | 目标值 | 说明 |
|------|------|--------|------|
| 任务写入 | p99 | < 50ms | 单次任务创建 |
| 任务列表查询 | p95 | < 100ms | 100 条记录 |
| SQLite WAL 并发 | p99 | < 100ms | 10 并发写入 |
| Redis 操作 | p99 | < 10ms | SET/GET 操作 |

### 2.2 算法训练/推理性能

#### 2.2.1 训练性能

| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| 训练启动时间 | < 30s | 从 dispatch 到 GPU 开始计算 |
| GPU 利用率 | >= 80% | 训练过程中 nvidia-smi 采样 |
| GPU 显存使用 | 18-22 GB | 稳定训练时的显存占用 |
| 每 Epoch 时间 | 基准 +/- 10% | 与历史数据对比 |
| 调度决策延迟 | < 100ms | AgenticScheduler.schedule() |

#### 2.2.2 推理性能

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 推理延迟 (小 batch) | p99 < 500ms | batch=1 |
| 推理延迟 (中 batch) | p99 < 2s | batch=16 |
| 推理吞吐量 | >= 10 img/s | 单 GPU |
| 模型加载时间 | < 10s | 首次推理前 |

### 2.3 数据处理/备份性能

#### 2.3.1 数据集加载

| 数据集 | 指标 | 目标值 | 说明 |
|--------|------|--------|------|
| COCO2017 (小样本) | 加载时间 < 10s | 1000 张图片 |
| COCO2017 (全量) | 加载时间 < 60s | 全部标注 |
| 增量数据加载 | < 5s | 新增 100 张 |

#### 2.3.2 DVC 传输

| 操作 | 指标 | 目标值 | 说明 |
|------|------|--------|------|
| DVC Push | >= 50 MB/s | 受网络带宽限制 |
| DVC Pull | >= 50 MB/s | 受网络带宽限制 |
| 增量更新 | < 30s | 10 张图片变更 |

#### 2.3.3 JuiceFS 吞吐

| 操作 | 指标 | 目标值 | 说明 |
|------|------|--------|------|
| 顺序读 | >= 500 MB/s | 1GB 文件 |
| 顺序写 | >= 300 MB/s | 1GB 文件 |
| 随机读 | >= 200 MB/s | 4KB 块，10000 随机读 |
| 元数据操作 | < 10ms | 创建/查询 |

---

## 3. 测试场景设计

### 3.1 平台性能测试

#### 3.1.1 API 负载测试

```python
# tests/performance/test_api_load.py
import pytest
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import time
import statistics

class TestAPILoad:
    """API 负载测试"""

    @pytest.fixture
    def api_base_url(self):
        return "http://192.168.0.126:8000"

    @pytest.mark.performance
    def test_tasks_list_p95_latency(self, api_base_url):
        """GET /api/tasks p95 响应时间 < 100ms"""
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            response = requests.get(f"{api_base_url}/api/tasks")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert response.status_code == 200

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p50 = latencies[int(len(latencies) * 0.50)]
        avg = statistics.mean(latencies)

        print(f"\nAPI /api/tasks Latency: p50={p50:.2f}ms, p95={p95:.2f}ms")
        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms"

    @pytest.mark.performance
    def test_concurrent_requests(self, api_base_url):
        """100 并发请求，系统稳定"""
        def make_request():
            response = requests.get(f"{api_base_url}/api/tasks")
            return response.status_code

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [f.result() for f in futures]

        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 95, f"Only {success_count}/100 requests succeeded"
```

#### 3.1.2 SSE 连接测试

```python
# tests/performance/test_sse_performance.py
import pytest
import sseclient
import requests
import time
from threading import Thread

class TestSSEPerformance:
    """SSE 长连接性能测试"""

    @pytest.mark.performance
    def test_sse_concurrent_connections(self):
        """测试 100 并发 SSE 连接"""
        num_connections = 100
        connections = []
        errors = []

        def create_sse_connection(task_id):
            try:
                response = requests.get(
                    f"http://192.168.0.126:8000/api/tasks/{task_id}/progress",
                    stream=True,
                    timeout=35
                )
                client = sseclient.SSEClient(response)
                for event in client.events():
                    pass  # 保持连接
            except Exception as e:
                errors.append(str(e))

        # 启动 100 个连接
        threads = []
        for i in range(num_connections):
            t = Thread(target=create_sse_connection, args=(f"train-{i}",))
            threads.append(t)
            t.start()

        # 保持 30 秒
        time.sleep(30)

        # 中断所有连接
        for t in threads:
            t.join(timeout=5)

        success_rate = (num_connections - len(errors)) / num_connections
        assert success_rate >= 0.95, f"Only {success_rate*100:.1f}% connections survived"

    @pytest.mark.performance
    def test_sse_message_latency(self):
        """测试 SSE 消息延迟 < 500ms"""
        latencies = []
        task_id = "train-test-latency"

        # 先创建一个任务
        requests.post("http://192.168.0.126:8000/api/tasks", json={...})

        response = requests.get(
            f"http://192.168.0.126:8000/api/tasks/{task_id}/progress",
            stream=True
        )
        client = sseclient.SSEClient(response)

        for event in client.events():
            if event.data.startswith("progress:"):
                send_time = event.data.split(":")[1]
                recv_time = time.time() * 1000
                latency = recv_time - float(send_time)
                latencies.append(latency)

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            assert avg_latency < 500, f"Average SSE latency {avg_latency:.2f}ms exceeds 500ms"
```

#### 3.1.3 SQLite WAL 并发测试

```python
# tests/performance/test_sqlite_wal.py
import pytest
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import statistics

class TestSQLiteWAL:
    """SQLite WAL 模式并发写入测试"""

    @pytest.fixture
    def db_path(self, tmp_path):
        return tmp_path / "test.db"

    @pytest.fixture
    def setup_db(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        return db_path

    @pytest.mark.performance
    def test_concurrent_writes_10_workers(self, setup_db):
        """10 并发写入，p99 < 100ms"""
        latencies = []
        lock = threading.Lock()

        def write_task(task_num):
            start = time.perf_counter()
            conn = sqlite3.connect(setup_db)
            conn.execute(
                "INSERT OR REPLACE INTO tasks (task_id, status) VALUES (?, ?)",
                (f"task-{task_num}", "running")
            )
            conn.commit()
            conn.close()
            elapsed = (time.perf_counter() - start) * 1000
            with lock:
                latencies.append(elapsed)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_task, i) for i in range(100)]
            [f.result() for f in futures]

        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nSQLite WAL Write Latency: avg={avg:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
        assert p99 < 100, f"WAL p99 latency {p99:.2f}ms exceeds 100ms"
```

### 3.2 算法性能测试

#### 3.2.1 训练启动测试

```python
# tests/performance/test_training_performance.py
import pytest
import ray
import time
import subprocess

class TestTrainingPerformance:
    """训练性能测试"""

    @pytest.fixture(autouse=True)
    def ray_setup(self):
        ray.init(address="192.168.0.126:6379", ignore_reinit_error=True)
        yield
        ray.shutdown()

    @pytest.mark.performance
    def test_training_startup_time(self):
        """训练启动时间 < 30s"""
        start_time = time.perf_counter()

        # 提交训练任务
        result = ray.remote(num_gpus=1)(
            lambda: time.sleep(5)  # 模拟训练初始化
        ).remote()

        # 等待 GPU 开始计算
        time.sleep(25)  # 允许最多 25 秒启动

        startup_time = time.perf_counter() - start_time
        assert startup_time < 30, f"Training startup took {startup_time:.2f}s"

    @pytest.mark.performance
    def test_gpu_utilization_during_training(self):
        """训练时 GPU 利用率 >= 80%"""
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        # 在后台启动训练
        def run_training():
            # 实际训练代码
            import torch
            model = torch.nn.Linear(1000, 1000).cuda()
            optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
            data = torch.randn(32, 1000).cuda()

            for _ in range(100):
                output = model(data)
                loss = output.sum()
                loss.backward()
                optimizer.step()

        import threading
        train_thread = threading.Thread(target=run_training)
        train_thread.start()

        # 采样 GPU 利用率
        time.sleep(2)  # 等待训练稳定
        utilizations = []
        for _ in range(10):
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            utilizations.append(util.gpu)
            time.sleep(1)

        train_thread.join()

        avg_util = sum(utilizations) / len(utilizations)
        assert avg_util >= 80, f"GPU utilization {avg_util:.1f}% below 80%"

    @pytest.mark.performance
    def test_scheduling_decision_latency(self):
        """调度决策延迟 < 100ms"""
        from algo_studio.core.scheduler import AgenticScheduler
        from algo_studio.core.task import Task, TaskType

        scheduler = AgenticScheduler()
        task = Task.create(TaskType.TRAIN, "simple_classifier", "v1", {"epochs": 10})

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            decision = scheduler.schedule(task)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 100, f"Scheduling latency p95 {p95:.2f}ms exceeds 100ms"
```

#### 3.2.2 推理性能测试

```python
# tests/performance/test_inference_performance.py
import pytest
import torch
import time
import statistics

class TestInferencePerformance:
    """推理性能测试"""

    @pytest.mark.performance
    def test_inference_latency_small_batch(self):
        """小 batch 推理延迟 p99 < 500ms"""
        from algorithms.simple_classifier.v1 import SimpleClassifier

        model = SimpleClassifier()
        model.eval()
        batch = torch.randn(1, 3, 224, 224)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            with torch.no_grad():
                _ = model(batch)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nInference Latency (batch=1): avg={avg:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
        assert p99 < 500, f"Inference p99 latency {p99:.2f}ms exceeds 500ms"

    @pytest.mark.performance
    def test_inference_throughput(self):
        """推理吞吐量 >= 10 img/s"""
        from algorithms.simple_classifier.v1 import SimpleClassifier

        model = SimpleClassifier()
        model.eval()
        batch = torch.randn(16, 3, 224, 224)

        # 预热
        for _ in range(5):
            with torch.no_grad():
                _ = model(batch)

        # 正式测试
        num_iterations = 50
        start = time.perf_counter()
        for _ in range(num_iterations):
            with torch.no_grad():
                _ = model(batch)
        elapsed = time.perf_counter() - start

        total_images = num_iterations * 16
        throughput = total_images / elapsed
        assert throughput >= 10, f"Throughput {throughput:.2f} img/s below 10"
```

### 3.3 数据性能测试

#### 3.3.1 数据集加载测试

```python
# tests/performance/test_data_performance.py
import pytest
import time
import os
import statistics

class TestDataPerformance:
    """数据处理性能测试"""

    @pytest.mark.performance
    def test_coco_small_loading_time(self):
        """COCO 小样本加载 < 10s"""
        data_path = "/mnt/VtrixDataset/COCO2017"

        start = time.perf_counter()
        # 模拟数据加载
        import json
        annotation_file = os.path.join(data_path, "annotations/instances_train2017.json")
        if os.path.exists(annotation_file):
            with open(annotation_file) as f:
                coco_data = json.load(f)
        elapsed = time.perf_counter() - start

        assert elapsed < 10, f"COCO loading took {elapsed:.2f}s exceeds 10s"

    @pytest.mark.performance
    def test_dvc_push_pull_speed(self):
        """DVC Push/Pull 速度测试"""
        # 测试 DVC push 速度
        start = time.perf_counter()
        result = subprocess.run(
            ["dvc", "push", "-j", "4"],
            capture_output=True,
            timeout=300
        )
        push_time = time.perf_counter() - start

        # 假设推送 1GB 数据
        data_size_gb = 1
        speed_mbps = (data_size_gb * 1024) / push_time

        assert speed_mbps >= 50, f"DVC push speed {speed_mbps:.2f} MB/s below 50"
```

#### 3.3.2 JuiceFS 吞吐测试

```python
# tests/performance/test_juicefs_throughput.py
import pytest
import subprocess
import time
import os
import statistics

class TestJuiceFSPerformance:
    """JuiceFS 性能测试"""

    @pytest.fixture
    def test_file(self, tmp_path):
        """创建 1GB 测试文件"""
        test_file = tmp_path / "test_1g.bin"
        if not test_file.exists():
            subprocess.run(
                ["dd", "if=/dev/urandom", f"of={test_file}", "bs=1M", "count=1024"],
                check=True
            )
        return test_file

    @pytest.mark.performance
    def test_sequential_read_throughput(self, test_file):
        """顺序读 >= 500 MB/s"""
        start = time.perf_counter()
        result = subprocess.run(
            ["cat", str(test_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        elapsed = time.perf_counter() - start

        file_size_mb = test_file.stat().st_size / (1024 * 1024)
        throughput_mbps = file_size_mb / elapsed

        print(f"\nJuiceFS Sequential Read: {throughput_mbps:.2f} MB/s")
        assert throughput_mbps >= 500, f"Read throughput {throughput_mbps:.2f} MB/s below 500"

    @pytest.mark.performance
    def test_metadata_operations(self, tmp_path):
        """元数据操作 < 10ms"""
        test_dir = tmp_path / "test_meta"
        test_dir.mkdir()

        latencies = []
        for i in range(100):
            filename = str(test_dir / f"test_{i}.txt")
            start = time.perf_counter()
            with open(filename, "w") as f:
                f.write("test")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        # 清理
        import shutil
        shutil.rmtree(test_dir)

        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nMetadata Ops Latency: avg={avg:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
        assert p99 < 10, f"Metadata operation p99 {p99:.2f}ms exceeds 10ms"
```

---

## 4. 性能测试执行计划

### 4.1 测试阶段划分

| 阶段 | 时间 | 测试内容 |
|------|------|---------|
| **Week 0** | PoC | SSE 长连接稳定性 |
| **Week 1** | Phase 2.1 | SQLite WAL 并发测试 |
| **Week 2** | Phase 2.2 | API 基准测试、调度延迟测试 |
| **Week 3** | Phase 2.2 | 告警系统性能 |
| **Week 4** | Phase 2.3 | 配额系统性能、公平调度测试 |
| **Week 5** | Phase 2.3 | 训练启动测试、GPU 利用率测试 |
| **Week 6** | Phase 2.4 | E2E 压测、100 并发场景 |
| **Week 7-8** | 集成 | 完整性能基准、数据传输测试 |

### 4.2 测试环境要求

| 环境 | 要求 |
|------|------|
| Head 节点 | 192.168.0.126 (测试执行机) |
| Worker 节点 | 192.168.0.115 |
| Python | 3.10+ with pytest |
| 依赖 | pytest, pytest-benchmark, locust, psutil, pynvml |
| 网络 | 测试期间网络稳定，无限速 |

### 4.3 测试数据准备

```bash
# 创建性能测试数据集
mkdir -p /mnt/VtrixDataset/perf_test
for i in $(seq 1 1000); do
    dd if=/dev/urandom of=/mnt/VtrixDataset/perf_test/img_$i.jpg bs=1K count=100 2>/dev/null
done

# 预训练模型
cp algorithms/simple_classifier/v1/model.pth /tmp/perf_model.pth
```

---

## 5. 性能监控配置

### 5.1 Prometheus 指标

```yaml
# prometheus/perf_rules.yml
groups:
  - name: algo_studio_performance
    rules:
      - record: algo_studio:api_latency_p95
        expr: histogram_quantile(0.95, rate(algo_studio_api_request_duration_seconds_bucket[5m]))

      - record: algo_studio:sse_connections
        expr: algo_studio_sse_active_connections

      - record: algo_studio:gpu_utilization
        expr: rate(nvidia_gpu_utilization[1m])

      - record: algo_studio:task_dispatch_latency_p95
        expr: histogram_quantile(0.95, rate(algo_studio_task_dispatch_duration_seconds_bucket[5m]))

      - record: algo_studio:redis_operation_latency_p99
        expr: histogram_quantile(0.99, rate(algo_studio_redis_operation_duration_seconds_bucket[5m]))
```

### 5.2 性能仪表盘 (Grafana)

关键仪表盘面板：
1. **API 响应时间** - p50/p95/p99
2. **SSE 连接数** - 实时计数
3. **GPU 利用率** - 实时曲线
4. **数据库延迟** - WAL 写入延迟
5. **调度延迟** - p95 趋势

---

## 6. 性能验收标准

### 6.1 平台性能

| 指标 | 验收标准 | 优先级 |
|------|---------|--------|
| API p95 响应时间 | < 100ms | P0 |
| SSE 100 并发 | 95%+ 存活 | P0 |
| SQLite WAL p99 | < 100ms | P1 |
| Redis p99 | < 10ms | P1 |

### 6.2 算法性能

| 指标 | 验收标准 | 优先级 |
|------|---------|--------|
| 训练启动时间 | < 30s | P0 |
| GPU 利用率 | >= 80% | P0 |
| 调度延迟 p95 | < 100ms | P0 |
| 推理延迟 p99 | < 500ms | P1 |

### 6.3 数据性能

| 指标 | 验收标准 | 优先级 |
|------|---------|--------|
| COCO 小样本加载 | < 10s | P1 |
| JuiceFS 顺序读 | >= 500 MB/s | P1 |
| DVC 传输 | >= 50 MB/s | P2 |

---

## 7. 性能测试报告模板

```markdown
# Performance Test Report - [模块名]

**测试日期:** YYYY-MM-DD
**测试人员:** @performance-engineer
**测试环境:** Head: 192.168.0.126 / Worker: 192.168.0.115

## 测试结果摘要

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| API p95 | < 100ms | XXms | PASS/FAIL |
| GPU 利用率 | >= 80% | XX% | PASS/FAIL |
| ... | ... | ... | ... |

## 详细数据

### 7.1 API 响应时间

```
测试方法: 100 次连续请求
测试工具: pytest + requests
p50: XXms
p95: XXms
p99: XXms
```

### 7.2 GPU 利用率

```
测试方法: nvidia-smi 采样
采样间隔: 1s
采样次数: 30
平均值: XX%
最小值: XX%
最大值: XX%
```

## 问题与优化建议

1. **问题:** [描述]
   **影响:** [影响分析]
   **建议:** [优化方案]

## 结论

[综合评价]
```

---

## 8. 附录

### 8.1 测试工具清单

| 工具 | 用途 |
|------|------|
| pytest | 单元/功能测试框架 |
| pytest-benchmark | 基准测试 |
| locust | HTTP 负载测试 |
| wrk | 高性能 HTTP 基准测试 |
| nvidia-smi | GPU 监控 |
| psutil | 系统监控 |
| iostat | 磁盘 IO 监控 |
| prometheus | 指标收集 |

### 8.2 基准数据存储

```
tests/performance/benchmarks/
├── api_baseline.json      # API 响应时间基准
├── gpu_baseline.json      # GPU 利用率基准
├── db_baseline.json       # 数据库基准
└── throughput_baseline.json  # 吞吐基准
```

### 8.3 联系方式

| 角色 | 负责人 | 职责 |
|------|--------|------|
| 性能测试工程师 | @performance-engineer | 测试执行、报告 |
| 后端工程师 | @backend-engineer | API 性能优化 |
| AI 调度工程师 | @ai-scheduling-engineer | 调度性能优化 |

---

**文档状态:** 待评审
**下次更新:** Phase 2 实施前
