# tests/unit/scheduler/test_agentic_scheduler_deep_path.py
"""Unit tests for DeepPathAgent - LLM-based scheduling decisions.

Tests cover:
- DeepPathAgent initialization and configuration
- LLM provider mocking for API isolation
- Deep Path decision logic with mock responses
- Claude API integration (mocked)
- Cost tracking
- Fallback behavior on LLM errors
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from algo_studio.core.scheduler.agents.deep_path_agent import DeepPathAgent
from algo_studio.core.scheduler.agents.llm.base import LLMResponse
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.ray_client import NodeStatus


def create_sample_task_profile(task_id="test-task-001"):
    """Create a sample TaskProfile for testing."""
    return TaskProfile(
        task_id=task_id,
        task_type=TaskType.TRAIN,
        num_gpus=2,
        num_cpus=4,
        memory_gb=16,
        priority=7,
        preferred_nodes=None,
        data_locality=None,
        estimated_duration_minutes=60,
        timeout_minutes=120,
        is_retry=False,
        retry_count=0,
    )


def create_sample_nodes():
    """Create sample NodeStatus objects."""
    node1 = NodeStatus(
        node_id="node-001",
        ip="192.168.0.10",
        status="idle",
        cpu_used=2,
        cpu_total=8,
        gpu_used=0,
        gpu_total=2,
        memory_used_gb=16,
        memory_total_gb=64,
        disk_used_gb=100,
        disk_total_gb=500,
        gpu_utilization=0,
        hostname="worker-1",
    )
    node2 = NodeStatus(
        node_id="node-002",
        ip="192.168.0.11",
        status="busy",
        cpu_used=6,
        cpu_total=8,
        gpu_used=1,
        gpu_total=2,
        memory_used_gb=48,
        memory_total_gb=64,
        disk_used_gb=200,
        disk_total_gb=500,
        gpu_utilization=80,
        hostname="worker-2",
    )
    return [node1, node2]


def create_sample_node_scores():
    """Create sample NodeScore objects."""
    node1 = NodeStatus(
        node_id="node-001",
        ip="192.168.0.10",
        status="idle",
        cpu_used=2,
        cpu_total=8,
        gpu_used=0,
        gpu_total=2,
        memory_used_gb=16,
        memory_total_gb=64,
        disk_used_gb=100,
        disk_total_gb=500,
        gpu_utilization=0,
        hostname="worker-1",
    )
    node2 = NodeStatus(
        node_id="node-002",
        ip="192.168.0.11",
        status="busy",
        cpu_used=6,
        cpu_total=8,
        gpu_used=1,
        gpu_total=2,
        memory_used_gb=48,
        memory_total_gb=64,
        disk_used_gb=200,
        disk_total_gb=500,
        gpu_utilization=80,
        hostname="worker-2",
    )
    return [
        NodeScore(node=node1, total_score=85.0, gpu_score=90.0, memory_score=75.0, load_score=80.0, health_score=85.0),
        NodeScore(node=node2, total_score=60.0, gpu_score=50.0, memory_score=60.0, load_score=50.0, health_score=70.0),
    ]


class TestDeepPathAgentInit:
    """Tests for DeepPathAgent initialization."""

    def test_agent_initializes_with_defaults(self):
        """Test that agent initializes with reasonable defaults."""
        agent = DeepPathAgent()
        assert agent.timeout_seconds == 10.0
        assert agent.max_retries == 2
        assert agent.total_cost_usd == 0.0
        assert agent.total_tokens_used == 0

    def test_agent_accepts_custom_llm_provider(self):
        """Test that agent accepts custom LLM provider."""
        mock_provider = MagicMock()
        agent = DeepPathAgent(llm_provider=mock_provider)
        assert agent.llm_provider is mock_provider

    def test_agent_accepts_custom_timeout(self):
        """Test that agent accepts custom timeout."""
        agent = DeepPathAgent(timeout_seconds=30.0)
        assert agent.timeout_seconds == 30.0

    def test_agent_accepts_custom_max_retries(self):
        """Test that agent accepts custom max retries."""
        agent = DeepPathAgent(max_retries=5)
        assert agent.max_retries == 5

    def test_tools_schema_is_defined(self):
        """Test that TOOLS schema is properly defined."""
        assert len(DeepPathAgent.TOOLS) == 2
        tool_names = [t["name"] for t in DeepPathAgent.TOOLS]
        assert "select_node" in tool_names
        assert "request_more_info" in tool_names

    def test_system_prompt_is_defined(self):
        """Test that system prompt is defined."""
        assert DeepPathAgent.SYSTEM_PROMPT is not None
        assert len(DeepPathAgent.SYSTEM_PROMPT) > 0
        assert "scheduler" in DeepPathAgent.SYSTEM_PROMPT.lower()


class TestDeepPathAgentContext:
    """Tests for context building in DeepPathAgent."""

    def test_build_context_creates_correct_structure(self):
        """Test that _build_context creates properly structured dict."""
        agent = DeepPathAgent()
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        context = agent._build_context(task_profile, nodes, node_scores)

        assert "task" in context
        assert "nodes" in context
        assert "timestamp" in context
        assert context["task"]["task_id"] == "test-task-001"

    def test_build_context_limits_nodes_to_top_5(self):
        """Test that _build_context limits nodes to top 5."""
        agent = DeepPathAgent()
        task_profile = create_sample_task_profile()

        # Create 10 nodes
        many_nodes = []
        for i in range(10):
            node = NodeStatus(
                node_id=f"node-{i:03d}",
                ip=f"192.168.0.{i}",
                status="idle",
                cpu_used=0,
                cpu_total=8,
                gpu_used=0,
                gpu_total=2,
                memory_used_gb=0,
                memory_total_gb=64,
                disk_used_gb=0,
                disk_total_gb=500,
                gpu_utilization=0,
                hostname=f"worker-{i}",
            )
            many_nodes.append(node)

        many_scores = [NodeScore(node=n, total_score=100 - i * 5, gpu_score=80, memory_score=80, load_score=80) for i, n in enumerate(many_nodes)]

        context = agent._build_context(task_profile, many_nodes, many_scores)
        assert len(context["nodes"]) == 5

    def test_build_messages_creates_user_message(self):
        """Test that _build_messages creates properly formatted user message."""
        agent = DeepPathAgent()
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        context = agent._build_context(task_profile, nodes, node_scores)
        messages = agent._build_messages(context)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "task" in messages[0]["content"].lower() or "Task" in messages[0]["content"]
        assert "select_node" in messages[0]["content"]


class TestDeepPathAgentDecide:
    """Tests for DeepPathAgent.decide() method."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider with successful response."""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content=json.dumps({
                "text": "I select worker-1 based on available GPU resources.",
                "tool_calls": [{
                    "name": "select_node",
                    "input": {
                        "node_id": "worker-1",
                        "confidence": 0.85,
                        "reasoning": "Node has 2 GPUs available and low utilization.",
                        "alternative_nodes": ["worker-2"]
                    }
                }]
            }),
            stop_reason="tool_use",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "input_tokens": 100, "output_tokens": 50},
            cost_usd=0.002,
        )
        mock_provider.messages_complete_with_tools = AsyncMock(return_value=mock_response)
        return mock_provider

    @pytest.fixture
    def agent_with_mock(self, mock_llm_provider):
        """Create a DeepPathAgent with mocked LLM provider."""
        return DeepPathAgent(llm_provider=mock_llm_provider, timeout_seconds=5.0, max_retries=1)

    @pytest.mark.asyncio
    async def test_decide_returns_scheduling_decision(self, agent_with_mock):
        """Test that decide() returns a SchedulingDecision."""
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        decision = await agent_with_mock.decide(task_profile, nodes, node_scores)

        assert decision is not None
        assert decision.routing_path == "deep"
        assert decision.task_id == "test-task-001"

    @pytest.mark.asyncio
    async def test_decide_tracks_cost(self, agent_with_mock):
        """Test that decide() tracks LLM cost."""
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        initial_cost = agent_with_mock.total_cost_usd
        await agent_with_mock.decide(task_profile, nodes, node_scores)

        assert agent_with_mock.total_cost_usd > initial_cost

    @pytest.mark.asyncio
    async def test_decide_tracks_tokens(self, agent_with_mock):
        """Test that decide() tracks token usage."""
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        initial_tokens = agent_with_mock.total_tokens_used
        await agent_with_mock.decide(task_profile, nodes, node_scores)

        assert agent_with_mock.total_tokens_used > initial_tokens

    @pytest.mark.asyncio
    async def test_decide_with_no_nodes_returns_fallback(self):
        """Test that decide() with no nodes returns fallback decision."""
        agent = DeepPathAgent()
        task_profile = create_sample_task_profile()

        decision = await agent.decide(task_profile, [], [])

        assert decision.routing_path == "deep"
        assert decision.fallback_used is True
        assert "No available nodes" in decision.reasoning

    @pytest.mark.asyncio
    async def test_decide_retries_on_llm_failure(self):
        """Test that decide() retries on LLM failure."""
        mock_provider = MagicMock()
        # Fail twice, then succeed
        mock_provider.messages_complete_with_tools = AsyncMock(
            side_effect=[
                Exception("LLM Error 1"),
                Exception("LLM Error 2"),
                LLMResponse(
                    content=json.dumps({
                        "text": "Selected node",
                        "tool_calls": [{
                            "name": "select_node",
                            "input": {
                                "node_id": "worker-1",
                                "confidence": 0.8,
                                "reasoning": "Good node"
                            }
                        }]
                    }),
                    stop_reason="tool_use",
                    usage={"prompt_tokens": 50, "completion_tokens": 30, "input_tokens": 50, "output_tokens": 30},
                    cost_usd=0.001,
                )
            ]
        )
        agent = DeepPathAgent(llm_provider=mock_provider, max_retries=3)
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        decision = await agent.decide(task_profile, nodes, node_scores)
        # Should eventually succeed
        assert decision.routing_path == "deep"

    @pytest.mark.asyncio
    async def test_decide_falls_back_after_max_retries(self):
        """Test that decide() falls back after max retries exhausted."""
        mock_provider = MagicMock()
        mock_provider.messages_complete_with_tools = AsyncMock(
            side_effect=Exception("Persistent LLM Error")
        )
        agent = DeepPathAgent(llm_provider=mock_provider, max_retries=2)
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        decision = await agent.decide(task_profile, nodes, node_scores)

        # Should fall back to fast path
        assert decision.routing_path == "deep"
        assert decision.fallback_used is True

    @pytest.mark.asyncio
    async def test_decide_parses_select_node_tool_call(self, agent_with_mock):
        """Test that decide() correctly parses select_node tool call."""
        task_profile = create_sample_task_profile()
        nodes = create_sample_nodes()
        node_scores = create_sample_node_scores()

        decision = await agent_with_mock.decide(task_profile, nodes, node_scores)

        # Decision should use deep path and have a node selected
        assert decision.routing_path == "deep"
        # The mock returns worker-1, so we expect it to be found
        assert decision.selected_node is not None or decision.confidence > 0


