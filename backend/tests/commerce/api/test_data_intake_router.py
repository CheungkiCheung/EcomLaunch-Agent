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
    app.dependency_overrides[get_commerce_data_service] = lambda: CommerceDataService(storage_root=tmp_path / "commerce-storage")
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
                b"order_id,order_purchase_timestamp,order_approved_at,order_delivered_carrier_date,order_delivered_customer_date,order_estimated_delivery_date,seller_id\no1,2018-01-01,2018-01-01,2018-01-02,2018-01-05,2018-01-06,s1\n",
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
    status_mapping = next(item for item in mappings.json()["mappings"] if item["column_name"] == "status")
    assert status_mapping["status"] == "confirmed"
    assert status_mapping["source"] == "user_confirmed"
    assert invalid_column.status_code == 400
    assert hidden.status_code == 404


@pytest.mark.anyio
async def test_mapping_confirmation_resume_is_batch_atomic_idempotent_and_refreshes_capabilities(
    tmp_path,
):
    app = _app(tmp_path)
    workspace_id = WorkspaceId.new()
    headers = {
        "X-Commerce-Workspace-Id": str(workspace_id),
        "X-Commerce-Actor-Id": "data-reviewer-a",
    }
    files = [
        (
            "files",
            (
                "orders.csv",
                b"id,purchased_at,approved_at,carrier_handoff_at,delivered_at,estimated_delivery_at\no1,2018-01-01,2018-01-01,2018-01-02,2018-01-05,2018-01-06\n",
                "text/csv",
            ),
        ),
        (
            "files",
            (
                "order_items.csv",
                b"order_id,seller_id\no1,s1\n",
                "text/csv",
            ),
        ),
    ]
    body = {
        "confirmations": [
            {
                "table_name": "orders",
                "column_name": "id",
                "semantic_field": "order.id",
            }
        ],
        "idempotency_key": "mapping-resume-001",
    }

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
        invalid_batch = await client.post(
            f"/api/commerce/datasets/{dataset_id}/mapping-resume",
            headers=headers,
            json={
                "confirmations": [
                    body["confirmations"][0],
                    {
                        "table_name": "orders",
                        "column_name": "missing",
                        "semantic_field": "order.status",
                    },
                ],
                "idempotency_key": "mapping-resume-invalid-001",
            },
        )
        after_invalid = await client.get(
            f"/api/commerce/datasets/{dataset_id}/mappings",
            headers=headers,
        )
        resumed = await client.post(
            f"/api/commerce/datasets/{dataset_id}/mapping-resume",
            headers=headers,
            json=body,
        )
        replayed = await client.post(
            f"/api/commerce/datasets/{dataset_id}/mapping-resume",
            headers=headers,
            json=body,
        )
        conflict = await client.post(
            f"/api/commerce/datasets/{dataset_id}/mapping-resume",
            headers=headers,
            json={
                **body,
                "confirmations": [
                    {
                        "table_name": "orders",
                        "column_name": "id",
                        "semantic_field": "review.order_id",
                    }
                ],
            },
        )

    assert uploaded.status_code == 201
    before = next(item for item in uploaded.json()["capabilities"]["capabilities"] if item["name"] == "fulfillment_diagnosis")
    assert before["status"] == "unavailable"
    assert invalid_batch.status_code == 400
    still_unconfirmed = next(item for item in after_invalid.json()["mappings"] if item["table_name"] == "orders" and item["column_name"] == "id")
    assert still_unconfirmed["status"] == "needs_confirmation"
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["created"] is True
    assert resumed.json()["replayed"] is False
    assert resumed.json()["confirmations"][0]["confirmed_by"] == "data-reviewer-a"
    confirmed = next(item for item in resumed.json()["mappings"]["mappings"] if item["table_name"] == "orders" and item["column_name"] == "id")
    assert confirmed["status"] == "confirmed"
    assert confirmed["source"] == "user_confirmed"
    fulfillment = next(item for item in resumed.json()["capabilities"]["capabilities"] if item["name"] == "fulfillment_diagnosis")
    assert fulfillment["status"] == "partial"
    assert replayed.status_code == 200
    assert replayed.json() == {
        **resumed.json(),
        "created": False,
        "replayed": True,
    }
    assert conflict.status_code == 409
    assert "idempotency" in conflict.json()["detail"].lower()


