"""
AgenticScheduler - Main scheduler facade with Fast/Deep path routing
"""

import os
import uuid
from datetime import datetime
from typing import List, Optional

from algo_studio.core.task import Task
from algo_studio.core.ray_client import NodeStatus, RayClient
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.scheduler.agents.fast_scheduler import FastPathScheduler
from algo_studio.core.scheduler.agents.deep_path_agent import DeepPathAgent
from algo_studio.core.scheduler.routing.router import Router
from algo_studio.core.scheduler.analyzers.default_analyzer import DefaultTaskAnalyzer
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer
from algo_studio.core.scheduler.validators.resource_validator import ResourceValidator
from algo_studio.core.scheduler.exceptions import NoAvailableNodeError


class AgenticScheduler:
    """
    Agentic scheduler with Fast/Deep path routing.

    This is the main entry point for the AI scheduling module.

    Usage:
        scheduler = AgenticScheduler()
        decision = scheduler.schedule(task)
        if decision.selected_node:
            # Use decision.selected_node for task execution
    """

    def __init__(
        self,
        ray_client: RayClient = None,
        fast_scheduler: FastPathScheduler = None,
        router: Router = None,
        deep_path_agent: DeepPathAgent = None,
    ):
        """
        Initialize Agentic scheduler.

        Args:
            ray_client: Ray client for getting node status (optional for Fast Path)
            fast_scheduler: Fast Path scheduler (uses default if None)
            router: Router for Fast/Deep path decision (uses default if None)
            deep_path_agent: Deep Path agent for LLM-based scheduling (M4)
        """
        self.ray_client = ray_client
        self.fast_scheduler = fast_scheduler or FastPathScheduler()
        self.router = router or Router()
        self.deep_path_agent = deep_path_agent

        # Components for analysis
        self.task_analyzer = DefaultTaskAnalyzer()
        self.node_scorer = MultiDimNodeScorer()
        self.validator = ResourceValidator()

        # Deep Path configuration (M4)
        self._deep_path_enabled = self._check_llm_available()

    def _check_llm_available(self) -> bool:
        """
        Check if LLM is available for Deep Path.

        Returns:
            bool: True if ANTHROPIC_API_KEY is set
        """
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    @property
    def deep_path_enabled(self) -> bool:
        """Check if Deep Path is enabled"""
        return self._deep_path_enabled

    @property
    def llm_available(self) -> bool:
        """Check if LLM is available (alias for deep_path_enabled)"""
        return self._deep_path_enabled

    def enable_deep_path(self, agent: DeepPathAgent = None):
        """
        Enable Deep Path with optional custom agent.

        Args:
            agent: Custom DeepPathAgent (uses default if None)
        """
        if agent:
            self.deep_path_agent = agent
        elif self.deep_path_agent is None:
            self.deep_path_agent = DeepPathAgent()
        self._deep_path_enabled = True

    def disable_deep_path(self):
        """Disable Deep Path (use Fast Path only)"""
        self._deep_path_enabled = False

    def schedule(self, task: Task) -> SchedulingDecision:
        """
        Synchronous scheduling decision (Fast Path or Deep Path fallback).

        This is the main scheduling method.

        Args:
            task: Task to schedule

        Returns:
            SchedulingDecision: Scheduling decision
        """
        # Get node status
        if self.ray_client is None:
            # Default RayClient if not provided
            self.ray_client = RayClient()

        nodes = self.ray_client.get_nodes()

        # Analyze task
        task_profile = self.task_analyzer.analyze(task)

        # Score nodes
        node_scores = self.node_scorer.score(task_profile, nodes)

        # Check if Deep Path should be used
        use_deep_path = self.should_use_deep_path(task_profile)

        if use_deep_path and self._deep_path_enabled and self.deep_path_agent:
            # Use Deep Path (synchronously for now - will be async in full M4)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we need to schedule it
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.deep_path_agent.decide(task_profile, nodes, node_scores)
                        )
                        decision = future.result(timeout=15)
                else:
                    decision = loop.run_until_complete(
                        self.deep_path_agent.decide(task_profile, nodes, node_scores)
                    )
            except Exception:
                # Fall back to Fast Path on any error
                decision = self.fast_scheduler.schedule(task, nodes)
                decision.routing_path = "deep"
                decision.fallback_used = True
                decision.fallback_reason = "Deep Path error, using Fast Path"

            decision.reasoning = f"[{self.router.get_routing_reason(task_profile)}]\n\n{decision.reasoning}"
            return decision

        # Use Fast Path
        return self.fast_scheduler.schedule(task, nodes)

    async def schedule_async(self, task: Task) -> SchedulingDecision:
        """
        Asynchronous scheduling decision (supports Deep Path with LLM).

        This is the async version that properly awaits LLM calls.

        Args:
            task: Task to schedule

        Returns:
            SchedulingDecision: Scheduling decision
        """
        # When not using deep path, delegate to sync schedule
        if not self._deep_path_enabled or not self.deep_path_agent:
            return self.schedule(task)

        # Get node status
        if self.ray_client is None:
            self.ray_client = RayClient()

        nodes = self.ray_client.get_nodes()

        # Analyze task
        task_profile = self.task_analyzer.analyze(task)

        # Score nodes
        node_scores = self.node_scorer.score(task_profile, nodes)

        # Check if Deep Path should be used
        use_deep_path = self.should_use_deep_path(task_profile)

        if use_deep_path and self._deep_path_enabled and self.deep_path_agent:
            # Use Deep Path with async LLM call
            try:
                decision = await self.deep_path_agent.decide(task_profile, nodes, node_scores)
                decision.reasoning = f"[{self.router.get_routing_reason(task_profile)}]\n\n{decision.reasoning}"
                return decision
            except Exception as e:
                # Fall back to Fast Path on any error
                decision = self.fast_scheduler.schedule(task, nodes)
                decision.routing_path = "deep"
                decision.fallback_used = True
                decision.fallback_reason = f"Deep Path error: {str(e)}, using Fast Path"
                return decision

        # Use Fast Path (delegate to sync schedule)
        return self.schedule(task)

    def should_use_deep_path(self, task_profile: TaskProfile) -> bool:
        """
        Determine if task should use Deep Path.

        Args:
            task_profile: Task profile

        Returns:
            bool: True if should use Deep Path
        """
        return self.router.should_use_deep_path(task_profile)

    def should_use_deep_path_with_context(
        self,
        task_profile: TaskProfile,
        queue_length: int,
        avg_node_load: float,
    ) -> bool:
        """
        Determine if task should use Deep Path with full context.

        Args:
            task_profile: Task profile
            queue_length: Current queue length
            avg_node_load: Average node load

        Returns:
            bool: True if should use Deep Path
        """
        return self.router.should_use_deep_path_with_context(
            task_profile, queue_length, avg_node_load
        )

    def get_scheduler_status(self) -> dict:
        """
        Get scheduler status.

        Returns:
            dict: Status information
        """
        status = {
            "status": "healthy",
            "fast_path_enabled": True,
            "deep_path_enabled": self._deep_path_enabled,
            "llm_available": self._deep_path_enabled,
            "components": {
                "task_analyzer": "DefaultTaskAnalyzer",
                "node_scorer": "MultiDimNodeScorer",
                "validator": "ResourceValidator",
                "router": "Router",
                "fast_scheduler": "FastPathScheduler",
            },
        }

        if self._deep_path_enabled and self.deep_path_agent:
            status["deep_path_agent"] = "DeepPathAgent"
            status["cost_summary"] = self.deep_path_agent.get_cost_summary()

        return status

    def get_routing_decision(self, task_profile: TaskProfile) -> dict:
        """
        Get detailed routing decision information.

        Args:
            task_profile: Task profile

        Returns:
            dict: Routing decision details
        """
        should_use_deep = self.should_use_deep_path(task_profile)
        reason = self.router.get_routing_reason(task_profile)

        return {
            "task_id": task_profile.task_id,
            "selected_path": "deep" if should_use_deep else "fast",
            "reason": reason,
            "deep_path_available": self._deep_path_enabled,
            "task_complexity": task_profile.complexity,
            "is_retry": task_profile.is_retry,
            "has_affinity": bool(task_profile.preferred_nodes),
            "timeout_minutes": task_profile.timeout_minutes,
        }