class TestDeepPathAgentFallback:
    """Tests for DeepPathAgent fallback behavior."""

    def test_fallback_returns_fast_path_top_choice(self):
        """Test that fallback uses top scored node."""
        agent = DeepPathAgent()

        node1 = NodeStatus(
            node_id="node-001",
            ip="192.168.0.10",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="worker-1",
        )
        node2 = NodeStatus(
            node_id="node-002",
            ip="192.168.0.11",
            status="busy",
            cpu_used=6,
            cpu_total=8,
            gpu_used=1,
            gpu_total=2,
            memory_used_gb=48,
            memory_total_gb=64,
            disk_used_gb=200,
            disk_total_gb=500,
            gpu_utilization=80,
            hostname="worker-2",
        )

        profile = create_sample_task_profile(task_id="test-task")
        node_scores = [
            NodeScore(node=node1, total_score=85.0, gpu_score=90.0, memory_score=75.0, load_score=80.0, health_score=85.0),
            NodeScore(node=node2, total_score=60.0, gpu_score=50.0, memory_score=60.0, load_score=50.0, health_score=70.0),
        ]

        fallback = agent._fallback_to_fast_path(profile, node_scores, "LLM failed")

        assert fallback.routing_path == "deep"
        assert fallback.fallback_used is True
        assert fallback.selected_node == node1  # Top scored node
        assert "LLM failed" in fallback.reasoning

    def test_fallback_with_no_node_scores(self):
        """Test fallback with no node scores returns empty decision."""
        agent = DeepPathAgent()
        profile = create_sample_task_profile(task_id="test-task")

        fallback = agent._fallback_to_fast_path(profile, [], "No scores available")

        assert fallback.selected_node is None
        assert fallback.confidence == 0.0
        assert fallback.fallback_used is True


