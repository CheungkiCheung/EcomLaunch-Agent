"""HTTP and streaming adapters for Commerce Case Agent.

Keep package import side-effect free so persistence and Agent contracts can
import focused API service modules without constructing the entire FastAPI
router graph.  ``router`` remains available as a lazy compatibility export.
"""

from typing import Any

__all__ = ["router"]


def __getattr__(name: str) -> Any:
    if name != "router":
        raise AttributeError(name)
    from app.commerce.api.router import router

    return router
