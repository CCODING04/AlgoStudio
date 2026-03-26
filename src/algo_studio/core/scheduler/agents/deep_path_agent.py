"""
DeepPathAgent - LLM-based scheduling decision maker using Claude Function Calling
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable

from algo_studio.core.task import Task
from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.scheduler.agents.llm.anthropic_provider import AnthropicProvider
from algo_studio.core.scheduler.agents.llm.base import LLMResponse
from algo_studio.core.scheduler.exceptions import LLMError, SchedulingError


class DeepPathAgent:
    """
    Deep Path agent using Claude LLM for complex scheduling decisions.

    Uses Function Calling to allow Claude to select the best node
    based on task requirements and cluster state.
    """

    # System prompt for the scheduling agent
    SYSTEM_PROMPT = """You are an expert AI scheduler for a distributed Ray cluster. Your job is to select the optimal node for running computational tasks.

You have access to cluster information including:
- Node resource availability (CPU, GPU, memory)
- Node health and current load
- Historical task success rates on each node
- Task requirements (GPU, memory, affinity preferences)

When making scheduling decisions:
1. Prioritize nodes with sufficient resources
2. Consider data locality if specified
3. Prefer nodes with higher historical success rates for similar tasks
4. Avoid overloaded nodes
5. Respect node affinity preferences when possible

