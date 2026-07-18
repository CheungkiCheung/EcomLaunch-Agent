"""Versioned JSON contracts for the Commerce Case read workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommerceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseResponse(CommerceResponse):
    id: str
    workspace_id: str
    title: str
    severity: str
    status: str
    summary: str | None
    evidence_ids: list[str]
    hypothesis_ids: list[str]
    action_ids: list[str]
    opened_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)


class EvidenceResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str
    summary: str
    relation: str
    semantic_status: str
    confidence: float = Field(ge=0.0, le=1.0)
    fact_ids: list[str]
    metric_observation_ids: list[str]


class HypothesisResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str
    statement: str
    status: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    version: int = Field(ge=1)


class DomainEventResponse(CommerceResponse):
    id: str
    workspace_id: str
    case_id: str | None
    run_id: str | None
    event_type: str
    schema_version: str
    case_sequence: int | None
    run_sequence: int | None
    occurred_at: datetime
    recorded_at: datetime
    trace_id: str
    correlation_id: str
    causation_event_id: str | None
    actor: str
    payload: dict[str, Any]


class CaseListResponse(CommerceResponse):
    items: list[CaseResponse]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class CaseDetailResponse(CommerceResponse):
    case: CaseResponse
    evidence: list[EvidenceResponse]
    hypotheses: list[HypothesisResponse]


class EvidenceListResponse(CommerceResponse):
    items: list[EvidenceResponse]


class HypothesisListResponse(CommerceResponse):
    items: list[HypothesisResponse]


class DomainEventListResponse(CommerceResponse):
    items: list[DomainEventResponse]
