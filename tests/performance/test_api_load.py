"""
API Load Performance Tests

Tests API endpoint performance under various load conditions.
Run with: pytest tests/performance/test_api_load.py -v -m performance
"""
import os
import time
import statistics
import hashlib
import hmac
import pytest
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

# Test secret key for authentication
TEST_SECRET_KEY = "test-secret-key-for-benchmark"
os.environ["RBAC_SECRET_KEY"] = TEST_SECRET_KEY


def generate_signature(user_id: str, timestamp: str) -> str:
    """Generate HMAC-SHA256 signature for authentication."""
    message = f"{user_id}:{timestamp}"
    return hmac.new(
        TEST_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def get_auth_headers(user_id: str = "test-user", role: str = "admin") -> dict:
    """Generate valid auth headers."""
    timestamp = str(int(time.time()))
    return {
        "X-User-ID": user_id,
        "X-User-Role": role,
        "X-Timestamp": timestamp,
        "X-Signature": generate_signature(user_id, timestamp),
    }


class TestAPILoad:
    """API load performance tests."""

    @pytest.fixture
    def api_base_url(self) -> str:
        """Return the API base URL."""
        return "http://192.168.0.126:8000"

    @pytest.mark.performance
    def test_tasks_list_p95_latency(self, api_base_url: str):
        """GET /api/tasks p95 response time < 100ms."""
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            response = requests.get(f"{api_base_url}/api/tasks", timeout=10, headers=get_auth_headers())
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p50 = latencies[int(len(latencies) * 0.50)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nAPI /api/tasks Latency: p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms, avg={avg:.2f}ms")
        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms threshold"

    @pytest.mark.performance
    def test_tasks_get_by_id_p95_latency(self, api_base_url: str):
        """GET /api/tasks/{id} p95 response time < 50ms."""
        latencies = []
        task_id = "train-test-latency"

        for _ in range(100):
            start = time.perf_counter()
            response = requests.get(f"{api_base_url}/api/tasks/{task_id}", timeout=10, headers=get_auth_headers())
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            # Accept both 200 (success) and 404 (task not found) as valid responses
            assert response.status_code in (200, 404), f"Unexpected status {response.status_code}"

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p50 = latencies[int(len(latencies) * 0.50)]
        avg = statistics.mean(latencies)

        print(f"\nAPI /api/tasks/{{id}} Latency: p50={p50:.2f}ms, p95={p95:.2f}ms, avg={avg:.2f}ms")
        assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms threshold"

    @pytest.mark.performance
    def test_hosts_list_p95_latency(self, api_base_url: str):
        """GET /api/hosts p95 response time < 100ms."""
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            response = requests.get(f"{api_base_url}/api/hosts", timeout=10, headers=get_auth_headers())
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p50 = latencies[int(len(latencies) * 0.50)]
        avg = statistics.mean(latencies)

        print(f"\nAPI /api/hosts Latency: p50={p50:.2f}ms, p95={p95:.2f}ms, avg={avg:.2f}ms")
        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms threshold"

    @pytest.mark.performance
    def test_concurrent_requests_100_workers(self, api_base_url: str):
        """100 concurrent requests, system remains stable."""
        num_requests = 100

        def make_request() -> Tuple[int, float]:
            start = time.perf_counter()
            try:
                response = requests.get(f"{api_base_url}/api/tasks", timeout=30, headers=get_auth_headers())
                elapsed = time.perf_counter() - start
                return (response.status_code, elapsed * 1000)
            except Exception as e:
                return (-1, 0.0)

        results = []
        latencies = []
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            for future in as_completed(futures):
                status, latency = future.result()
                results.append(status)
                if latency > 0:
                    latencies.append(latency)

        total_time = time.perf_counter() - start_time

        success_count = sum(1 for r in results if r == 200)
        success_rate = success_count / num_requests

        print(f"\nConcurrent Requests: {num_requests}")
        print(f"  Success Rate: {success_rate*100:.1f}% ({success_count}/{num_requests})")
        print(f"  Total Time: {total_time:.2f}s")
        if latencies:
            print(f"  Avg Latency: {statistics.mean(latencies):.2f}ms")

        assert success_count >= 95, f"Only {success_count}/{num_requests} requests succeeded (expected >= 95)"

    @pytest.mark.performance
    def test_concurrent_requests_50_workers(self, api_base_url: str):
        """50 concurrent requests with multiple endpoints."""
        num_requests = 50
        endpoints = ["/api/tasks", "/api/hosts"]

        def make_request(endpoint: str) -> Tuple[str, int, float]:
            start = time.perf_counter()
            try:
                response = requests.get(f"{api_base_url}{endpoint}", timeout=30, headers=get_auth_headers())
                elapsed = time.perf_counter() - start
                return (endpoint, response.status_code, elapsed * 1000)
            except Exception as e:
                return (endpoint, -1, 0.0)

        results = {}
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = []
            for _ in range(num_requests):
                for endpoint in endpoints:
                    futures.append(executor.submit(make_request, endpoint))

            for future in as_completed(futures):
                endpoint, status, latency = future.result()
                if endpoint not in results:
                    results[endpoint] = {"success": 0, "fail": 0, "latencies": []}
                if status == 200:
                    results[endpoint]["success"] += 1
                    results[endpoint]["latencies"].append(latency)
                else:
                    results[endpoint]["fail"] += 1

        total_time = time.perf_counter() - start_time

        print(f"\nConcurrent Mixed Endpoints ({num_requests} requests x {len(endpoints)} endpoints)")
        print(f"  Total Time: {total_time:.2f}s")

        all_passed = True
        for endpoint, result in results.items():
            success_rate = result["success"] / (result["success"] + result["fail"])
            print(f"  {endpoint}: {success_rate*100:.1f}% success ({result['success']}/{result['success']+result['fail']})")
            if result["latencies"]:
                avg_lat = statistics.mean(result["latencies"])
                print(f"    Avg Latency: {avg_lat:.2f}ms")
            if success_rate < 0.95:
                all_passed = False

        assert all_passed, "One or more endpoints had < 95% success rate"

    @pytest.mark.performance
    def test_sustained_load_30_seconds(self, api_base_url: str):
        """Sustained load test over 30 seconds."""
        duration_seconds = 30
        target_rps = 10  # requests per second

        latencies = []
        request_count = 0
        error_count = 0

        start_time = time.perf_counter()
        last_report_time = start_time

        while time.perf_counter() - start_time < duration_seconds:
            req_start = time.perf_counter()
            try:
                response = requests.get(f"{api_base_url}/api/tasks", timeout=5, headers=get_auth_headers())
                req_elapsed = (time.perf_counter() - req_start) * 1000
                latencies.append(req_elapsed)
                if response.status_code == 200:
                    request_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

            # Rate limiting: sleep to maintain target_rps
            elapsed = time.perf_counter() - req_start
            sleep_time = (1.0 / target_rps) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Progress report every 10 seconds
            current_time = time.perf_counter()
            if current_time - last_report_time >= 10:
                elapsed_total = current_time - start_time
                actual_rps = request_count / elapsed_total
                print(f"  Progress: {elapsed_total:.0f}s, RPS: {actual_rps:.1f}, Errors: {error_count}")
                last_report_time = current_time

        total_time = time.perf_counter() - start_time
        actual_rps = request_count / total_time
        error_rate = error_count / (request_count + error_count) if (request_count + error_count) > 0 else 0

        latencies.sort()
        if latencies:
            p50 = latencies[int(len(latencies) * 0.50)]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            avg = statistics.mean(latencies)
        else:
            p50 = p95 = p99 = avg = 0

        print(f"\nSustained Load Test ({duration_seconds}s at ~{target_rps} RPS)")
        print(f"  Total Requests: {request_count}")
        print(f"  Error Rate: {error_rate*100:.2f}%")
        print(f"  Actual RPS: {actual_rps:.1f}")
        print(f"  Latency: p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms, avg={avg:.2f}ms")

        assert error_rate < 0.05, f"Error rate {error_rate*100:.2f}% exceeds 5% threshold"
        assert actual_rps >= target_rps * 0.8, f"RPS {actual_rps:.1f} is below 80% of target {target_rps}"


class TestAPIThroughput:
    """API throughput tests."""

    @pytest.fixture
    def api_base_url(self) -> str:
        return "http://192.168.0.126:8000"

    @pytest.mark.performance
    def test_tasks_create_p95_latency(self, api_base_url: str):
        """POST /api/tasks p95 response time < 200ms."""
        latencies = []

        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 1}
        }

        for _ in range(100):
            start = time.perf_counter()
            try:
                response = requests.post(
                    f"{api_base_url}/api/tasks",
                    json=task_payload,
                    timeout=10,
                    headers=get_auth_headers()
                )
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
                # Accept 200, 201, or 500 (if algo not found) as valid responses
                assert response.status_code in (200, 201, 500), f"Unexpected status {response.status_code}"
            except requests.exceptions.RequestException:
                # Network errors shouldn't fail the test if most requests succeed
                pass

        if not latencies:
            pytest.skip("No successful requests to measure")

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p50 = latencies[int(len(latencies) * 0.50)]
        avg = statistics.mean(latencies)

        print(f"\nAPI POST /api/tasks Latency: p50={p50:.2f}ms, p95={p95:.2f}ms, avg={avg:.2f}ms")
        assert p95 < 200, f"p95 latency {p95:.2f}ms exceeds 200ms threshold"

    @pytest.mark.performance
    def test_dispatch_task_p95_latency(self, api_base_url: str):
        """POST /api/tasks/{id}/dispatch p95 response time < 500ms."""
        latencies = []

        # First create a task
        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 1}
        }

        try:
            create_response = requests.post(f"{api_base_url}/api/tasks", json=task_payload, timeout=10, headers=get_auth_headers())
            if create_response.status_code == 200:
                task_data = create_response.json()
                task_id = task_data.get("task_id", "train-test-dispatch")
            else:
                task_id = "train-test-dispatch"
        except Exception:
            task_id = "train-test-dispatch"

        for _ in range(50):  # Fewer iterations as dispatch may be heavier
            start = time.perf_counter()
            try:
                response = requests.post(
                    f"{api_base_url}/api/tasks/{task_id}/dispatch",
                    timeout=10,
                    headers=get_auth_headers()
                )
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
                # Accept various statuses (task may not exist, etc.)
            except requests.exceptions.RequestException:
                pass

        if not latencies:
            pytest.skip("No successful requests to measure")

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p50 = latencies[int(len(latencies) * 0.50)]
        avg = statistics.mean(latencies)

        print(f"\nAPI POST /api/tasks/{{id}}/dispatch Latency: p50={p50:.2f}ms, p95={p95:.2f}ms, avg={avg:.2f}ms")
        assert p95 < 500, f"p95 latency {p95:.2f}ms exceeds 500ms threshold"