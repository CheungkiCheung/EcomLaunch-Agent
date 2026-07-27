"""Run and persist two side-effect-free live Shadow evaluations for a Candidate."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commerce.agents.context_loader import ContextPacketLoader
from app.commerce.agents.contracts import AgentBudgetLimit
from app.commerce.api.analysis_service import CommerceAnalysisService
from app.commerce.api.data_service import CommerceDataService
from app.commerce.api.run_service import CommerceRunService
from app.commerce.data.gold_cases import load_evaluation_case
from app.commerce.domain.ids import SkillCandidateId, WorkspaceId
from app.commerce.evaluation.shadow import (
    FreshSkillShadowRunner,
    SkillShadowAuditRegistry,
    record_passing_shadow,
)
from app.commerce.evaluation.skill_evolution import SkillCandidateRegistry
from app.commerce.metrics.registry import MetricWindow
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.schema import create_commerce_schema

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CASES_ROOT = _REPO_ROOT / "evals" / "commerce" / "cases"
_SHADOW_ROOT = _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "shadow"
_SKILL_ROOT = _REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "skills"


def create_shadow_workspace_root(
    root: Path,
    candidate_id: SkillCandidateId,
    *,
    execution_nonce: str | None = None,
) -> Path:
    nonce = execution_nonce or uuid4().hex
    workspace_root = root / "workspaces" / f"shadow-{candidate_id}-{nonce}"
    workspace_root.mkdir(parents=True, exist_ok=False)
    return workspace_root


async def run_candidate_shadow(
    *,
    candidate_id: SkillCandidateId,
    workspace_id: WorkspaceId,
    case_keys: tuple[str, ...],
):
    if len(case_keys) < 2 or len(case_keys) != len(set(case_keys)):
        raise ValueError("Formal Shadow requires at least two unique Gold Cases")
    skill_registry = SkillCandidateRegistry(_SKILL_ROOT / str(workspace_id))
    candidate = skill_registry.get(candidate_id)
    if candidate is None:
        raise ValueError("Skill Candidate was not found in the Workspace")

    workspace_root = create_shadow_workspace_root(_SHADOW_ROOT, candidate_id)
    execution_id = workspace_root.name
    data_service = CommerceDataService(storage_root=workspace_root / "data")
    engine = create_async_engine(f"sqlite+aiosqlite:///{workspace_root / 'commerce.db'}")
    await create_commerce_schema(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    runner = FreshSkillShadowRunner(audit_registry=SkillShadowAuditRegistry(_SHADOW_ROOT))
    shadow_runs = []
    before_cases = {}
    try:
        for case_key in case_keys:
            case_root = _CASES_ROOT / case_key
            evaluation_case = load_evaluation_case(case_root)
            request = evaluation_case.input_bundle.analysis_request
            if request is None:
                raise ValueError(f"Gold Case {case_key} has no visible analysis_request")
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
            if len(analysis.cases) != 1:
                raise ValueError(f"Gold Case {case_key} did not create exactly one Case")
            case = analysis.cases[0]
            commerce_run = (
                await CommerceRunService(factory).start_investigation(
                    workspace_id,
                    case.id,
                    goal=evaluation_case.input_bundle.user_prompt,
                    idempotency_key=f"{execution_id}-{case_key.lower()}",
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

        for case_id, before in before_cases.items():
            after = await SqlCaseRepository(factory).get(workspace_id, case_id)
            if after != before:
                raise RuntimeError("Shadow modified authoritative Commerce Case state")
        report = runner.build_report(candidate, tuple(shadow_runs))
        shadowed = record_passing_shadow(skill_registry, report)
        return report, shadowed, workspace_root
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run formal fresh DeepSeek V4 Skill Candidate Shadow gates")
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument(
        "--workspace-id",
        default="wsp_00000000000000000000000000000001",
    )
    parser.add_argument("--case-key", action="append", dest="case_keys")
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    case_keys = tuple(args.case_keys or ("GC-FULFILLMENT-001", "GC-REVIEW-002"))
    report, candidate, workspace_root = await run_candidate_shadow(
        candidate_id=SkillCandidateId(args.candidate_id),
        workspace_id=WorkspaceId(args.workspace_id),
        case_keys=case_keys,
    )
    print(
        json.dumps(
            {
                "candidate_id": str(candidate.id),
                "status": candidate.status.value,
                "shadow_live_run_ids": list(candidate.shadow_live_run_ids),
                "provider_request_ids": list(report.provider_request_ids),
                "passed": report.passed,
                "workspace_root": str(workspace_root),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
