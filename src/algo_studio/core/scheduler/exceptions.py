"""
Scheduler exceptions
"""


class SchedulingError(Exception):
    """Base exception for scheduling errors"""
    pass


class NoAvailableNodeError(SchedulingError):
    """Raised when no available node can be found for a task"""
    pass


class ValidationError(SchedulingError):
    """Raised when a scheduling decision fails validation"""
    pass


class AnalysisError(Exception):
    """Raised when task analysis fails"""
    pass


class LLMError(Exception):
    """Raised when LLM call fails"""
    pass