@pytest.mark.anyio
async def test_dataset_list_and_detail_are_workspace_scoped_and_resumable(tmp_path):
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
        first = await client.post("/api/commerce/datasets/intake", files=files, headers=headers)
        second = await client.post("/api/commerce/datasets/intake", files=files, headers=headers)
        first_id = first.json()["manifest"]["dataset_id"]
        second_id = second.json()["manifest"]["dataset_id"]
        listed = await client.get("/api/commerce/datasets?limit=1&offset=0", headers=headers)
        detail = await client.get(f"/api/commerce/datasets/{first_id}", headers=headers)
        other_workspace = await client.get(
            "/api/commerce/datasets",
            headers={"X-Commerce-Workspace-Id": str(WorkspaceId.new())},
        )
        invalid_id = await client.get("/api/commerce/datasets/not-a-dataset", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert listed.status_code == 200
    assert listed.json()["limit"] == 1
    assert listed.json()["offset"] == 0
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["dataset_id"] in {first_id, second_id}
    assert listed.json()["items"][0]["workspace_id"] == str(workspace_id)
    assert listed.json()["items"][0]["integrity_status"] == "verified"
    assert listed.json()["items"][0]["checks"]["file_count"] == 1
    assert listed.json()["items"][0]["checks"]["table_count"] == 1
    assert listed.json()["items"][0]["checks"]["row_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["manifest"]["dataset_id"] == first_id
    assert detail.json()["profile"]["dataset_id"] == first_id
    assert detail.json()["integrity_status"] == "verified"
    assert detail.json()["confirmations"] == []
    assert other_workspace.status_code == 200
    assert other_workspace.json()["items"] == []
    assert invalid_id.status_code == 400


@pytest.mark.anyio
async def test_dataset_read_fails_closed_when_manifest_or_source_file_is_corrupt(tmp_path):
    app = _app(tmp_path)
    workspace_id = WorkspaceId.new()
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}
    files = [("files", ("orders.csv", b"order_id\no1\n", "text/csv"))]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        uploaded = await client.post("/api/commerce/datasets/intake", files=files, headers=headers)
        dataset_id = uploaded.json()["manifest"]["dataset_id"]
        storage_root = tmp_path / "commerce-storage"
        manifest_path = storage_root / str(workspace_id) / dataset_id / "manifest.json"
        manifest_path.chmod(0o644)
        manifest_path.write_text("{not-json", encoding="utf-8")
        corrupt_manifest = await client.get(f"/api/commerce/datasets/{dataset_id}", headers=headers)

        uploaded_again = await client.post(
            "/api/commerce/datasets/intake",
            files=files,
            headers=headers,
        )
        source_dataset_id = uploaded_again.json()["manifest"]["dataset_id"]
        source_manifest = json.loads((storage_root / str(workspace_id) / source_dataset_id / "manifest.json").read_text(encoding="utf-8"))
        source_path = storage_root / str(workspace_id) / source_dataset_id / source_manifest["files"][0]["stored_relative_path"]
        source_path.chmod(0o644)
        source_path.write_text("order_id\nchanged\n", encoding="utf-8")
        source_path.chmod(0o444)
        corrupt_source = await client.get(
            f"/api/commerce/datasets/{source_dataset_id}",
            headers=headers,
        )
        corrupt_list = await client.get("/api/commerce/datasets", headers=headers)

    assert uploaded.status_code == 201
    assert corrupt_manifest.status_code == 409
    assert "manifest" in corrupt_manifest.json()["detail"].lower()
    assert corrupt_source.status_code == 409
    assert any(token in corrupt_source.json()["detail"].lower() for token in ("hash", "size", "writable", "missing"))
    assert corrupt_list.status_code == 409


@pytest.mark.anyio
async def test_semantic_confirmations_are_scoped_to_the_dataset_not_the_workspace(tmp_path):
    app = _app(tmp_path)
    workspace_id = WorkspaceId.new()
    headers = {"X-Commerce-Workspace-Id": str(workspace_id)}
    files = [("files", ("orders.csv", b"id,created\no1,2026-07-20\n", "text/csv"))]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first = await client.post("/api/commerce/datasets/intake", files=files, headers=headers)
        second = await client.post("/api/commerce/datasets/intake", files=files, headers=headers)
        first_id = first.json()["manifest"]["dataset_id"]
        second_id = second.json()["manifest"]["dataset_id"]
        confirmed = await client.post(
            f"/api/commerce/datasets/{first_id}/semantic-confirmations",
            headers=headers,
            json={
                "table_name": "orders",
                "column_name": "id",
                "semantic_field": "order.id",
            },
        )
        first_mapping = await client.get(
            f"/api/commerce/datasets/{first_id}/mappings",
            headers=headers,
        )
        second_mapping = await client.get(
            f"/api/commerce/datasets/{second_id}/mappings",
            headers=headers,
        )

    assert confirmed.status_code == 201
    first_status = next(item for item in first_mapping.json()["mappings"] if item["column_name"] == "id")
    second_status = next(item for item in second_mapping.json()["mappings"] if item["column_name"] == "id")
    assert first_status["status"] == "confirmed"
    assert second_status["status"] == "needs_confirmation"
