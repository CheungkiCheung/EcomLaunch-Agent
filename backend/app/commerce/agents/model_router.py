"""Deterministic model-profile binding for Commerce Agent roles."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.commerce.agents.budget import (
    BudgetDelta,
    BudgetDimension,
    BudgetExceededError,
    BudgetManager,
)
from app.commerce.agents.contracts import ModelProfile
from app.commerce.domain.enums import CaseSeverity
from app.commerce.domain.events import DomainEventActor, NewDomainEvent
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    RunId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel

MODEL_ROUTER_VERSION = "commerce-model-router@1.0.0"


class ModelRole(StrEnum):
    LEAD = "lead"
    ANSWER = "answer"
    PATH = "path"
    VERIFIER = "verifier"
    STRUCTURED_REPAIR = "structured_repair"
    OFFLINE_CANDIDATE = "offline_candidate"
    ACTION_PLANNER = "action_planner"


class ModelEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutputSchemaComplexity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ModelRouteReasonCode(StrEnum):
    PROFILE_BINDING = "profile_binding"
    ROLE_READ_ONLY_ANSWER = "role_read_only_answer"
    ROLE_VERIFIER = "role_verifier"
    ROLE_STRUCTURED_REPAIR = "role_structured_repair"
    ROLE_OFFLINE_CANDIDATE = "role_offline_candidate"
    ROLE_ACTION_PLANNER = "role_action_planner"
    TOOL_USE_REQUIRED = "tool_use_required"
    CRITICAL_CASE = "critical_case"
    CONTRADICTIONS_PRESENT = "contradictions_present"
    COMPLEX_SYNTHESIS = "complex_synthesis"
    VERIFICATION_FAILURE = "verification_failure"
    PROFILE_ESCALATED = "profile_escalated"
    TOKEN_BUDGET_CAPPED = "token_budget_capped"


class ModelBinding(CommerceModel):
    profile: ModelProfile
    model_alias: str = Field(min_length=1)
    effort: ModelEffort
    max_output_tokens: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)
    supports_tool_use: bool
    supports_vision: bool


class ModelRouteRequest(CommerceModel):
    role: ModelRole
    base_profile: ModelProfile
    case_severity: CaseSeverity = CaseSeverity.MEDIUM
    capability_count: int = Field(default=0, ge=0)
    evidence_path_count: int = Field(default=0, ge=0, le=3)
    contradiction_count: int = Field(default=0, ge=0)
    schema_complexity: OutputSchemaComplexity = OutputSchemaComplexity.MEDIUM
    verification_failure_count: int = Field(default=0, ge=0)
    needs_vision: bool = False
    needs_tool_use: bool = False
    minimum_output_tokens: int = Field(default=256, ge=1)


class ModelAssignment(CommerceModel):
    schema_version: str = "1.0"
    role: ModelRole
    base_profile: ModelProfile
    profile: ModelProfile
    model_alias: str = Field(min_length=1)
    effort: ModelEffort
    max_output_tokens: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)
    reason_codes: frozenset[ModelRouteReasonCode] = Field(min_length=1)
    router_version: str = MODEL_ROUTER_VERSION
    escalation_count: int = Field(ge=0)


class ModelCapabilityError(RuntimeError):
    """Raised when no configured binding can meet a required model capability."""


_PROFILE_RANK = {
    ModelProfile.FAST_STRUCTURED: 0,
    ModelProfile.BALANCED_TOOL_USER: 1,
    ModelProfile.STRONG_SYNTHESIZER: 2,
    ModelProfile.STRONG_VERIFIER: 2,
    ModelProfile.OFFLINE_CANDIDATE_BUILDER: 2,
}


def default_model_bindings() -> tuple[ModelBinding, ...]:
    """Bind logical profiles to aliases without claiming the served model identity."""

    return (
        ModelBinding(
            profile=ModelProfile.FAST_STRUCTURED,
            model_alias="deepseek-reasoner",
            effort=ModelEffort.LOW,
            max_output_tokens=2_000,
            timeout_seconds=60,
            supports_tool_use=False,
            supports_vision=False,
        ),
        ModelBinding(
            profile=ModelProfile.BALANCED_TOOL_USER,
            model_alias="deepseek-reasoner",
            effort=ModelEffort.MEDIUM,
            max_output_tokens=4_000,
            timeout_seconds=120,
            supports_tool_use=True,
            supports_vision=False,
        ),
        ModelBinding(
            profile=ModelProfile.STRONG_SYNTHESIZER,
            model_alias="deepseek-reasoner",
            effort=ModelEffort.HIGH,
            max_output_tokens=6_000,
            timeout_seconds=180,
            supports_tool_use=True,
            supports_vision=False,
        ),
        ModelBinding(
            profile=ModelProfile.STRONG_VERIFIER,
            model_alias="deepseek-reasoner",
            effort=ModelEffort.HIGH,
            max_output_tokens=5_000,
            timeout_seconds=180,
            supports_tool_use=True,
            supports_vision=False,
        ),
        ModelBinding(
            profile=ModelProfile.OFFLINE_CANDIDATE_BUILDER,
            model_alias="deepseek-reasoner",
            effort=ModelEffort.HIGH,
            max_output_tokens=8_000,
            timeout_seconds=240,
            supports_tool_use=True,
            supports_vision=False,
        ),
    )


class ModelRouter:
    """Choose a logical model profile using auditable rules and budget gates."""

    def __init__(self, bindings: tuple[ModelBinding, ...] | None = None) -> None:
        selected_bindings = bindings or default_model_bindings()
        self._bindings = {binding.profile: binding for binding in selected_bindings}
        if len(self._bindings) != len(selected_bindings):
            raise ValueError("Model bindings must contain unique profiles")

    async def assign(
        self,
        request: ModelRouteRequest,
        budget: BudgetManager,
    ) -> ModelAssignment:
        profile, reasons, role_binding = self._select_profile(request)
        binding = self._binding(profile)
        self._require_capabilities(request, binding)

        remaining_tokens = budget.snapshot.limit.max_tokens - budget.snapshot.usage.tokens
        if remaining_tokens < request.minimum_output_tokens:
            raise BudgetExceededError(
                BudgetDimension.TOKENS,
                attempted=budget.snapshot.usage.tokens + request.minimum_output_tokens,
                limit=budget.snapshot.limit.max_tokens,
            )
        output_tokens = min(binding.max_output_tokens, remaining_tokens)
        if output_tokens < binding.max_output_tokens:
            reasons.add(ModelRouteReasonCode.TOKEN_BUDGET_CAPPED)

        is_escalation = not role_binding and profile != request.base_profile and _PROFILE_RANK[profile] > _PROFILE_RANK[request.base_profile]
        if is_escalation:
            await budget.consume(BudgetDelta(model_escalations=1))
            reasons.add(ModelRouteReasonCode.PROFILE_ESCALATED)

        return ModelAssignment(
            role=request.role,
            base_profile=request.base_profile,
            profile=profile,
            model_alias=binding.model_alias,
            effort=binding.effort,
            max_output_tokens=output_tokens,
            timeout_seconds=binding.timeout_seconds,
            reason_codes=frozenset(reasons),
            escalation_count=budget.snapshot.usage.model_escalations,
        )

    def _select_profile(
        self,
        request: ModelRouteRequest,
    ) -> tuple[ModelProfile, set[ModelRouteReasonCode], bool]:
        reasons = {ModelRouteReasonCode.PROFILE_BINDING}
        if request.role is ModelRole.VERIFIER:
            reasons.add(ModelRouteReasonCode.ROLE_VERIFIER)
            return ModelProfile.STRONG_VERIFIER, reasons, True
        if request.role is ModelRole.ANSWER:
            reasons.add(ModelRouteReasonCode.ROLE_READ_ONLY_ANSWER)
            return ModelProfile.FAST_STRUCTURED, reasons, True
        if request.role is ModelRole.STRUCTURED_REPAIR:
            reasons.add(ModelRouteReasonCode.ROLE_STRUCTURED_REPAIR)
            return ModelProfile.FAST_STRUCTURED, reasons, True
        if request.role is ModelRole.OFFLINE_CANDIDATE:
            reasons.add(ModelRouteReasonCode.ROLE_OFFLINE_CANDIDATE)
            return ModelProfile.OFFLINE_CANDIDATE_BUILDER, reasons, True
        if request.role is ModelRole.ACTION_PLANNER:
            reasons.add(ModelRouteReasonCode.ROLE_ACTION_PLANNER)
            return ModelProfile.FAST_STRUCTURED, reasons, True

        profile = request.base_profile
        if request.needs_tool_use:
            reasons.add(ModelRouteReasonCode.TOOL_USE_REQUIRED)
            if profile is ModelProfile.FAST_STRUCTURED:
                profile = ModelProfile.BALANCED_TOOL_USER

        synthesis_upgrade = False
        if request.case_severity is CaseSeverity.CRITICAL:
            reasons.add(ModelRouteReasonCode.CRITICAL_CASE)
            synthesis_upgrade = True
        if request.contradiction_count >= 2:
            reasons.add(ModelRouteReasonCode.CONTRADICTIONS_PRESENT)
            synthesis_upgrade = True
        if request.evidence_path_count >= 3 and request.schema_complexity is OutputSchemaComplexity.HIGH:
            reasons.add(ModelRouteReasonCode.COMPLEX_SYNTHESIS)
            synthesis_upgrade = True
        if request.verification_failure_count > 0:
            reasons.add(ModelRouteReasonCode.VERIFICATION_FAILURE)
            synthesis_upgrade = True
        if synthesis_upgrade and request.role is ModelRole.LEAD:
            profile = ModelProfile.STRONG_SYNTHESIZER
        return profile, reasons, False

    def _binding(self, profile: ModelProfile) -> ModelBinding:
        try:
            return self._bindings[profile]
        except KeyError as exc:
            raise ModelCapabilityError(f"No model binding is configured for profile {profile.value}") from exc

    @staticmethod
    def _require_capabilities(
        request: ModelRouteRequest,
        binding: ModelBinding,
    ) -> None:
        if request.needs_vision and not binding.supports_vision:
            raise ModelCapabilityError(f"Model profile {binding.profile.value} does not support vision")
        if request.needs_tool_use and not binding.supports_tool_use:
            raise ModelCapabilityError(f"Model profile {binding.profile.value} does not support tool use")


def build_model_assignment_event(
    assignment: ModelAssignment,
    *,
    workspace_id: WorkspaceId,
    case_id: CaseId,
    run_id: RunId,
    trace_id: TraceId,
    correlation_id: CorrelationId,
) -> NewDomainEvent:
    """Convert an assignment into the authoritative run/case event envelope."""

    return NewDomainEvent(
        workspace_id=workspace_id,
        case_id=case_id,
        run_id=run_id,
        event_type="model.assigned",
        trace_id=trace_id,
        correlation_id=correlation_id,
        actor=DomainEventActor.AGENT,
        payload=assignment.model_dump(mode="json"),
    )
