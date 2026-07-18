"""Live DeepSeek V4 semantic-candidate integration test.

This test is deliberately not part of deterministic Commerce regression. It
must make a fresh preflight request and a fresh candidate request; it never
uses a fake, replay, cache or fallback model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.commerce.data.intake import DataIntakeService
from app.commerce.data.profiler import DataProfiler
from app.commerce.data.semantic_candidate_service import (
    CandidateRunStatus,
    SemanticCandidateAuditStore,
    SemanticCandidateService,
)
from app.commerce.domain.ids import WorkspaceId


@pytest.mark.real_model
def test_real_deepseek_v4_returns_unconfirmed_semantic_candidates(tmp_path: Path):
    source = tmp_path / "orders.csv"
    source.write_text(
        "order_id,order_purchase_timestamp\n"
        "o1,2018-01-01 10:00:00\n",
        encoding="utf-8",
    )
    storage_root = tmp_path / "commerce-storage"
    manifest = DataIntakeService(storage_root=storage_root).ingest(
        WorkspaceId.new(),
        (source,),
    )
    profile = DataProfiler(storage_root=storage_root).profile(manifest)

    result = SemanticCandidateService(
        audit_store=SemanticCandidateAuditStore(tmp_path / "candidate-audit")
    ).suggest(profile)

    assert result.telemetry.status is CandidateRunStatus.PASSED
    assert result.telemetry.actual_model_identity is not None
    assert result.telemetry.actual_model_identity.lower().startswith("deepseek-v4")
    assert result.telemetry.request_attempt_count == 1
    assert result.telemetry.retry_count == 0
    assert all(
        mapping.status.value != "confirmed"
        for mapping in result.mapping_profile.mappings
        if mapping.source.value == "llm_candidate"
    )
    assert (tmp_path / "candidate-audit" / f"{result.telemetry.run_id}.json").is_file()
