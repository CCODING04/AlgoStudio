"""
NodeScore - Node scoring result for scheduling decisions
"""

from dataclasses import dataclass, field
from typing import List, Optional

from algo_studio.core.ray_client import NodeStatus


@dataclass
class NodeScore:
    """
    Node scoring result with multi-dimensional evaluation.
    """

    node: NodeStatus

    # Dimension scores (0-100)
    gpu_score: float = 0.0       # GPU match score
    memory_score: float = 0.0   # Memory match score
    load_score: float = 0.0     # Current load score (lower load = higher score)
    health_score: float = 0.0   # Health score
    affinity_score: float = 0.0 # Affinity score

    # Overall score
    total_score: float = 0.0

    # Scoring reasons
    reasons: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """Check if node is usable (has enough resources)"""
        return self.total_score > 0

    def explain_score(self) -> str:
        """
        Generate human-readable explanation of the score.
        """
        lines = [
            f"Node: {self.node.hostname or self.node.ip}",
            f"Total Score: {self.total_score:.1f}/100",
            "",
            "Dimension Scores:",
            f"  GPU Match:     {self.gpu_score:.1f}/100",
            f"  Memory Match:  {self.memory_score:.1f}/100",
            f"  Load Score:    {self.load_score:.1f}/100",
            f"  Health Score: {self.health_score:.1f}/100",
            f"  Affinity:      {self.affinity_score:.1f}/100",
            "",
        ]

        if self.reasons:
            lines.append("Reasons:")
            for reason in self.reasons:
                lines.append(f"  + {reason}")

        if self.concerns:
            lines.append("Concerns:")
            for concern in self.concerns:
                lines.append(f"  - {concern}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "node_id": self.node.node_id,
            "hostname": self.node.hostname,
            "ip": self.node.ip,
            "gpu_score": self.gpu_score,
            "memory_score": self.memory_score,
            "load_score": self.load_score,
            "health_score": self.health_score,
            "affinity_score": self.affinity_score,
            "total_score": self.total_score,
            "reasons": self.reasons,
            "concerns": self.concerns,
        }
