"""Fresh real DeepSeek V4 behavior gate for SellerPeerPathAgent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.commerce.agents.claim_policy import unsupported_causal_phrases
from app.commerce.agents.seller_peer import (
    SellerPeerAuditStore,
    SellerPeerPathAgent,
)
from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import WorkspaceId
from app.commerce.metrics.registry import MetricWindow, PeerCohortPolicy

REPO_ROOT = Path(__file__).parents[4]
CASE_ROOT = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-PEER-004"
TARGET_SELLER_ID = "e5a3438891c0bfdb9394643f95273d8e"


@pytest.mark.real_model
@pytest.mark.anyio
async def test_real_seller_peer_agent_explains_gap_geography_and_boundaries(tmp_path):
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
    agent = SellerPeerPathAgent(
        data_service=data_service,
        audit_store=SellerPeerAuditStore(
            REPO_ROOT / ".deer-flow/commerce/evaluation/path-agents"
        ),
    )
    plan = await agent.prepare(
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
    run = await agent.run_prepared(plan)

    assert run.telemetry.actual_model_identity is not None
    assert run.telemetry.actual_model_identity.startswith("deepseek-v4")
    assert run.telemetry.provider_request_id
    assert run.telemetry.token_usage is not None
    assert run.telemetry.request_attempt_count == 1
    assert run.telemetry.retry_count == 0
    assert Path(run.audit_path).is_file()
    assert tuple(item.tool_name for item in run.result.tool_calls) == (
        "peer_cohort_query",
        "geographic_order_count_query",
    )
    assert run.result.cost.tool_call_count == 2

    peer = run.context.peer_comparison
    peer_ids = {
        peer.target_rate_observation_id,
        peer.peer_rate_observation_id,
    }
    assert any(
        peer_ids.issubset(set(item.metric_observation_ids))
        for item in run.result.observations
    )
    rendered = run.result.model_dump_json().casefold()
    assert "target" in rendered
    assert "peer" in rendered
    assert "gap" in rendered
    assert any(term in rendered for term in ("27.1", "27.12", "0.271"))
    assert any(term in rendered for term in ("7.39", "7.4", "0.0739"))
    assert any(term in rendered for term in ("19.7", "19.72", "0.197"))
    assert "257" in rendered
    assert "5 peer" in rendered or "five peer" in rendered

    top_geography_ids = {
        plan.context.geography.segment(state).metric_observation_id
        for state in ("SP", "MG", "RJ")
    }
    assert top_geography_ids.issubset(
        {
            metric_id
            for item in run.result.observations
            for metric_id in item.metric_observation_ids
        }
    )
    assert all(term in rendered for term in ("sp", "mg", "rj", "26", "8", "7"))
    assert not any(
        unsupported_causal_phrases(item.summary)
        for item in run.result.observations
    )
    assert "diagnostic" in rendered
    assert "causal" in rendered or "causality" in rendered
    assert not any(
        term in rendered
        for term in (
            "confirmed roi",
            "verified uplift",
            "真实gmv",
            "实际转化率",
            "广告roi已提升",
        )
    )

    hidden = evaluation_case.expected_behavior
    required_facts = {item.name: item for item in hidden.required_facts}
    assert required_facts["peer.target_order_count"].expected_value == 59
    assert required_facts["peer.peer_seller_count"].expected_value == 5
    assert "expected_behavior" not in plan.context.model_dump_json().casefold()
