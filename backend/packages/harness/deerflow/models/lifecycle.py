"""Explicit lifecycle helpers for provider-owned sync and async clients."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable
from typing import Any

_CLOSED_MARKER = "_deerflow_model_client_closed"


def _owned_clients(model: Any) -> tuple[Any, ...]:
    clients: list[Any] = []
    seen: set[int] = set()
    for attribute in ("root_async_client", "root_client"):
        client = getattr(model, attribute, None)
        if client is None or id(client) in seen:
            continue
        seen.add(id(client))
        clients.append(client)
    return tuple(clients)


def _is_closed(client: Any) -> bool:
    if bool(getattr(client, _CLOSED_MARKER, False)):
        return True
    is_closed = getattr(client, "is_closed", None)
    return bool(is_closed()) if callable(is_closed) else False


def _mark_closed(client: Any) -> None:
    try:
        setattr(client, _CLOSED_MARKER, True)
    except (AttributeError, TypeError):
        pass


async def _await_close(result: Awaitable[Any]) -> None:
    await result


async def aclose_model_clients(model: Any) -> None:
    """Close provider clients on the event loop that executed the model."""

    for client in _owned_clients(model):
        if _is_closed(client):
            continue
        close = getattr(client, "close", None)
        if not callable(close):
            continue
        result = close()
        if inspect.isawaitable(result):
            await result
        _mark_closed(client)


def close_model_clients(model: Any) -> None:
    """Close provider clients for synchronous model invocation paths."""

    for client in _owned_clients(model):
        if _is_closed(client):
            continue
        close = getattr(client, "close", None)
        if not callable(close):
            continue
        result = close()
        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_await_close(result))
            else:
                result.close() if inspect.iscoroutine(result) else None
                raise RuntimeError(
                    "Synchronous model cleanup cannot await inside a running event "
                    "loop; use aclose_model_clients"
                )
        _mark_closed(client)
