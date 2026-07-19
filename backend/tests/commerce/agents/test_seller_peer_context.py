"""Deterministic SellerPeer context and tool-trace contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.commerce.agents.seller_peer import SellerPeerPathAgent
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"
TARGET_SELLER_ID = "e5a3438891c0bfdb9394643f95273d8e"


def _uploaded(tmp_path):
    evaluation_case = load_evaluation_case(CASE_ROOT)
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-storage")
    view = data_service.ingest_uploads(
        workspace_id,
        tuple(
            (Path(file.relative_path).name, (CASE_ROOT / file.relative_path).read_bytes())
            for file in evaluation_case.input_bundle.files
        ),
    )
    return data_service, workspace_id, view


@pytest.mark.anyio
async def test_seller_peer_prepare_executes_outcome_agnostic_tools_and_hashes_results(
    tmp_path,
):
    data_service, workspace_id, view = _uploaded(tmp_path)

    plan = await SellerPeerPathAgent(data_service=data_service).prepare(
        workspace_id,
        view.manifest.dataset_id,
        seller_id=TARGET_SELLER_ID,
        window=MetricWindow(
            start=datetime(2018, 1, 1), end=datetime(2018, 7, 1)
        ),
        policy=PeerCohortPolicy(
            product_category="fashion_bolsas_e_acessorios",
            min_orders_per_seller=20,
        ),
    )

    peer = plan.context.peer_comparison
    assert peer.eligibility_uses_late_delivery_result is False
    assert peer.target_order_count == 59
    assert peer.peer_seller_count == 5
    assert peer.peer_order_count == 257
    assert float(peer.target_late_delivery_rate) == pytest.approx(16 / 59)
    assert float(peer.peer_late_delivery_rate) == pytest.approx(19 / 257)
    assert float(peer.late_delivery_rate_gap) == pytest.approx(
        (16 / 59) - (19 / 257)
    )
    geography = {item.customer_state: item.order_count for item in plan.context.geography.segments}
    assert geography["SP"] == 26
    assert geography["MG"] == 8
    assert geography["RJ"] == 7
    assert plan.context.geography.total_order_count == 59
    assert tuple(item.tool_name for item in plan.tool_calls) == (
        "peer_cohort_query",
        "geographic_order_count_query",
    )
    assert all(item.status.value == "succeeded" for item in plan.tool_calls)
    assert all(item.request_sha256 != item.response_sha256 for item in plan.tool_calls)
    serialized = plan.context.model_dump_json().casefold()
    assert "expected_behavior" not in serialized
    assert "gold_label" not in serialized