You will respond with your reasoning and use the select_node function to make your final decision."""

    # Function calling schema for node selection
    TOOLS = [
        {
            "name": "select_node",
            "description": "Select the optimal node for task execution based on task requirements and cluster state.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "The node_id (hostname or IP) of the selected node"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score (0.0-1.0) for this decision"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Detailed reasoning for why this node was selected"
                    },
                    "alternative_nodes": {
                        "type": "array",
                        "description": "List of alternative nodes in order of preference",
                        "items": {"type": "string"}
                    }
                },
                "required": ["node_id", "confidence", "reasoning"]
            }
        },
        {
            "name": "request_more_info",
            "description": "Request additional information about nodes or tasks when the available information is insufficient.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The specific question or information request"
                    }
                },
                "required": ["question"]
            }
        }
    ]

    def __init__(
        self,
        llm_provider: AnthropicProvider = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
    ):
        """
        Initialize Deep Path agent.

        Args:
            llm_provider: LLM provider (uses AnthropicProvider if None)
            timeout_seconds: Maximum time to wait for LLM response
            max_retries: Maximum number of retries on LLM failure
        """
        self.llm_provider = llm_provider
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Cost tracking
        self.total_cost_usd = 0.0
        self.total_tokens_used = 0

    async def decide(
        self,
        task_profile: TaskProfile,
        nodes: List[NodeStatus],
        node_scores: List[NodeScore],
    ) -> SchedulingDecision:
        """
        Make a scheduling decision using LLM-based reasoning.

        Args:
            task_profile: Task characteristics profile
            nodes: Available nodes
            node_scores: Scored nodes from Fast Path

        Returns:
            SchedulingDecision: Scheduling decision with LLM reasoning

        Raises:
            LLMError: If LLM call fails after retries
            SchedulingError: If no decision can be made
        """
        if not nodes:
            return SchedulingDecision(
                decision_id=f"deep-{uuid.uuid4().hex[:8]}",
                task_id=task_profile.task_id,
                selected_node=None,
                routing_path="deep",
                confidence=0.0,
                reasoning="No available nodes",
                fallback_used=True,
                fallback_reason="No nodes available",
            )

        # Build context for LLM
        context = self._build_context(task_profile, nodes, node_scores)
        messages = self._build_messages(context)

        # Try LLM call with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self._call_llm_with_timeout(messages)
                decision = self._parse_llm_response(response, task_profile, nodes, node_scores)

                # Track cost
                self.total_cost_usd += response.cost_usd
                self.total_tokens_used += response.usage.get("prompt_tokens", 0) + response.usage.get("completion_tokens", 0)

                return decision

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

        # All retries failed - fall back to Fast Path decision
        return self._fallback_to_fast_path(task_profile, node_scores, str(last_error))

    def _build_context(
        self,
        task_profile: TaskProfile,
        nodes: List[NodeStatus],
        node_scores: List[NodeScore],
    ) -> Dict[str, Any]:
        """Build context dictionary for LLM prompt"""
        # Create node information summaries
        node_summaries = []
        for node, score in zip(nodes[:5], node_scores[:5]):  # Top 5 nodes
            node_summaries.append({
                "node_id": node.node_id,
                "hostname": node.hostname,
                "ip": node.ip,
                "status": node.status,
                "cpu_available": node.cpu_available,
                "gpu_available": node.gpu_available,
                "memory_available_gb": node.memory_available_gb,
                "gpu_utilization": node.gpu_utilization,
                "total_score": score.total_score if score else 0,
            })

        return {
            "task": task_profile.to_dict(),
            "nodes": node_summaries,
            "timestamp": datetime.now().isoformat(),
        }

    def _build_messages(self, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build messages for LLM conversation"""
        # Format the task requirements
        task_info = context["task"]
        nodes_info = json.dumps(context["nodes"], indent=2)

        user_message = f"""Please analyze the following task and select the optimal node:

## Task Requirements
- Task ID: {task_info['task_id']}
- Task Type: {task_info['task_type']}
- Required GPUs: {task_info['num_gpus']}
- Required CPUs: {task_info['num_cpus']}
- Required Memory: {task_info['memory_gb']} GB
- Priority: {task_info['priority']}/10
- Preferred Nodes: {task_info['preferred_nodes'] or 'None'}
- Data Locality: {task_info['data_locality'] or 'None'}
- Estimated Duration: {task_info['estimated_duration_minutes']} minutes
- Timeout: {task_info['timeout_minutes']} minutes
- Is Retry: {task_info['is_retry']}
- Complexity Score: {task_info['complexity']}/10

## Available Nodes (sorted by Fast Path score)
{nodes_info}

Please select the best node using the select_node function, or ask for more information if needed."""

        return [
            {"role": "user", "content": user_message}
        ]

    async def _call_llm_with_timeout(
        self,
        messages: List[Dict[str, str]],
    ) -> LLMResponse:
        """Call LLM with timeout"""
        provider = self.llm_provider
        if provider is None:
            from algo_studio.core.scheduler.agents.llm.anthropic_provider import get_anthropic_provider
            provider = get_anthropic_provider()

        try:
            return await asyncio.wait_for(
                provider.messages_complete_with_tools(
                    messages=messages,
                    tools=self.TOOLS,
                    system=self.SYSTEM_PROMPT,
                    temperature=0.3,  # Lower temperature for more consistent decisions
                ),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise LLMError(f"LLM call timed out after {self.timeout_seconds}s")

    def _parse_llm_response(
        self,
        response: LLMResponse,
        task_profile: TaskProfile,
        nodes: List[NodeStatus],
        node_scores: List[NodeScore],
    ) -> SchedulingDecision:
        """Parse LLM response into SchedulingDecision"""
        decision_id = f"deep-{uuid.uuid4().hex[:8]}"

        # Try to parse tool call from response
        try:
            parsed = json.loads(response.content)

            if isinstance(parsed, dict) and "tool_calls" in parsed:
                tool_calls = parsed["tool_calls"]
                for tool_call in tool_calls:
                    if tool_call.get("name") == "select_node":
                        return self._parse_select_node_response(
                            tool_call, decision_id, task_profile, nodes, node_scores, response.content
                        )
                    elif tool_call.get("name") == "request_more_info":
                        # Fall back to Fast Path if LLM needs more info
                        return self._fallback_to_fast_path(
                            task_profile, node_scores, "LLM requested more information"
                        )

            # If we got here, use the text content
            reasoning = parsed.get("text", response.content) if isinstance(parsed, dict) else response.content

        except (json.JSONDecodeError, TypeError):
            reasoning = response.content

        # Fall back to Fast Path with reasoning as context
        return self._fallback_to_fast_path(task_profile, node_scores, reasoning)

    def _parse_select_node_response(
        self,
        tool_call: Dict[str, Any],
        decision_id: str,
        task_profile: TaskProfile,
        nodes: List[NodeStatus],
        node_scores: List[NodeScore],
        raw_reasoning: str,
    ) -> SchedulingDecision:
        """Parse select_node tool call into SchedulingDecision"""
        tool_input = tool_call.get("input", {})
        selected_node_id = tool_input.get("node_id")
        confidence = tool_input.get("confidence", 0.5)
        reasoning = tool_input.get("reasoning", "")
        alternative_nodes = tool_input.get("alternative_nodes", [])

        # Find the selected node
        selected_node = None
        for node in nodes:
            if node.hostname == selected_node_id or node.ip == selected_node_id or node.node_id == selected_node_id:
                selected_node = node
                break

        # If node not found, try to use top scored node
        if selected_node is None and node_scores:
            selected_node = node_scores[0].node
            confidence = 0.3
            reasoning = f"Selected top-scored node as LLM choice was not available. {reasoning}"

        # Build alternative node scores
        alt_node_scores = []
        if alternative_nodes:
            for alt_id in alternative_nodes:
                for ns in node_scores:
                    if ns.node.hostname == alt_id or ns.node.ip == alt_id or ns.node.node_id == alt_id:
                        alt_node_scores.append(ns)
                        break

        # Add raw reasoning
        full_reasoning = f"[Deep Path LLM Decision]\n{reasoning}\n\n[Fast Path Context]\nConsidered {len(nodes)} nodes with scores 0-{max(ns.total_score for ns in node_scores) if node_scores else 0}"

        return SchedulingDecision(
            decision_id=decision_id,
            task_id=task_profile.task_id,
            selected_node=selected_node,
            alternative_nodes=alt_node_scores or node_scores[1:5],
            routing_path="deep",
            confidence=confidence,
            reasoning=full_reasoning,
            fallback_used=(selected_node is None),
            fallback_reason=None if selected_node else "LLM selected unavailable node",
        )

    def _fallback_to_fast_path(
        self,
        task_profile: TaskProfile,
        node_scores: List[NodeScore],
        reason: str,
    ) -> SchedulingDecision:
        """Fall back to Fast Path decision when LLM fails"""
        if not node_scores:
            return SchedulingDecision(
                decision_id=f"deep-{uuid.uuid4().hex[:8]}",
                task_id=task_profile.task_id,
                selected_node=None,
                routing_path="deep",
                confidence=0.0,
                reasoning=f"Deep Path failed: {reason}. No fallback nodes available.",
                fallback_used=True,
                fallback_reason=reason,
            )

        best = node_scores[0]
        reasoning = f"[Deep Path Fallback to Fast Path]\nLLM reasoning: {reason}\nUsing Fast Path top choice: {best.node.hostname or best.node.ip}"

        return SchedulingDecision(
            decision_id=f"deep-{uuid.uuid4().hex[:8]}",
            task_id=task_profile.task_id,
            selected_node=best.node,
            alternative_nodes=node_scores[1:5],
            routing_path="deep",
            confidence=best.total_score / 100.0 * 0.8,  # Reduce confidence due to fallback
            reasoning=reasoning,
            fallback_used=True,
            fallback_reason=reason,
        )

    def get_cost_summary(self) -> Dict[str, Any]:
        """
        Get cost tracking summary.

        Returns:
            dict: Cost summary including total cost and tokens
        """
        return {
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens_used,
            "estimated_cost_per_1k_tasks": self.total_cost_usd * 1000 if self.total_tokens_used > 0 else 0,
        }

    def reset_cost_tracking(self):
        """Reset cost tracking counters"""
        self.total_cost_usd = 0.0
        self.total_tokens_used = 0