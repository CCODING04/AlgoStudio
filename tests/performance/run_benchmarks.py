#!/usr/bin/env python3
"""
AlgoStudio Performance Benchmark Runner

Usage:
    python run_benchmarks.py --all
    python run_benchmarks.py --api
    python run_benchmarks.py --gpu
    python run_benchmarks.py --database
    python run_benchmarks.py --throughput
    python run_benchmarks.py --report
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import requests
import statistics


class BenchmarkRunner:
    """Run performance benchmarks and compare against baselines."""

    def __init__(self, base_url="http://192.168.0.126:8000", benchmark_dir=None):
        self.base_url = base_url
        self.benchmark_dir = benchmark_dir or os.path.join(
            os.path.dirname(__file__), "benchmarks"
        )
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "api": {},
            "gpu": {},
            "database": {},
            "throughput": {}
        }

    def load_baseline(self, category):
        """Load baseline for a category."""
        baseline_file = os.path.join(self.benchmark_dir, f"{category}_baseline.json")
        if os.path.exists(baseline_file):
            with open(baseline_file) as f:
                return json.load(f)
        return None

    def run_api_benchmarks(self):
        """Run API performance benchmarks."""
        print("\n=== API Performance Benchmarks ===")
        baseline = self.load_baseline("api")
        if not baseline:
            print("No API baseline found, skipping...")
            return

        endpoints = [
            ("GET", "/api/tasks", "GET /api/tasks"),
            ("GET", "/api/tasks/train-001", "GET /api/tasks/{id}"),
            ("GET", "/api/hosts", "GET /api/hosts"),
        ]

        for method, endpoint, name in endpoints:
            print(f"\nTesting {name}...")
            latencies = []
            for i in range(100):
                start = time.perf_counter()
                try:
                    if method == "GET":
                        response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                    elif method == "POST":
                        response = requests.post(f"{self.base_url}{endpoint}", json={}, timeout=10)

                    elapsed = (time.perf_counter() - start) * 1000
                    latencies.append(elapsed)
                    if response.status_code != 200:
                        print(f"  Warning: Status {response.status_code}")
                except Exception as e:
                    print(f"  Error: {e}")

                if (i + 1) % 20 == 0:
                    print(f"  Progress: {i + 1}/100")

            if latencies:
                latencies.sort()
                p50 = latencies[int(len(latencies) * 0.50)]
                p95 = latencies[int(len(latencies) * 0.95)]
                p99 = latencies[int(len(latencies) * 0.99)]

                target = baseline["targets"].get(name, {})
                p95_target = target.get("p95_ms", float("inf"))

                status = "PASS" if p95 <= p95_target else "FAIL"

                self.results["api"][name] = {
                    "p50_ms": round(p50, 2),
                    "p95_ms": round(p95, 2),
                    "p99_ms": round(p99, 2),
                    "target_p95_ms": p95_target,
                    "status": status
                }

                print(f"  Results: p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
                print(f"  Target p95: {p95_target}ms -> {status}")

    def run_sse_benchmark(self):
        """Run SSE concurrent connection benchmark."""
        print("\n=== SSE Performance Benchmark ===")
        baseline = self.load_baseline("api")
        if not baseline:
            return

        target = baseline.get("sse_targets", {})
        max_connections = target.get("max_concurrent_connections", 100)

        print(f"Testing SSE with {max_connections} concurrent connections...")
        print("Note: Full SSE test requires running pytest with test_sse_performance.py")

        self.results["api"]["sse_connections"] = {
            "max_concurrent": max_connections,
            "status": "SKIP (manual test required)"
        }

    def run_database_benchmarks(self):
        """Run database performance benchmarks."""
        print("\n=== Database Performance Benchmarks ===")
        baseline = self.load_baseline("db")
        if not baseline:
            print("No database baseline found, skipping...")
            return

        import sqlite3
        import tempfile
        import threading
        from concurrent.futures import ThreadPoolExecutor

        # Create temp database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Setup WAL mode database
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()

            # Concurrent write test
            print("\nTesting SQLite WAL concurrent writes (10 workers, 100 ops)...")
            latencies = []
            lock = threading.Lock()

            def write_task(task_num):
                start = time.perf_counter()
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "INSERT OR REPLACE INTO tasks (task_id, status) VALUES (?, ?)",
                    (f"perf-task-{task_num}", "running")
                )
                conn.commit()
                conn.close()
                elapsed = (time.perf_counter() - start) * 1000
                with lock:
                    latencies.append(elapsed)

            start_time = time.perf_counter()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(write_task, i) for i in range(100)]
                [f.result() for f in futures]
            total_time = time.perf_counter() - start_time

            latencies.sort()
            p99 = latencies[int(len(latencies) * 0.99)]
            target_p99 = baseline["targets"]["sqlite_wal"]["concurrent_10_write_p99_ms"]

            status = "PASS" if p99 <= target_p99 else "FAIL"

            self.results["database"]["sqlite_wal_concurrent"] = {
                "p99_ms": round(p99, 2),
                "total_time_s": round(total_time, 2),
                "target_p99_ms": target_p99,
                "status": status
            }

            print(f"  Results: p99={p99:.2f}ms, total={total_time:.2f}s")
            print(f"  Target p99: {target_p99}ms -> {status}")

        finally:
            os.unlink(db_path)

    def run_gpu_benchmarks(self):
        """Run GPU performance benchmarks."""
        print("\n=== GPU Performance Benchmarks ===")
        baseline = self.load_baseline("gpu")
        if not baseline:
            print("No GPU baseline found, skipping...")
            return

        print("Note: Full GPU benchmark requires pytest with test_training_performance.py")
        print("Checking GPU availability...")

        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()

            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                print(f"  GPU: {name}")
                print(f"  Memory Total: {memory_info.total / 1024**3:.2f} GB")
                print(f"  Memory Free: {memory_info.free / 1024**3:.2f} GB")
                print(f"  Memory Used: {memory_info.used / 1024**3:.2f} GB")

                self.results["gpu"]["gpu_info"] = {
                    "name": name,
                    "memory_total_gb": round(memory_info.total / 1024**3, 2),
                    "memory_used_gb": round(memory_info.used / 1024**3, 2),
                    "status": "AVAILABLE"
                }
            else:
                print("  No GPU found")
                self.results["gpu"]["gpu_info"] = {"status": "NOT_AVAILABLE"}

            pynvml.nvmlShutdown()

        except Exception as e:
            print(f"  Error accessing GPU: {e}")
            self.results["gpu"]["gpu_info"] = {"status": f"ERROR: {e}"}

    def run_throughput_benchmarks(self):
        """Run data throughput benchmarks."""
        print("\n=== Data Throughput Benchmarks ===")
        baseline = self.load_baseline("throughput")
        if not baseline:
            print("No throughput baseline found, skipping...")
            return

        print("Note: Full throughput tests require JuiceFS/DVC setup")
        print("Testing basic file system access...")

        # Basic filesystem test
        test_dir = "/mnt/VtrixDataset"
        if os.path.exists(test_dir):
            print(f"  {test_dir} is accessible")
            self.results["throughput"]["juicefs_access"] = {"status": "ACCESSIBLE"}
        else:
            print(f"  {test_dir} not found")
            self.results["throughput"]["juicefs_access"] = {"status": "NOT_ACCESSIBLE"}

    def generate_report(self, output_file=None):
        """Generate benchmark report."""
        report = {
            "title": "AlgoStudio Performance Benchmark Report",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0
            },
            "results": self.results
        }

        # Count results
        for category, tests in self.results.items():
            for test_name, result in tests.items():
                report["summary"]["total_tests"] += 1
                status = result.get("status", "UNKNOWN")
                if status == "PASS":
                    report["summary"]["passed"] += 1
                elif status == "FAIL":
                    report["summary"]["failed"] += 1
                else:
                    report["summary"]["skipped"] += 1

        report_json = json.dumps(report, indent=2)

        if output_file:
            with open(output_file, "w") as f:
                f.write(report_json)
            print(f"\nReport saved to: {output_file}")

        # Print summary
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"  Passed: {report['summary']['passed']}")
        print(f"  Failed: {report['summary']['failed']}")
        print(f"  Skipped: {report['summary']['skipped']}")
        print("=" * 60)

        return report


def main():
    parser = argparse.ArgumentParser(description="Run AlgoStudio performance benchmarks")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument("--api", action="store_true", help="Run API benchmarks")
    parser.add_argument("--database", action="store_true", help="Run database benchmarks")
    parser.add_argument("--gpu", action="store_true", help="Run GPU benchmarks")
    parser.add_argument("--throughput", action="store_true", help="Run throughput benchmarks")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--output", default="perf_report.json", help="Output file for report")
    parser.add_argument("--base-url", default="http://192.168.0.126:8000", help="API base URL")

    args = parser.parse_args()

    runner = BenchmarkRunner(base_url=args.base_url)

    if args.all or args.api:
        runner.run_api_benchmarks()
        runner.run_sse_benchmark()

    if args.all or args.database:
        runner.run_database_benchmarks()

    if args.all or args.gpu:
        runner.run_gpu_benchmarks()

    if args.all or args.throughput:
        runner.run_throughput_benchmarks()

    if args.report or args.all:
        runner.generate_report(args.output)

    if not any([args.all, args.api, args.database, args.gpu, args.throughput, args.report]):
        parser.print_help()


if __name__ == "__main__":
    main()
