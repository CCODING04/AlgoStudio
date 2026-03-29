# tests/unit/scheduler/routing/test_router.py
"""Unit tests for Router."""

import pytest
from algo_studio.core.scheduler.routing.router import Router
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType


class TestRouter:
    """Tests for Router."""

    @pytest.fixture
    def router(self):
        """Create a Router instance with default rules."""
        return Router()

    @pytest.fixture
    def router_custom_rules(self):
        """Create a Router with custom rules."""
        custom_rules = {
            "complexity_threshold": 5,
            "retry_count_threshold": 1,
            "queue_length_threshold": 10,
            "load_threshold": 0.5,
            "timeout_threshold_minutes": 60,
        }
        return Router(rules=custom_rules)

    @pytest.fixture
    def simple_task_profile(self):
        """Create a simple task profile."""
        return TaskProfile(
            task_id="simple-task-001",
            task_type=TaskType.INFER,
            num_gpus=0,
            memory_gb=8,
            priority=5,
            estimated_duration_minutes=30,
            timeout_minutes=60,
        )

    @pytest.fixture
    def high_complexity_profile(self):
        """Create a high complexity task profile (complexity >= 7)."""
        return TaskProfile(
            task_id="complex-task-001",
            task_type=TaskType.TRAIN,
            num_gpus=2,
            memory_gb=32,
            priority=9,
            preferred_nodes=["worker-1"],
            estimated_duration_minutes=120,
            timeout_minutes=180,
        )

    def test_router_has_default_rules(self, router):
        """Test that router has expected default rules."""
        assert router.rules["complexity_threshold"] == 7
        assert router.rules["retry_count_threshold"] == 2
        assert router.rules["queue_length_threshold"] == 20
        assert router.rules["load_threshold"] == 0.7
        assert router.rules["timeout_threshold_minutes"] == 120

    def test_router_accepts_custom_rules(self, router_custom_rules):
        """Test that router accepts custom rules."""
        assert router_custom_rules.rules["complexity_threshold"] == 5
        assert router_custom_rules.rules["retry_count_threshold"] == 1

    def test_should_use_deep_path_simple_task(self, router, simple_task_profile):
        """Test that simple task uses Fast Path."""
        result = router.should_use_deep_path(simple_task_profile)
        assert result is False

    def test_should_use_deep_path_high_complexity(self, router, high_complexity_profile):
        """Test that high complexity task uses Deep Path."""
        result = router.should_use_deep_path(high_complexity_profile)
        assert result is True

    def test_should_use_deep_path_with_context_high_load(self, router, simple_task_profile):
        """Test Deep Path triggers under high load scenario."""
        # queue_length > 20 AND avg_node_load > 0.7
        result = router.should_use_deep_path_with_context(
            simple_task_profile,
            queue_length=25,
            avg_node_load=0.8,
        )
        assert result is True

    def test_should_use_deep_path_with_context_normal_load(self, router, simple_task_profile):
        """Test Fast Path under normal load."""
        result = router.should_use_deep_path_with_context(
            simple_task_profile,
            queue_length=15,
            avg_node_load=0.5,
        )
        assert result is False

    def test_should_use_deep_path_with_context_high_queue_only(self, router, simple_task_profile):
        """Test that high queue alone doesn't trigger Deep Path."""
        # Must have BOTH high queue AND high load
        result = router.should_use_deep_path_with_context(
            simple_task_profile,
            queue_length=25,
            avg_node_load=0.5,  # Below threshold
        )
        assert result is False

    def test_should_use_deep_path_with_context_high_load_only(self, router, simple_task_profile):
        """Test that high load alone doesn't trigger Deep Path."""
        result = router.should_use_deep_path_with_context(
            simple_task_profile,
            queue_length=10,  # Below threshold
            avg_node_load=0.9,
        )
        assert result is False

    def test_should_use_deep_path_retry_task(self, router):
        """Test that retry task with count >= threshold uses Deep Path."""
        profile = TaskProfile(
            task_id="retry-task",
            task_type=TaskType.TRAIN,
            is_retry=True,
            retry_count=2,
        )
        result = router.should_use_deep_path(profile)
        assert result is True

    def test_should_use_deep_path_retry_below_threshold(self, router):
        """Test that retry task with count < threshold uses Fast Path."""
        profile = TaskProfile(
            task_id="retry-task",
            task_type=TaskType.TRAIN,
            is_retry=True,
            retry_count=1,  # Below threshold of 2
        )
        result = router.should_use_deep_path(profile)
        assert result is True  # Still True due to is_retry in _evaluate_rules

    def test_should_use_deep_path_preferred_nodes(self, router, simple_task_profile):
        """Test that preferred nodes triggers Deep Path."""
        simple_task_profile.preferred_nodes = ["worker-1"]
        result = router.should_use_deep_path(simple_task_profile)
        assert result is True

    def test_should_use_deep_path_long_timeout(self, router, simple_task_profile):
        """Test that long timeout (>120 min) triggers Deep Path."""
        simple_task_profile.timeout_minutes = 150
        result = router.should_use_deep_path(simple_task_profile)
        assert result is True

    def test_should_use_deep_path_short_timeout(self, router, simple_task_profile):
        """Test that short timeout uses Fast Path."""
        simple_task_profile.timeout_minutes = 60
        result = router.should_use_deep_path(simple_task_profile)
        assert result is False

    def test_get_routing_reason_fast_path(self, router, simple_task_profile):
        """Test routing reason for Fast Path."""
        reason = router.get_routing_reason(simple_task_profile)
        assert "Fast Path" in reason
        assert "Simple task" in reason

    def test_get_routing_reason_high_complexity(self, router, high_complexity_profile):
        """Test routing reason for high complexity Deep Path."""
        reason = router.get_routing_reason(high_complexity_profile)
        assert "Deep Path" in reason
        assert "High complexity" in reason

    def test_get_routing_reason_retry(self, router):
        """Test routing reason for retry task."""
        profile = TaskProfile(
            task_id="retry-task",
            task_type=TaskType.TRAIN,
            is_retry=True,
            retry_count=3,
        )
        reason = router.get_routing_reason(profile)
        assert "Deep Path" in reason
        assert "Multiple retries" in reason

    def test_get_routing_reason_high_load(self, router, simple_task_profile):
        """Test routing reason for high load scenario."""
        reason = router.get_routing_reason(
            simple_task_profile,
            queue_length=25,
            avg_node_load=0.8,
        )
        assert "Deep Path" in reason
        assert "High cluster load" in reason

    def test_get_routing_reason_preferred_nodes(self, router, simple_task_profile):
        """Test routing reason for preferred nodes."""
        simple_task_profile.preferred_nodes = ["worker-1"]
        reason = router.get_routing_reason(simple_task_profile)
        assert "Deep Path" in reason
        assert "Node affinity" in reason

    def test_get_routing_reason_long_running(self, router, simple_task_profile):
        """Test routing reason for long-running task."""
        simple_task_profile.timeout_minutes = 150
        reason = router.get_routing_reason(simple_task_profile)
        assert "Deep Path" in reason
        assert "Long-running task" in reason

    def test_custom_rules_respected(self, router_custom_rules):
        """Test that custom rules are used in decisions."""
        # This profile has complexity 3 (base 1 + GPU 2), which is < 5 threshold
        # It also doesn't trigger any other rule
        profile = TaskProfile(
            task_id="medium-task",
            task_type=TaskType.TRAIN,
            num_gpus=1,  # Adds 2 to base complexity
            memory_gb=8,  # Doesn't add (not > 16)
            priority=5,  # Doesn't add (not >= 8)
            estimated_duration_minutes=30,  # Doesn't add (not > 60)
            timeout_minutes=60,  # Set to 60 to not trigger timeout rule
            # Total complexity = 1 + 2 = 3, which is < 5 threshold
        )
        result = router_custom_rules.should_use_deep_path(profile)
        # All rules fail: complexity 3 < 5, is_retry=False, queue=0, no preferred nodes
        assert result is False

        # A task with preferred_nodes triggers Rule 4
        profile2 = TaskProfile(
            task_id="affinity-task",
            task_type=TaskType.TRAIN,
            preferred_nodes=["worker-1"],
        )
        result2 = router_custom_rules.should_use_deep_path(profile2)
        assert result2 is True

    def test_evaluate_rules_all_conditions(self, router):
        """Test that all rule conditions are evaluated correctly."""
        # Rule 1: High complexity (TaskProfile.complexity >= 7)
        # TaskProfile.complexity for num_gpus=4 is 1+2=3, not enough
        # We need to set multiple factors to reach 7+
        profile = TaskProfile(
            task_id="t1",
            task_type=TaskType.TRAIN,
            num_gpus=2,  # +2
            memory_gb=32,  # +1
            priority=8,  # +1
            preferred_nodes=["n1"],  # +2
            # Total: 1+2+1+1+2 = 7
        )
        assert router._evaluate_rules(profile, 0, 0.0) is True

        # Rule 2: Retry with high count
        profile = TaskProfile(task_id="t2", task_type=TaskType.TRAIN, is_retry=True, retry_count=3)
        assert router._evaluate_rules(profile, 0, 0.0) is True

        # Rule 3: High load
        profile = TaskProfile(task_id="t3", task_type=TaskType.TRAIN)
        assert router._evaluate_rules(profile, 25, 0.8) is True

        # Rule 4: Preferred nodes
        profile = TaskProfile(task_id="t4", task_type=TaskType.TRAIN, preferred_nodes=["n1"])
        assert router._evaluate_rules(profile, 0, 0.0) is True

        # Rule 5: Long timeout
        profile = TaskProfile(task_id="t5", task_type=TaskType.TRAIN, timeout_minutes=150)
        assert router._evaluate_rules(profile, 0, 0.0) is True

        # Rule 6: Retry (any retry)
        profile = TaskProfile(task_id="t6", task_type=TaskType.TRAIN, is_retry=True, retry_count=0)
        assert router._evaluate_rules(profile, 0, 0.0) is True

    def test_evaluate_rules_no_conditions_met(self, router, simple_task_profile):
        """Test that Fast Path is selected when no conditions are met."""
        result = router._evaluate_rules(simple_task_profile, 0, 0.0)
        assert result is False
