"""Commerce Agent application layer.

Import concrete contracts from their focused modules.  This package initializer
is intentionally side-effect free: persistence owns serialized checkpoints and
must be able to import ``agents.goal_loop`` without recursively constructing
Context loaders, API routers, model clients, or Subagent runtimes.
"""

__all__: list[str] = []