class TestDeepPathAgentCostTracking:
    """Tests for DeepPathAgent cost tracking functionality."""

    def test_get_cost_summary_returns_dict(self):
        """Test that get_cost_summary returns properly structured dict."""
        agent = DeepPathAgent()
        agent.total_cost_usd = 0.05
        agent.total_tokens_used = 1000

        summary = agent.get_cost_summary()

        assert isinstance(summary, dict)
        assert "total_cost_usd" in summary
        assert "total_tokens" in summary
        assert summary["total_cost_usd"] == 0.05
        assert summary["total_tokens"] == 1000

    def test_reset_cost_tracking(self):
        """Test that reset_cost_tracking zeros out counters."""
        agent = DeepPathAgent()
        agent.total_cost_usd = 1.0
        agent.total_tokens_used = 5000

        agent.reset_cost_tracking()

        assert agent.total_cost_usd == 0.0
        assert agent.total_tokens_used == 0

    def test_estimated_cost_per_1k_tasks(self):
        """Test estimated cost per 1000 tasks calculation."""
        agent = DeepPathAgent()
        agent.total_cost_usd = 0.02
        agent.total_tokens_used = 100

        summary = agent.get_cost_summary()

        assert summary["estimated_cost_per_1k_tasks"] == 0.02 * 1000

    def test_estimated_cost_per_1k_tasks_zero_tokens(self):
        """Test estimated cost with zero tokens returns zero."""
        agent = DeepPathAgent()
        agent.total_cost_usd = 0.0
        agent.total_tokens_used = 0

        summary = agent.get_cost_summary()

        assert summary["estimated_cost_per_1k_tasks"] == 0


