"""Deterministic contracts for real-run Skill Candidate shadow evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.commerce.domain.ids import (
    CaseId,
    RunId,
    SkillCandidateId,
    WorkspaceId,
)
from app.commerce.evaluation.run_shadow import create_shadow_workspace_root
from app.commerce.evaluation.runner import RealModelEvidence
from app.commerce.evaluation.shadow import (
    SkillShadowReport,
    SkillShadowRunRecord,
)


def _evidence(request_id: str) -> RealModelEvidence:
    return RealModelEvidence(
        actual_model_identity="deepseek-v4-flash",
        provider_request_id=request_id,
        configured_model_alias="deepseek-reasoner",
        endpoint="https://api.deepseek.com/v1",
        fresh_request=True,
        retry_count=0,
        input_tokens=800,
        output_tokens=100,
        latency_ms=1_500,
    )


def _run(
    candidate_id: SkillCandidateId,
    *,
    run_id: RunId,
    generation_request_id: str,
    semantic_request_id: str,
) -> SkillShadowRunRecord:
    return SkillShadowRunRecord(
        candidate_id=candidate_id,
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        commerce_run_id=run_id,
        case_key="GC-FULFILLMENT-001",
        context_sha256="a" * 64,
        generation_evidence=_evidence(generation_request_id),
        semantic_evidence=_evidence(semantic_request_id),
        response_content_sha256="b" * 64,
        semantic_response_sha256="c" * 64,
        passed=True,
        created_at=datetime.now(UTC),
    )


def test_shadow_report_requires_two_distinct_live_runs_and_model_requests():
    candidate_id = SkillCandidateId.new()
    first_run_id = RunId.new()
    first = _run(
        candidate_id,
        run_id=first_run_id,
        generation_request_id="req-generation-1",
        semantic_request_id="req-semantic-1",
    )
    second = _run(
        candidate_id,
        run_id=RunId.new(),
        generation_request_id="req-generation-2",
        semantic_request_id="req-semantic-2",
    )

    report = SkillShadowReport(candidate_id=candidate_id, runs=(first, second))

    assert report.passed is True
    assert len(report.provider_request_ids) == 4
    with pytest.raises(ValidationError, match="distinct Commerce Runs"):
        SkillShadowReport(
            candidate_id=candidate_id,
            runs=(first, first.model_copy(update={"workspace_id": WorkspaceId.new()})),
        )
    with pytest.raises(ValidationError, match="Provider request IDs"):
        SkillShadowReport(
            candidate_id=candidate_id,
            runs=(
                first,
                second.model_copy(update={"generation_evidence": _evidence("req-generation-1")}),
            ),
        )


def test_formal_shadow_creates_nested_sqlite_workspace_before_use(tmp_path):
    candidate_id = SkillCandidateId.new()

    workspace_root = create_shadow_workspace_root(
        tmp_path / "nested" / "shadow",
        candidate_id,
        execution_nonce="fixed",
    )

    assert workspace_root.is_dir()
    assert workspace_root.name == f"shadow-{candidate_id}-fixed"
