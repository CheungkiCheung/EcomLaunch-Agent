"""Action proposal, policy, Approval, and workspace HTTP contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.actions.contracts import ExternalOperation
from app.commerce.actions.execution import ActionExecutionService
from app.commerce.actions.policy import ActionPolicyGate, ConnectorPolicy
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    CaseAnalysisDigest,
    CaseHeader,
    ContextManifest,
    EvidenceDigest,
    HypothesisDigest,
    LeadContextPacket,
    MetricObservationDigest,
)
from app.commerce.api.action_service import CommerceActionService
from app.commerce.api.dependencies import (
    get_commerce_action_execution_service,
    get_commerce_action_service,
)
from app.commerce.api.router import router
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.domain.enums import (
    CaseSeverity,
    CaseStatus,
    SemanticStatus,
)
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    DatasetId,
    EntityId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import Case
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.events import SqlDomainEventStore
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


def _context() -> LeadContextPacket:
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    dataset_id = DatasetId.new()
    evidence_id = EvidenceId.new()
    hypothesis_id = HypothesisId.new()
    baseline_id = MetricObservationId.new()
    current_id = MetricObservationId.new()
    baseline_window = MetricWindow(
        start=datetime(2026, 1, 1),
        end=datetime(2026, 2, 1),
    )
    current_window = MetricWindow(
        start=datetime(2026, 2, 1),
        end=datetime(2026, 3, 1),
    )
    common = {
        "metric_name": "late_delivery_rate",
        "semantic_status": SemanticStatus.DERIVED,
        "unit": "ratio",
        "formula_version": "late_delivery_rate@1.0.0",
        "sample_size": 100,
        "source_fact_count": 100,
    }
    return LeadContextPacket(
        case=CaseHeader(
            workspace_id=workspace_id,
            case_id=case_id,
            title="Late-delivery anomaly",
            severity=CaseSeverity.HIGH,
            status=CaseStatus.INVESTIGATING,
            version=1,
        ),
        goal="Turn verified evidence into a bounded operation",
        manifest=ContextManifest(
            context_version="commerce-context@1.0.0",
            workspace_id=workspace_id,
            case_id=case_id,
            dataset_id=dataset_id,
            source_artifact_sha256="a" * 64,
            context_sha256="b" * 64,
            estimated_tokens=1_000,
            included_evidence_ids=(evidence_id,),
            included_metric_observation_ids=(baseline_id, current_id),
        ),
        budget=AgentBudgetLimit(),
        capabilities=frozenset(),
        capability_profile=CapabilityProfile(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            capabilities=(),
        ),
        analysis=CaseAnalysisDigest(
            dataset_id=dataset_id,
            seller_entity_id=EntityId.new(),
            seller_external_key="seller-a",
            baseline_window=baseline_window,
            current_window=current_window,
            baseline_metrics=(
                MetricObservationDigest(
                    metric_observation_id=baseline_id,
                    value=Decimal("0.10"),
                    numerator=10,
                    denominator=100,
                    window_start=baseline_window.start,
                    window_end=baseline_window.end,
                    **common,
                ),
            ),
            current_metrics=(
                MetricObservationDigest(
                    metric_observation_id=current_id,
                    value=Decimal("0.30"),
                    numerator=30,
                    denominator=100,
                    window_start=current_window.start,
                    window_end=current_window.end,
                    **common,
                ),
            ),
        ),
        evidence=(
            EvidenceDigest(
                evidence_id=evidence_id,
                summary="Late-delivery rate is elevated in the current window",
                semantic_status=SemanticStatus.DERIVED,
                confidence=0.95,
                metric_observation_ids=(baseline_id, current_id),
            ),
        ),
        hypotheses=(
            HypothesisDigest(
                hypothesis_id=hypothesis_id,
                statement="The current late-delivery rate requires monitoring",
                status="supported",
                confidence=0.9,
                evidence_ids=(evidence_id,),
            ),
        ),
    )


class _RefreshingContextLoader:
    def __init__(self, factory, packet: LeadContextPacket) -> None:
        self._cases = SqlCaseRepository(factory)
        self._packet = packet

    async def load_case_packet(
        self,
        workspace_id,
        case_id,
        *,
        goal,
        budget,
    ) -> LeadContextPacket:
        del goal, budget
        case = await self._cases.get(workspace_id, case_id)
        assert case is not None
        return self._packet.model_copy(
            update={
                "case": self._packet.case.model_copy(
                    update={
                        "version": case.version,
                        "status": case.status,
                    }
                )
            }
        )


async def _app(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commerce-action-api.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    packet = _context()
    case = Case(
        id=packet.case.case_id,
        workspace_id=packet.case.workspace_id,
        title=packet.case.title,
        severity=packet.case.severity,
        status=packet.case.status,
        evidence_ids=tuple(item.evidence_id for item in packet.evidence),
        hypothesis_ids=tuple(item.hypothesis_id for item in packet.hypotheses),
        opened_at=datetime(2026, 7, 19, 14, 0),
        updated_at=datetime(2026, 7, 19, 14, 0),
        version=packet.case.version,
    )
    await SqlCommerceUnitOfWork(factory).create_case(
        case,
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
        actor=DomainEventActor.SYSTEM,
    )
    service = CommerceActionService(
        factory,
        context_loader=_RefreshingContextLoader(factory, packet),
        policy_gate=ActionPolicyGate(connector_policy=ConnectorPolicy(allowed_operations={"merchant_ads": frozenset({ExternalOperation.UPDATE_CAMPAIGN_BUDGET})})),
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_action_service] = lambda: service
    app.dependency_overrides[get_commerce_action_execution_service] = lambda: ActionExecutionService(factory, storage_root=tmp_path / "action-artifacts")
    return app, engine, factory, packet


def _headers(workspace_id: WorkspaceId, actor: str = "operator-a") -> dict[str, str]:
    return {
        "X-Commerce-Workspace-Id": str(workspace_id),
        "X-Commerce-Actor-Id": actor,
    }


def _monitor_body(packet: LeadContextPacket, *, key: str, title: str | None = None):
    evidence_id = packet.evidence[0].evidence_id
    hypothesis_id = packet.hypotheses[0].hypothesis_id
    current_id = packet.analysis.current_metrics[0].metric_observation_id
    return {
        "idempotency_key": key,
        "title": title or "Monitor late-delivery recovery",
        "description": "Create a reversible internal metric monitor.",
        "evidence_ids": [str(evidence_id)],
        "hypothesis_ids": [str(hypothesis_id)],
        "expected_signal_metric_ids": [str(current_id)],
        "parameters": {
            "kind": "create_metric_monitor",
            "metric_name": "late_delivery_rate",
            "metric_observation_ids": [str(current_id)],
            "comparison": "less_than_or_equal",
            "threshold": "0.15",
            "cadence_hours": 24,
            "follow_up_after_days": 7,
        },
        "rollback_plan": {
            "strategy": "Disable the internal monitor",
            "trigger": "The metric contract or seller scope changes",
            "verification": "Confirm no active monitor remains for this Action",
        },
    }


def _external_body(packet: LeadContextPacket, *, key: str):
    body = _monitor_body(packet, key=key)
    body.update(
        {
            "title": "Reduce campaign budget",
            "description": "Apply a reversible external budget adjustment.",
            "parameters": {
                "kind": "external_mutation",
                "connector_id": "merchant_ads",
                "operation": "update_campaign_budget",
                "target_ref_sha256": "c" * 64,
                "reversible": True,
                "dry_run": False,
            },
            "rollback_plan": {
                "strategy": "Restore the prior campaign budget snapshot",
                "trigger": "Approval is revoked or a guardrail fires",
                "verification": "Read back the prior connector value",
            },
        }
    )
    return body


@pytest.mark.anyio
async def test_action_proposal_is_server_identified_idempotent_and_workspace_scoped(
    tmp_path,
):
    app, engine, factory, packet = await _app(tmp_path)
    headers = _headers(packet.case.workspace_id)
    body = _monitor_body(packet, key="monitor-action-001")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first = await client.post(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=headers,
            json=body,
        )
        replay = await client.post(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=headers,
            json=body,
        )
        action_id = first.json()["record"]["action"]["id"]
        detail = await client.get(
            f"/api/commerce/actions/{action_id}",
            headers=headers,
        )
        listed = await client.get(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=headers,
        )
        hidden = await client.get(
            f"/api/commerce/actions/{action_id}",
            headers=_headers(WorkspaceId.new()),
        )
        conflict_body = _monitor_body(
            packet,
            key="monitor-action-001",
            title="A different action under the same key",
        )
        conflict = await client.post(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=headers,
            json=conflict_body,
        )

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert first.json()["record"]["decision"]["level"] == "L2"
    assert first.json()["record"]["action"]["status"] == "policy_checked"
    assert replay.status_code == 201
    assert replay.json()["created"] is False
    assert replay.json()["record"]["action"]["id"] == action_id
    assert detail.status_code == 200
    assert detail.json()["record"]["action"]["id"] == action_id
    assert detail.json()["approval"] is None
    assert listed.status_code == 200
    assert [item["action"]["id"] for item in listed.json()["items"]] == [action_id]
    assert hidden.status_code == 404
    assert conflict.status_code == 409
    assert "idempotency" in conflict.json()["detail"].lower()
    events = await SqlDomainEventStore(factory).list_case(
        packet.case.workspace_id,
        packet.case.case_id,
    )
    created_event = next(event for event in events if event.event_type == "action.created")
    assert created_event.actor is DomainEventActor.USER
    assert created_event.payload["actor_id"] == "operator-a"
    await engine.dispose()


@pytest.mark.anyio
async def test_l4_action_requires_two_distinct_http_approvals_and_replays_safely(
    tmp_path,
):
    app, engine, _factory, packet = await _app(tmp_path)
    body = _external_body(packet, key="external-action-001")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        proposed = await client.post(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=_headers(packet.case.workspace_id),
            json=body,
        )
        action_id = proposed.json()["record"]["action"]["id"]
        approval = await client.get(
            f"/api/commerce/actions/{action_id}/approval",
            headers=_headers(packet.case.workspace_id),
        )
        first = await client.post(
            f"/api/commerce/actions/{action_id}/approvals/approve",
            headers=_headers(packet.case.workspace_id, "operator-a"),
            json={"idempotency_key": "approval-operator-a"},
        )
        replay = await client.post(
            f"/api/commerce/actions/{action_id}/approvals/approve",
            headers=_headers(packet.case.workspace_id, "operator-a"),
            json={"idempotency_key": "approval-operator-a"},
        )
        duplicate_actor = await client.post(
            f"/api/commerce/actions/{action_id}/approvals/approve",
            headers=_headers(packet.case.workspace_id, "operator-a"),
            json={"idempotency_key": "approval-operator-a-second-key"},
        )
        second = await client.post(
            f"/api/commerce/actions/{action_id}/approvals/approve",
            headers=_headers(packet.case.workspace_id, "operator-b"),
            json={"idempotency_key": "approval-operator-b"},
        )

    assert proposed.status_code == 201
    assert proposed.json()["record"]["decision"]["level"] == "L4"
    assert proposed.json()["record"]["action"]["status"] == "awaiting_approval"
    assert approval.status_code == 200
    assert approval.json()["required_approvals"] == 2
    assert first.status_code == 200
    assert first.json()["approval"]["status"] == "pending"
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert duplicate_actor.status_code == 409
    assert second.status_code == 200
    assert second.json()["approval"]["status"] == "approved"
    assert second.json()["record"]["action"]["status"] == "approved"
    await engine.dispose()


@pytest.mark.anyio
async def test_reject_and_modify_end_the_old_action_and_require_actor_header(tmp_path):
    app, engine, _factory, packet = await _app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        rejected_proposal = await client.post(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=_headers(packet.case.workspace_id),
            json=_external_body(packet, key="external-reject-001"),
        )
        rejected_id = rejected_proposal.json()["record"]["action"]["id"]
        rejected = await client.post(
            f"/api/commerce/actions/{rejected_id}/approvals/reject",
            headers=_headers(packet.case.workspace_id, "risk-reviewer"),
            json={
                "idempotency_key": "reject-decision-001",
                "reason": "Guardrail evidence is insufficient",
            },
        )

        modified_proposal = await client.post(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=_headers(packet.case.workspace_id),
            json=_external_body(packet, key="external-modify-001"),
        )
        modified_id = modified_proposal.json()["record"]["action"]["id"]
        replacement = _external_body(packet, key="replacement-action-001")
        replacement.pop("idempotency_key")
        replacement["title"] = "Dry-run the campaign budget change"
        replacement["parameters"]["dry_run"] = True
        modified = await client.post(
            f"/api/commerce/actions/{modified_id}/approvals/modify",
            headers=_headers(packet.case.workspace_id, "risk-reviewer"),
            json={
                "idempotency_key": "modify-decision-001",
                "replacement_idempotency_key": "replacement-action-001",
                "reason": "Require a dry-run before any write",
                "replacement": replacement,
            },
        )
        missing_actor = await client.post(
            f"/api/commerce/actions/{modified_id}/approvals/approve",
            headers={
                "X-Commerce-Workspace-Id": str(packet.case.workspace_id),
            },
            json={"idempotency_key": "missing-actor-001"},
        )

    assert rejected.status_code == 200
    assert rejected.json()["approval"]["status"] == "rejected"
    assert rejected.json()["record"]["action"]["status"] == "rejected"
    assert modified.status_code == 200
    assert modified.json()["approval"]["status"] == "revoked"
    assert modified.json()["record"]["action"]["status"] == "rejected"
    replacement_draft = modified.json()["command"]["replacement_draft"]
    assert replacement_draft["parameters"]["dry_run"] is True
    assert replacement_draft["id"].startswith("act_")
    assert missing_actor.status_code == 422
    await engine.dispose()


@pytest.mark.anyio
async def test_internal_action_execution_and_rollback_are_visible_in_action_detail(
    tmp_path,
):
    app, engine, _factory, packet = await _app(tmp_path)
    headers = _headers(packet.case.workspace_id)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        proposed = await client.post(
            f"/api/commerce/cases/{packet.case.case_id}/actions",
            headers=headers,
            json=_monitor_body(packet, key="monitor-execution-001"),
        )
        action_id = proposed.json()["record"]["action"]["id"]
        executed = await client.post(
            f"/api/commerce/actions/{action_id}/executions",
            headers=headers,
            json={
                "operation": "execute",
                "idempotency_key": "execute-monitor-api-001",
            },
        )
        detail = await client.get(
            f"/api/commerce/actions/{action_id}",
            headers=headers,
        )
        rolled_back = await client.post(
            f"/api/commerce/actions/{action_id}/executions",
            headers=headers,
            json={
                "operation": "rollback",
                "idempotency_key": "rollback-monitor-api-001",
            },
        )
        rollback_replay = await client.post(
            f"/api/commerce/actions/{action_id}/executions",
            headers=headers,
            json={
                "operation": "rollback",
                "idempotency_key": "rollback-monitor-api-001",
            },
        )

    assert executed.status_code == 201
    assert executed.json()["created"] is True
    assert executed.json()["run"]["run_type"] == "action_execution"
    assert executed.json()["run"]["action_operation"] == "execute"
    assert executed.json()["run"]["status"] == "completed"
    assert executed.json()["record"]["action"]["status"] == "monitoring"
    assert executed.json()["artifact"]["status"] == "active"
    assert detail.status_code == 200
    assert detail.json()["artifact"]["status"] == "active"
    assert rolled_back.status_code == 201
    assert rolled_back.json()["record"]["action"]["status"] == "rolled_back"
    assert rolled_back.json()["artifact"]["status"] == "disabled"
    assert rollback_replay.status_code == 201
    assert rollback_replay.json()["created"] is False
    assert rollback_replay.json()["replayed"] is True
    await engine.dispose()