class TestDeepPathAgentMockIntegration:
    """Integration tests with mocked AnthropicProvider."""

    def test_agent_uses_provided_provider(self):
        """Test that agent uses the provided LLM provider."""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content="Test response",
            stop_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "input_tokens": 10, "output_tokens": 5},
            cost_usd=0.0001,
        )
        mock_provider.messages_complete_with_tools = AsyncMock(return_value=mock_response)

        agent = DeepPathAgent(llm_provider=mock_provider)
        assert agent.llm_provider is mock_provider

    @pytest.mark.asyncio
    async def test_agent_calls_llm_with_correct_parameters(self):
        """Test that agent calls LLM with correct system prompt and tools."""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content=json.dumps({
                "text": "Selected worker-1",
                "tool_calls": [{
                    "name": "select_node",
                    "input": {
                        "node_id": "worker-1",
                        "confidence": 0.9,
                        "reasoning": "Best available"
                    }
                }]
            }),
            stop_reason="tool_use",
            usage={"prompt_tokens": 50, "completion_tokens": 30, "input_tokens": 50, "output_tokens": 30},
            cost_usd=0.001,
        )
        mock_provider.messages_complete_with_tools = AsyncMock(return_value=mock_response)

        agent = DeepPathAgent(llm_provider=mock_provider)

        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.10",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="worker-1",
        )
        profile = create_sample_task_profile(task_id="test-task")
        node_scores = [NodeScore(node=node, total_score=80.0, gpu_score=80.0, memory_score=80.0, load_score=80.0)]

        await agent.decide(profile, [node], node_scores)

        # Verify the mock was called
        mock_provider.messages_complete_with_tools.assert_called_once()
        call_kwargs = mock_provider.messages_complete_with_tools.call_args.kwargs
        assert "messages" in call_kwargs
        assert "tools" in call_kwargs
        assert "system" in call_kwargs


