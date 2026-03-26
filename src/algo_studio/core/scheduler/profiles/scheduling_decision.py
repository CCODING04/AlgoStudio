"""
SchedulingDecision - Final scheduling decision output
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.node_score import NodeScore


@dataclass
class SchedulingDecision:
    """
    Scheduling decision result.
    """

    decision_id: str
    task_id: str

    selected_node: Optional[NodeStatus]  # Selected node (None if no available node)
    alternative_nodes: List[NodeScore] = field(default_factory=list)  # Alternative nodes

    routing_path: str = "fast"  # "fast" | "deep"
    confidence: float = 0.0    # Confidence 0.0 - 1.0
    reasoning: str = ""

    created_at: datetime = field(default_factory=datetime.now)

    # Fallback information
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if decision is valid"""
        return self.selected_node is not None

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "decision_id": self.decision_id,
            "task_id": self.task_id,
            "selected_node": {
                "node_id": self.selected_node.node_id if self.selected_node else None,
                "hostname": self.selected_node.hostname if self.selected_node else None,
                "ip": self.selected_node.ip if self.selected_node else None,
            } if self.selected_node else None,
            "alternative_nodes": [ns.to_dict() for ns in self.alternative_nodes],
            "routing_path": self.routing_path,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
        }
