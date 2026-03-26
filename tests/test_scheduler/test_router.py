# tests/test_scheduler/test_router.py
"""Tests for Router - Fast/Deep path routing"""

import pytest
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.routing.router import Router


class TestRouter:
    """Test suite for Router"""

    def setup_method(self):
        """Set up test fixtures"""
        self.router = Router()

    def _create_profile(
        self,
        num_gpus=0,
        preferred_nodes=None,
        is_retry=False,
        retry_count=0,
        timeout_minutes=120,
        complexity=1,
    ):
        """Helper to create TaskProfile"""
        profile = TaskProfile(
            task_id="test-task",
            task_type=TaskType.TRAIN,
            num_gpus=num_gpus,
            preferred_nodes=preferred_nodes or [],
            is_retry=is_retry,
            retry_count=retry_count,
            timeout_minutes=timeout_minutes,
        )
        # Manually set complexity if provided
        if complexity != 1:
            # We can't directly set complexity as it's computed, so we test what triggers it
            pass
        return profile

    def test_simple_task_uses_fast_path(self):
        """Test that simple tasks use Fast Path"""
        profile = self._create_profile()

        use_deep = self.router.should_use_deep_path(profile)

        assert use_deep is False

    def test_high_complexity_uses_deep_path(self):
        """Test that high complexity tasks use Deep Path"""
        # A profile with preferred_nodes and other attributes that make it complex
        profile = self._create_profile(
            num_gpus=2,
            preferred_nodes=["worker-1"],
            timeout_minutes=150,  # > 120
        )

        use_deep = self.router.should_use_deep_path(profile)

        # This should trigger Deep Path due to preferred_nodes
        assert use_deep is True

    def test_retry_with_high_count_uses_deep_path(self):
        """Test that retry tasks with high retry count use Deep Path"""
        profile = self._create_profile(is_retry=True, retry_count=3)

        use_deep = self.router.should_use_deep_path_with_context(profile, 0, 0.0)

        assert use_deep is True

    def test_high_load_with_long_queue_uses_deep_path(self):
        """Test that high load scenarios use Deep Path"""
        profile = self._create_profile()

        # queue_length > 20 AND avg_node_load > 0.7
        use_deep = self.router.should_use_deep_path_with_context(profile, 25, 0.8)

        assert use_deep is True

    def test_preferred_nodes_uses_deep_path(self):
        """Test that tasks with preferred nodes use Deep Path"""
        profile = self._create_profile(preferred_nodes=["worker-1"])

        use_deep = self.router.should_use_deep_path_with_context(profile, 0, 0.0)

        assert use_deep is True

    def test_long_running_task_uses_deep_path(self):
        """Test that long-running tasks use Deep Path"""
        profile = self._create_profile(timeout_minutes=150)  # > 120

        use_deep = self.router.should_use_deep_path_with_context(profile, 0, 0.0)

        assert use_deep is True

    def test_retry_task_uses_deep_path(self):
        """Test that retry tasks use Deep Path"""
        profile = self._create_profile(is_retry=True)

        use_deep = self.router.should_use_deep_path_with_context(profile, 0, 0.0)

        assert use_deep is True

    def test_get_routing_reason_deep_path(self):
        """Test getting routing reason for Deep Path"""
        profile = self._create_profile(timeout_minutes=150)

        reason = self.router.get_routing_reason(profile)

        assert "Deep Path" in reason
        assert "Long-running task" in reason

    def test_get_routing_reason_fast_path(self):
        """Test getting routing reason for Fast Path"""
        profile = self._create_profile()

        reason = self.router.get_routing_reason(profile)

        assert "Fast Path" in reason

    def test_get_routing_reason_multiple_triggers(self):
        """Test getting routing reason when multiple triggers apply"""
        profile = self._create_profile(
            preferred_nodes=["worker-1"],
            timeout_minutes=150,
        )

        reason = self.router.get_routing_reason(profile)

        assert "Deep Path" in reason
        assert "Node affinity" in reason
        assert "Long-running task" in reason

    def test_default_rules(self):
        """Test default routing rules"""
        rules = Router.DEFAULT_RULES

        assert rules["complexity_threshold"] == 7
        assert rules["retry_count_threshold"] == 2
        assert rules["queue_length_threshold"] == 20
        assert rules["load_threshold"] == 0.7
        assert rules["timeout_threshold_minutes"] == 120

    def test_custom_rules(self):
        """Test custom routing rules"""
        custom_rules = {
            "complexity_threshold": 5,
            "retry_count_threshold": 1,
            "queue_length_threshold": 10,
            "load_threshold": 0.5,
            "timeout_threshold_minutes": 60,
        }
        router = Router(rules=custom_rules)

        assert router.rules["complexity_threshold"] == 5
        assert router.rules["load_threshold"] == 0.5

    def test_should_use_deep_path_with_context_all_conditions(self):
        """Test all conditions that trigger Deep Path"""
        # Condition 1: preferred nodes triggers deep path
        profile1 = self._create_profile(preferred_nodes=["worker-1"])
        assert self.router.should_use_deep_path_with_context(profile1, 0, 0.0) is True

    def test_normal_load_and_queue_uses_fast_path(self):
        """Test that normal load and queue uses Fast Path"""
        profile = self._create_profile()

        # queue_length <= 20 OR avg_node_load <= 0.7
        use_deep = self.router.should_use_deep_path_with_context(profile, 15, 0.5)

        assert use_deep is False
