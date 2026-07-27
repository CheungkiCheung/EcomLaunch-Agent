"""Fresh DeepSeek V4 Skill Candidate Shadow runs over persisted Commerce Runs."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import ExperimentId, WorkspaceId
from app.commerce.evaluation.experiment import (
    ExperimentDecision,
    ExperimentReport,
    VariantAggregate,
)
from app.commerce.evaluation.run_experiment import _CANDIDATE_SKILL_CONTRACT
from app.commerce.evaluation.shadow import (
    FreshSkillShadowRunner,
    SkillShadowAuditRegistry,
    record_passing_shadow,
)
from app.commerce.evaluation.skill_evolution import (
    SkillCandidateRegistry,
    SkillCandidateStatus,
)
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"
CASE_KEYS = ("GC-FULFILLMENT-001", "GC-REVIEW-002")


def _offline_candidate(root: Path):
    experiment_id = ExperimentId.new()
    report = ExperimentReport(
        experiment_id=experiment_id,
        control=VariantAggregate(
            variant_name="control",
            run_count=6,
            passed_count=3,
            hard_gate_failures=3,
            pass_rate=0.5,
            mean_total_tokens=2_300,
            mean_latency_ms=7_400,
        ),
        candidate=VariantAggregate(
            variant_name="candidate",
            run_count=6,
            passed_count=6,
            hard_gate_failures=0,
            pass_rate=1,
            mean_total_tokens=2_000,
            mean_latency_ms=5_000,
        ),
        decision=ExperimentDecision.PROMOTE_CANDIDATE,
        reasons=("Candidate passed regression and holdout",),
        provider_request_ids=tuple(f"setup-request-{index}" for index in range(24)),
    )
    registry = SkillCandidateRegistry(root)
    proposed = registry.propose(
        skill_name="commerce-diagnostic-synthesis",
        base_version="1.1.0",
        candidate_version="1.3.0",
        content=_CANDIDATE_SKILL_CONTRACT,
        source_failure_codes=("no-transit-causal-certainty",),
        proposed_by="shadow-test",
        source_experiment_report=report,
    )
    evaluated = registry.record_offline_evaluation(
        proposed.id,
        experiment_report=report,
        regression_passed=True,
        holdout_passed=True,
    )
    return registry, evaluated


@pytest.mark.real_model
@pytest.mark.anyio
async def test_candidate_shadow_uses_two_live_runs_without_case_side_effects(
    tmp_path,
):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'skill-shadow.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = WorkspaceId.new()
    data_service = CommerceDataService(storage_root=tmp_path / "commerce-data")
    skill_registry, candidate = _offline_candidate(tmp_path / "skills")
    shadow_root = tmp_path / "shadow"
    runner = FreshSkillShadowRunner(audit_registry=SkillShadowAuditRegistry(shadow_root))
    shadow_runs = []
    before_cases = {}
    try:
        for case_key in CASE_KEYS:
            case_root = CASES_ROOT / case_key
            evaluation_case = load_evaluation_case(case_root)
            request = evaluation_case.input_bundle.analysis_request
            assert request is not None
            view = data_service.ingest_uploads(
                workspace_id,
                tuple(
                    (
                        Path(item.relative_path).name,
                        (case_root / item.relative_path).read_bytes(),
                    )
                    for item in evaluation_case.input_bundle.files
                ),
            )
            analysis = await CommerceAnalysisService(
                data_service=data_service,
                session_factory=factory,
            ).analyze(
                workspace_id,
                view.manifest.dataset_id,
                baseline_window=MetricWindow(
                    start=request.baseline_window.start,
                    end=request.baseline_window.end,
                ),
                current_window=MetricWindow(
                    start=request.anomaly_window.start,
                    end=request.anomaly_window.end,
                ),
                seller_id=request.seller_id,
            )
            case = analysis.cases[0]
            commerce_run = (
                await CommerceRunService(factory).start_investigation(
                    workspace_id,
                    case.id,
                    goal=evaluation_case.input_bundle.user_prompt,
                    idempotency_key=f"shadow-{case_key.lower()}",
                )
            ).run
            context = await ContextPacketLoader(
                data_service=data_service,
                session_factory=factory,
            ).load_case_packet(
                workspace_id,
                case.id,
                goal=commerce_run.goal,
                budget=AgentBudgetLimit(max_tokens=12_000),
            )
            before_cases[case.id] = await SqlCaseRepository(factory).get(
                workspace_id,
                case.id,
            )
            shadow_runs.append(
                await runner.run(
                    candidate=candidate,
                    commerce_run=commerce_run,
                    context=context,
                    evaluation_case=evaluation_case,
                )
            )

        report = runner.build_report(candidate, tuple(shadow_runs))
        shadowed = record_passing_shadow(skill_registry, report)

        assert report.passed is True
        assert len(report.provider_request_ids) == 4
        assert len(report.provider_request_ids) == len(set(report.provider_request_ids))
        assert all(item.generation_evidence.actual_model_identity.startswith("deepseek-v4") for item in report.runs)
        assert all(item.semantic_evidence.actual_model_identity.startswith("deepseek-v4") for item in report.runs)
        assert all(item.generation_evidence.retry_count == 0 and item.semantic_evidence.retry_count == 0 for item in report.runs)
        assert shadowed.status is SkillCandidateStatus.SHADOW
        assert set(shadowed.shadow_live_run_ids) == {str(item.commerce_run_id) for item in report.runs}
        for case_id, before in before_cases.items():
            after = await SqlCaseRepository(factory).get(workspace_id, case_id)
            assert after == before
        assert len(tuple((shadow_root / "runs").rglob("*.json"))) == 2
        assert len(tuple((shadow_root / "reports").rglob("*.json"))) == 1
    finally:
        await engine.dispose()
