"""
FastPathScheduler - Fast Path rule-based scheduler
"""

import uuid
from datetime import datetime
from typing import List, Optional

from algo_studio.core.task import Task
from algo_studio.core.ray_client import NodeStatus, RayClient
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.scheduler.analyzers.default_analyzer import DefaultTaskAnalyzer
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer
from algo_studio.core.scheduler.validators.resource_validator import ResourceValidator
from algo_studio.core.scheduler.exceptions import NoAvailableNodeError


class FastPathScheduler:
    """
    Fast Path scheduler using rule-based decision making.

    This is the synchronous scheduling path with < 10ms latency.
    """

    def __init__(
        self,
        task_analyzer=None,
        node_scorer=None,
        validator=None,
    ):
        """
        Initialize Fast Path scheduler.

        Args:
            task_analyzer: Task analyzer (uses DefaultTaskAnalyzer if None)
            node_scorer: Node scorer (uses MultiDimNodeScorer if None)
            validator: Safety validator (uses ResourceValidator if None)
        """
        self.task_analyzer = task_analyzer or DefaultTaskAnalyzer()
        self.node_scorer = node_scorer or MultiDimNodeScorer()
        self.validator = validator or ResourceValidator()

    def schedule(
        self,
        task: Task,
        nodes: List[NodeStatus],
    ) -> SchedulingDecision:
        """
        Make scheduling decision using Fast Path.

        Args:
            task: Task to schedule
            nodes: Available nodes

        Returns:
            SchedulingDecision: Scheduling decision

        Raises:
            NoAvailableNodeError: If no suitable node is available
        """
        decision_id = f"fp-{uuid.uuid4().hex[:8]}"

        # Step 1: Analyze task
        task_profile = self.task_analyzer.analyze(task)

        # Step 2: Score nodes
        node_scores = self.node_scorer.score(task_profile, nodes)

        if not node_scores:
            return SchedulingDecision(
                decision_id=decision_id,
                task_id=task.task_id,
                selected_node=None,
                routing_path="fast",
                confidence=0.0,
                reasoning="No available nodes found",
                fallback_used=False,
            )

        # Step 3: Validate best node
        best_score = node_scores[0]
        validation = self.validator.validate(best_score, task_profile)

        if not validation.is_valid:
            # Try alternatives
            for alt_score in node_scores[1:]:
                alt_validation = self.validator.validate(alt_score, task_profile)
                if alt_validation.is_valid:
                    best_score = alt_score
                    validation = alt_validation
                    break

            if not validation.is_valid:
                # Fallback: use best node anyway with warnings
                return SchedulingDecision(
                    decision_id=decision_id,
                    task_id=task.task_id,
                    selected_node=best_score.node,
                    alternative_nodes=node_scores[1:5],  # Top 4 alternatives
                    routing_path="fast",
                    confidence=0.3,
                    reasoning=f"Validation warnings: {'; '.join(validation.warnings)}",
                    fallback_used=True,
                    fallback_reason="Validation warnings present",
                )

        # Step 4: Build reasoning
        reasoning = self._build_reasoning(task_profile, best_score)

        return SchedulingDecision(
            decision_id=decision_id,
            task_id=task.task_id,
            selected_node=best_score.node,
            alternative_nodes=node_scores[1:5],  # Top 4 alternatives
            routing_path="fast",
            confidence=best_score.total_score / 100.0,
            reasoning=reasoning,
            fallback_used=False,
        )

    def _build_reasoning(self, task_profile: TaskProfile, best_score: NodeScore) -> str:
        """Build human-readable reasoning for decision"""
        lines = [
            f"Selected {best_score.node.hostname or best_score.node.ip} for {task_profile.task_type.value} task",
            f"Total score: {best_score.total_score:.1f}/100",
        ]

        if best_score.reasons:
            lines.append("Reasons:")
            for reason in best_score.reasons[:3]:  # Top 3 reasons
                lines.append(f"  + {reason}")

        return "\n".join(lines)
