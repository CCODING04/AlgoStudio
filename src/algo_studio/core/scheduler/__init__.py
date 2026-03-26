"""
AlgoStudio Agentic Scheduler Module

Provides intelligent task scheduling with Fast/Deep path routing.
"""

from algo_studio.core.scheduler.agentic_scheduler import AgenticScheduler
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.scheduler.exceptions import (
    SchedulingError,
    NoAvailableNodeError,
    ValidationError,
    AnalysisError,
    LLMError,
)
from algo_studio.core.scheduler.agents.deep_path_agent import DeepPathAgent
from algo_studio.core.scheduler.agents.llm import (
    AnthropicProvider,
    get_anthropic_provider,
    estimate_llm_cost,
)

__all__ = [
    # Main scheduler
    "AgenticScheduler",
    # Data structures
    "TaskProfile",
    "TaskType",
    "NodeScore",
    "SchedulingDecision",
    # Exceptions
    "SchedulingError",
    "NoAvailableNodeError",
    "ValidationError",
    "AnalysisError",
    "LLMError",
    # Deep Path (M4)
    "DeepPathAgent",
    "AnthropicProvider",
    "get_anthropic_provider",
    "estimate_llm_cost",
]