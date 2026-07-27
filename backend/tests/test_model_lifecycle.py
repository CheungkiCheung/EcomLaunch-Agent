"""Deterministic model client lifecycle contracts."""

from __future__ import annotations

import pytest

from deerflow.models.lifecycle import aclose_model_clients, close_model_clients


class _AsyncRoot:
    def __init__(self) -> None:
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


class _SyncRoot:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class _Model:
    def __init__(self) -> None:
        self.root_async_client = _AsyncRoot()
        self.root_client = _SyncRoot()


@pytest.mark.anyio
async def test_aclose_model_clients_closes_async_and_sync_roots_once():
    model = _Model()

    await aclose_model_clients(model)
    await aclose_model_clients(model)

    assert model.root_async_client.close_calls == 1
    assert model.root_client.close_calls == 1


def test_close_model_clients_closes_sync_call_path_roots_once():
    model = _Model()

    close_model_clients(model)
    close_model_clients(model)

    assert model.root_async_client.close_calls == 1
    assert model.root_client.close_calls == 1
