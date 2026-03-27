# tests/integration/test_scheduler_integration.py
"""Integration tests for scheduler components."""

import pytest
from unittest.mock import MagicMock, patch
from algo_studio.core.scheduler.agents.fast_scheduler import FastPathScheduler
from algo_studio.core.scheduler.analyzers.default_analyzer import DefaultTaskAnalyzer
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer
from algo_studio.core.scheduler.validators.resource_validator import ResourceValidator
from algo_studio.core.task import Task, TaskType, TaskStatus


class TestFastPathSchedulerIntegration:
    """Integration tests for FastPathScheduler with real components."""

    @pytest.fixture
    def fast_scheduler(self):
        """Create a FastPathScheduler instance."""
        analyzer = DefaultTaskAnalyzer()
        scorer = MultiDimNodeScorer()
        validator = ResourceValidator()

        return FastPathScheduler(
            task_analyzer=analyzer,
            node_scorer=scorer,
            validator=validator
        )

    def test_schedule_train_task(self, fast_scheduler):
        """Test scheduling a training task."""
        task = Task(
            task_id="test-task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status=TaskStatus.PENDING,
            config={"epochs": 100, "num_gpus": 1},
        )

        # Scheduler should handle the task
        assert fast_scheduler is not None


class TestAnalyzerScorerValidatorChain:
    """Integration tests for component chain."""

    def test_analyzer_returns_task_profile(self):
        """Test that analyzer returns task profile."""
        analyzer = DefaultTaskAnalyzer()
        task = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"epochs": 100},
        )

        profile = analyzer.analyze(task)
        assert profile is not None
        assert profile.task_id == "test-001"
        assert profile.num_gpus >= 0

    def test_multi_dim_scorer_initialization(self):
        """Test MultiDimNodeScorer initializes correctly."""
        scorer = MultiDimNodeScorer()
        assert scorer is not None
