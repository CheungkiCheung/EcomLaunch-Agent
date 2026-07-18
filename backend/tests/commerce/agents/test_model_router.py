"""Deterministic model-profile routing and assignment-event contracts."""

from __future__ import annotations

import pytest

from app.commerce.agents.budget import (
    BudgetDelta,
    BudgetDimension,
    BudgetExceededError,
    BudgetManager,
)
from app.commerce.agents.contracts import AgentBudgetLimit, ModelProfile
from app.commerce.agents.model_router import (
    ModelCapabilityError,
    ModelEffort,
    ModelRole,
    ModelRouter,
    ModelRouteReasonCode,
    ModelRouteRequest,
    OutputSchemaComplexity,
    build_model_assignment_event,
)
from app.commerce.domain.enums import CaseSeverity
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)


@pytest.mark.anyio
async def test_verifier_role_is_bound_to_strong_verifier_profile_and_event():
    manager = BudgetManager(AgentBudgetLimit())
    assignment = await ModelRouter().assign(
        ModelRouteRequest(
            role=ModelRole.VERIFIER,
            base_profile=ModelProfile.BALANCED_TOOL_USER,
        ),
        manager,
    )

    assert assignment.profile is ModelProfile.STRONG_VERIFIER
    assert assignment.model_alias == "deepseek-reasoner"
    assert assignment.effort is ModelEffort.HIGH
    assert ModelRouteReasonCode.ROLE_VERIFIER in assignment.reason_codes
    assert assignment.escalation_count == 0

    event = build_model_assignment_event(
        assignment,
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        run_id=RunId.new(),
        trace_id=TraceId.new(),
        correlation_id=CorrelationId.new(),
    )
    assert event.event_type == "model.assigned"
    assert event.payload["profile"] == "strong_verifier"
    assert event.payload["router_version"] == "commerce-model-router@1.0.0"


@pytest.mark.anyio
async def test_high_risk_lead_upgrade_consumes_escalation_budget_once():
    manager = BudgetManager(
        AgentBudgetLimit(max_model_escalations=1, max_tokens=20_000)
    )
    router = ModelRouter()
    request = ModelRouteRequest(
        role=ModelRole.LEAD,
        base_profile=ModelProfile.BALANCED_TOOL_USER,
        case_severity=CaseSeverity.CRITICAL,
        contradiction_count=3,
        evidence_path_count=3,
        schema_complexity=OutputSchemaComplexity.HIGH,
    )

    assignment = await router.assign(request, manager)

    assert assignment.profile is ModelProfile.STRONG_SYNTHESIZER
    assert assignment.escalation_count == 1
    assert manager.snapshot.usage.model_escalations == 1
    assert ModelRouteReasonCode.CRITICAL_CASE in assignment.reason_codes
    assert ModelRouteReasonCode.CONTRADICTIONS_PRESENT in assignment.reason_codes

    with pytest.raises(BudgetExceededError) as error:
        await router.assign(request, manager)

    assert error.value.dimension is BudgetDimension.MODEL_ESCALATIONS
    assert manager.snapshot.usage.model_escalations == 1


@pytest.mark.anyio
async def test_assignment_is_capped_by_remaining_token_budget_without_consuming_tokens():
    manager = BudgetManager(AgentBudgetLimit(max_tokens=1_000))
    await manager.consume(BudgetDelta(tokens=700))

    assignment = await ModelRouter().assign(
        ModelRouteRequest(
            role=ModelRole.PATH,
            base_profile=ModelProfile.BALANCED_TOOL_USER,
            needs_tool_use=True,
        ),
        manager,
    )

    assert assignment.max_output_tokens == 300
    assert ModelRouteReasonCode.TOKEN_BUDGET_CAPPED in assignment.reason_codes
    assert manager.snapshot.usage.tokens == 700


@pytest.mark.anyio
async def test_router_fails_closed_when_requested_capability_has_no_binding():
    manager = BudgetManager(AgentBudgetLimit())

    with pytest.raises(ModelCapabilityError, match="vision"):
        await ModelRouter().assign(
            ModelRouteRequest(
                role=ModelRole.PATH,
                base_profile=ModelProfile.BALANCED_TOOL_USER,
                needs_vision=True,
            ),
            manager,
        )
