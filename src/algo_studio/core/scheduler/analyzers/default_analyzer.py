"""
DefaultTaskAnalyzer - Default implementation of TaskAnalyzer
"""

from typing import Any, Dict

from algo_studio.core.task import Task, TaskType as CoreTaskType, TaskStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.analyzers.base import TaskAnalyzerInterface
from algo_studio.core.scheduler.exceptions import AnalysisError


class DefaultTaskAnalyzer(TaskAnalyzerInterface):
    """
    Default task analyzer that extracts task profiles from Task objects.

    Uses algorithm metadata and task configuration to determine resource
    requirements and scheduling preferences.
    """

    # Default resource requirements by task type
    DEFAULT_REQUIREMENTS: Dict[CoreTaskType, Dict[str, Any]] = {
        CoreTaskType.TRAIN: {
            "num_gpus": 1,
            "num_cpus": 4,
            "memory_gb": 16.0,
            "estimated_duration_minutes": 60,
        },
        CoreTaskType.INFER: {
            "num_gpus": 0,
            "num_cpus": 2,
            "memory_gb": 4.0,
            "estimated_duration_minutes": 10,
        },
        CoreTaskType.VERIFY: {
            "num_gpus": 0,
            "num_cpus": 2,
            "memory_gb": 4.0,
            "estimated_duration_minutes": 15,
        },
    }

    # Priority mapping from algorithm config
    PRIORITY_KEYS = ["priority", "task_priority", "user_priority"]

    # Affinity keys
    AFFINITY_KEYS = ["preferred_node", "preferred_nodes", "node_affinity", "affinity"]

    # Data locality keys
    LOCALITY_KEYS = ["data_path", "data_locality", "data_node", "dataset_path"]

    def analyze(self, task: Task) -> TaskProfile:
        """
        Analyze task and generate task profile.

        Args:
            task: Task object to analyze

        Returns:
            TaskProfile: Generated task profile

        Raises:
            AnalysisError: When analysis fails
        """
        try:
            task_type = self._map_task_type(task.task_type)
            resources = self.get_resource_requirements(task)
            priority = self._extract_priority(task)
            preferred_nodes = self._extract_preferred_nodes(task)
            data_locality = self._extract_data_locality(task)
            timeout = self._extract_timeout(task)

            # Estimate duration based on task type and config
            estimated_duration = self._estimate_duration(task, resources)

            return TaskProfile(
                task_id=task.task_id,
                task_type=task_type,
                num_gpus=resources.get("num_gpus", 0),
                num_cpus=resources.get("num_cpus", 1),
                memory_gb=resources.get("memory_gb", 0.0),
                priority=priority,
                preferred_nodes=preferred_nodes,
                data_locality=data_locality,
                estimated_duration_minutes=estimated_duration,
                is_retry=task.status == TaskStatus.RUNNING and task.result is not None,
                retry_count=0,  # Would need to track this in task
                timeout_minutes=timeout,
            )
        except Exception as e:
            raise AnalysisError(f"Failed to analyze task {task.task_id}: {e}") from e

    def get_resource_requirements(self, task: Task) -> Dict[str, Any]:
        """
        Extract resource requirements from task.

        Args:
            task: Task object

        Returns:
            dict: Resource requirements with keys num_gpus, num_cpus, memory_gb
        """
        # Start with defaults for task type
        defaults = self.DEFAULT_REQUIREMENTS.get(task.task_type, {})
        resources = defaults.copy()

        # Override with config values if present
        config = task.config or {}

        # Check for explicit GPU config
        if "num_gpus" in config:
            resources["num_gpus"] = config["num_gpus"]
        elif "gpus" in config:
            resources["num_gpus"] = config["gpus"]
        elif "gpu_count" in config:
            resources["num_gpus"] = config["gpu_count"]

        # Check for explicit CPU config
        if "num_cpus" in config:
            resources["num_cpus"] = config["num_cpus"]
        elif "cpus" in config:
            resources["num_cpus"] = config["cpus"]

        # Check for explicit memory config
        if "memory_gb" in config:
            resources["memory_gb"] = config["memory_gb"]
        elif "memory" in config:
            mem_str = str(config["memory"])
            if isinstance(config["memory"], (int, float)):
                resources["memory_gb"] = float(config["memory"])
            elif "GB" in mem_str or "Gb" in mem_str:
                resources["memory_gb"] = float(mem_str.replace("GB", "").replace("Gb", ""))
            elif "MB" in mem_str or "Mb" in mem_str:
                resources["memory_gb"] = float(mem_str.replace("MB", "").replace("Mb", "")) / 1024

        # Batch size can indicate higher resource needs
        if "batch_size" in config:
            batch_size = config["batch_size"]
            if isinstance(batch_size, int) and batch_size > 32:
                # Scale memory estimate based on batch size
                resources["memory_gb"] = resources.get("memory_gb", 4.0) * (batch_size / 32)

        # Model size can indicate GPU requirements
        if "model_size_gb" in config:
            model_size = config["model_size_gb"]
            if isinstance(model_size, (int, float)) and model_size > 1.0:
                resources["num_gpus"] = max(resources.get("num_gpus", 0), 1)

        return resources

    def _map_task_type(self, task_type: CoreTaskType) -> TaskType:
        """Map core TaskType to scheduler TaskType"""
        mapping = {
            CoreTaskType.TRAIN: TaskType.TRAIN,
            CoreTaskType.INFER: TaskType.INFER,
            CoreTaskType.VERIFY: TaskType.VERIFY,
        }
        return mapping.get(task_type, TaskType.INFER)

    def _extract_priority(self, task: Task) -> int:
        """Extract priority from task config"""
        config = task.config or {}
        for key in self.PRIORITY_KEYS:
            if key in config:
                priority = config[key]
                if isinstance(priority, int):
                    return max(1, min(10, priority))  # Clamp to 1-10
        return 5  # Default priority

    def _extract_preferred_nodes(self, task: Task) -> list:
        """Extract preferred nodes from task config"""
        config = task.config or {}
        for key in self.AFFINITY_KEYS:
            if key in config:
                value = config[key]
                if isinstance(value, str):
                    return [value]
                elif isinstance(value, list):
                    return value
        return []

    def _extract_data_locality(self, task: Task) -> str:
        """Extract data locality hint from task config"""
        config = task.config or {}
        for key in self.LOCALITY_KEYS:
            if key in config:
                return str(config[key])
        return None

    def _extract_timeout(self, task: Task) -> int:
        """Extract timeout from task config"""
        config = task.config or {}
        timeout_keys = ["timeout_minutes", "timeout", "time_limit"]
        for key in timeout_keys:
            if key in config:
                timeout = config[key]
                if isinstance(timeout, (int, float)):
                    return int(timeout)
        return 120  # Default 2 hours

    def _estimate_duration(self, task: Task, resources: Dict[str, Any]) -> int:
        """Estimate task duration in minutes"""
        config = task.config or {}

        # Check for explicit duration estimate
        if "estimated_duration_minutes" in config:
            return config["estimated_duration_minutes"]
        if "duration_minutes" in config:
            return config["duration_minutes"]

        # Base duration from resources
        base_duration = resources.get("estimated_duration_minutes", 30)

        # Adjust for batch size
        if "batch_size" in config:
            batch_size = config["batch_size"]
            if isinstance(batch_size, int):
                # Larger batches may take longer
                base_duration *= (batch_size / 32)

        # Adjust for epochs (training only)
        if task.task_type == CoreTaskType.TRAIN:
            epochs = config.get("epochs", config.get("num_epochs", 1))
            if isinstance(epochs, int):
                base_duration *= epochs

        return max(1, int(base_duration))
