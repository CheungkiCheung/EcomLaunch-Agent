"""Errors raised by the durable SubagentTask runtime."""


class SubagentTaskError(RuntimeError):
    """Base error for durable subagent task operations."""


class TaskAlreadyExistsError(SubagentTaskError):
    """Raised when a task ID is reused."""


class TaskNotFoundError(SubagentTaskError):
    """Raised when a task cannot be found."""


class TaskTransitionError(SubagentTaskError):
    """Raised when a lifecycle transition is invalid."""


class TaskVersionConflictError(SubagentTaskError):
    """Raised when optimistic concurrency detects a stale writer."""


class TaskLeaseConflictError(SubagentTaskError):
    """Raised when a worker does not own the current fencing lease."""