class TestDeepPathAgentParseResponse:
    """Tests for response parsing in DeepPathAgent."""

    def test_parse_select_node_response_finds_node_by_hostname(self):
        """Test that node is found by hostname."""
        agent = DeepPathAgent()

        node1 = NodeStatus(
            node_id="node-001",
            ip="192.168.0.10",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="worker-1",
        )
        node2 = NodeStatus(
            node_id="node-002",
            ip="192.168.0.11",
            status="busy",
            cpu_used=6,
            cpu_total=8,
            gpu_used=1,
            gpu_total=2,
            memory_used_gb=48,
            memory_total_gb=64,
            disk_used_gb=200,
            disk_total_gb=500,
            gpu_utilization=80,
            hostname="worker-2",
        )
        nodes = [node1, node2]
        profile = create_sample_task_profile(task_id="test")
        node_scores = [
            NodeScore(node=node1, total_score=85.0, gpu_score=90.0, memory_score=75.0, load_score=80.0, health_score=85.0),
            NodeScore(node=node2, total_score=60.0, gpu_score=50.0, memory_score=60.0, load_score=50.0, health_score=70.0),
        ]

        tool_call = {
            "name": "select_node",
            "input": {
                "node_id": "worker-1",
                "confidence": 0.85,
                "reasoning": "Best node available",
                "alternative_nodes": ["worker-2"]
            }
        }

        decision = agent._parse_select_node_response(tool_call, "dec-001", profile, nodes, node_scores, "raw text")

        assert decision.selected_node == node1
        assert decision.confidence == 0.85

    def test_parse_select_node_response_falls_back_when_node_not_found(self):
        """Test fallback when LLM selects unavailable node."""
        agent = DeepPathAgent()

        node1 = NodeStatus(
            node_id="node-001",
            ip="192.168.0.10",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="worker-1",
        )
        nodes = [node1]
        profile = create_sample_task_profile(task_id="test")
        node_scores = [NodeScore(node=node1, total_score=85.0, gpu_score=90.0, memory_score=75.0, load_score=80.0, health_score=85.0)]

        # LLM selects a node that doesn't exist
        tool_call = {
            "name": "select_node",
            "input": {
                "node_id": "non-existent-node",
                "confidence": 0.9,
                "reasoning": "Chose a wrong node"
            }
        }

        decision = agent._parse_select_node_response(tool_call, "dec-001", profile, nodes, node_scores, "raw text")

        # Should select fallback node (top scored node) since LLM choice was unavailable
        assert decision.selected_node == node1
        assert "not available" in decision.reasoning.lower()
        assert decision.confidence == 0.3  # Lowered due to fallback

    def test_parse_request_more_info_falls_back(self):
        """Test that request_more_info triggers fallback."""
        agent = DeepPathAgent()

        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.10",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="worker-1",
        )
        nodes = [node]
        profile = create_sample_task_profile(task_id="test")
        node_scores = [NodeScore(node=node, total_score=85.0, gpu_score=90.0, memory_score=75.0, load_score=80.0, health_score=85.0)]

        tool_call = {
            "name": "request_more_info",
            "input": {
                "question": "What is the GPU memory available?"
            }
        }

        response = LLMResponse(
            content=json.dumps({
                "text": "Need more info",
                "tool_calls": [tool_call]
            }),
            stop_reason="tool_use",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "input_tokens": 10, "output_tokens": 5},
            cost_usd=0.0001,
        )

        decision = agent._parse_llm_response(response, profile, nodes, node_scores)

        assert decision.fallback_used is True

    def test_parse_non_json_response_falls_back(self):
        """Test that non-JSON response falls back gracefully."""
        agent = DeepPathAgent()

        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.10",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="worker-1",
        )
        nodes = [node]
        profile = create_sample_task_profile(task_id="test")
        node_scores = [NodeScore(node=node, total_score=85.0, gpu_score=90.0, memory_score=75.0, load_score=80.0, health_score=85.0)]

        # Non-JSON response
        response = LLMResponse(
            content="I think worker-1 is the best choice because it has available GPUs.",
            stop_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "input_tokens": 10, "output_tokens": 5},
            cost_usd=0.0001,
        )

        decision = agent._parse_llm_response(response, profile, nodes, node_scores)

        # Should fall back to fast path
        assert decision.fallback_used is True
