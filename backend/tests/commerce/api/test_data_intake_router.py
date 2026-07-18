"""Deterministic HTTP contracts for uploaded Commerce datasets."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.dependencies import get_commerce_data_service
from app.commerce.api.router import router
from app.commerce.domain.ids import WorkspaceId


def _app(tmp_path):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_data_service] = lambda: CommerceDataService(
        storage_root=tmp_path / "commerce-storage"
    )
    return app


@pytest.mark.anyio
async def test_upload_profile_and_capability_are_deterministic_and_workspace_scoped(tmp_path):
    app = _app(tmp_path)
    workspace_id = WorkspaceId.new()
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}
    files = [
        (
            "files",
            (
                "orders.csv",
                b"order_id,order_purchase_timestamp,order_approved_at,"
                b"order_delivered_carrier_date,order_delivered_customer_date,"
                b"order_estimated_delivery_date,seller_id\n"
                b"o1,2018-01-01,2018-01-01,2018-01-02,2018-01-05,2018-01-06,s1\n",
                "text/csv",
            ),
        ),
        (
            "files",
            (
                "reviews.csv",
                b"order_id,review_score\no1,2\n",
                "text/csv",
            ),
        ),
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        uploaded = await client.post(
            "/api/commerce/datasets/intake",
            files=files,
            headers=headers,
        )
        dataset_id = uploaded.json()["manifest"]["dataset_id"]
        profile = await client.get(
            f"/api/commerce/datasets/{dataset_id}/profile",
            headers=headers,
        )
        capabilities = await client.get(
            f"/api/commerce/datasets/{dataset_id}/capabilities",
            headers=headers,
        )
        hidden = await client.get(
            f"/api/commerce/datasets/{dataset_id}/profile",
            headers={"X-Commerce-Workspace-Id": str(WorkspaceId.new())},
        )

    assert uploaded.status_code == 201
    assert uploaded.json()["manifest"]["workspace_id"] == str(workspace_id)
    assert {table["table_name"] for table in uploaded.json()["profile"]["tables"]} == {
        "orders",
        "reviews",
    }
    assert profile.status_code == 200
    assert profile.json()["dataset_id"] == dataset_id
    assert capabilities.status_code == 200
    capability_names = {item["name"] for item in capabilities.json()["capabilities"]}
    assert "fulfillment_diagnosis" in capability_names
    assert hidden.status_code == 404


@pytest.mark.anyio
async def test_upload_rejects_path_like_filenames_before_storage(tmp_path):
    app = _app(tmp_path)
    headers = {"X-Commerce-Workspace-Id": str(WorkspaceId.new())}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/commerce/datasets/intake",
            files=[("files", ("../orders.csv", b"order_id\no1\n", "text/csv"))],
            headers=headers,
        )

    assert response.status_code == 400
    assert "filename" in json.dumps(response.json()).lower()


@pytest.mark.anyio
async def test_semantic_confirmation_is_persisted_and_changes_mapping_view(tmp_path):
    app = _app(tmp_path)
    workspace_id = WorkspaceId.new()
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}
    files = [
        (
            "files",
            (
                "orders.csv",
                b"order_id,status\no1,delivered\n",
                "text/csv",
            ),
        )
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        uploaded = await client.post(
            "/api/commerce/datasets/intake",
            files=files,
            headers=headers,
        )
        dataset_id = uploaded.json()["manifest"]["dataset_id"]
        confirmed = await client.post(
            f"/api/commerce/datasets/{dataset_id}/semantic-confirmations",
            json={
                "table_name": "orders",
                "column_name": "status",
                "semantic_field": "order.status",
            },
            headers=headers,
        )
        mappings = await client.get(
            f"/api/commerce/datasets/{dataset_id}/mappings",
            headers=headers,
        )
        invalid_column = await client.post(
            f"/api/commerce/datasets/{dataset_id}/semantic-confirmations",
            json={
                "table_name": "orders",
                "column_name": "missing",
                "semantic_field": "order.status",
            },
            headers=headers,
        )
        hidden = await client.post(
            f"/api/commerce/datasets/{dataset_id}/semantic-confirmations",
            json={
                "table_name": "orders",
                "column_name": "status",
                "semantic_field": "order.status",
            },
            headers={"X-Commerce-Workspace-Id": str(WorkspaceId.new())},
        )

    assert uploaded.status_code == 201
    assert confirmed.status_code == 201
    assert confirmed.json()["semantic_field"] == "order.status"
    assert mappings.status_code == 200
    status_mapping = next(
        item for item in mappings.json()["mappings"] if item["column_name"] == "status"
    )
    assert status_mapping["status"] == "confirmed"
    assert status_mapping["source"] == "user_confirmed"
    assert invalid_column.status_code == 400
    assert hidden.status_code == 404
