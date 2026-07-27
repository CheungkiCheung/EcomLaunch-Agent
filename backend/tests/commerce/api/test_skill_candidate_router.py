"""Skill Candidate proposal API binds content to immutable Experiment evidence."""

from __future__ import annotations

import hashlib

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.commerce.api.dependencies import get_commerce_skill_candidate_service
from app.commerce.api.router import router
from app.commerce.api.skill_candidate_service import CommerceSkillCandidateService
from app.commerce.domain.ids import ExperimentId, WorkspaceId
from app.commerce.evaluation.experiment import (
    ExperimentDecision,
    ExperimentDefinition,
    ExperimentRegistry,
    ExperimentReport,
    ExperimentVariant,
    VariantAggregate,
)
from app.commerce.evaluation.skill_evolution import SkillCandidateRegistry


def _content() -> str:
    return "# Commerce Diagnostic Synthesis\n\nUse association wording, preserve causal uncertainty, and end with one bounded follow-up step.\n"


def _experiment(root, content: str) -> ExperimentId:
    experiment_id = ExperimentId.new()
    definition = ExperimentDefinition(
        id=experiment_id,
        title="Explicit diagnostic contract",
        hypothesis="Candidate preserves safety while improving the Pareto frontier.",
        control=ExperimentVariant(
            name="control",
            prompt_version="prompt@1.0.0",
            context_version="gold-case@1.0.0",
            router_version="router@1.0.0",
            skill_version="prompt-only@1.0.0",
            skill_content_sha256=hashlib.sha256(b"prompt-only").hexdigest(),
        ),
        candidate=ExperimentVariant(
            name="candidate",
            prompt_version="prompt@1.0.0",
            context_version="gold-case@1.0.0",
            router_version="router@1.0.0",
            skill_version="commerce-diagnostic-synthesis@1.2.0-candidate",
            skill_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        ),
        case_keys=("GC-FULFILLMENT-001",),
        repetitions=2,
        controlled_variables=("model=deepseek-v4",),
        reproduction_command="python -m app.commerce.evaluation.run_experiment",
    )
    report = ExperimentReport(
        experiment_id=experiment_id,
        control=VariantAggregate(
            variant_name="control",
            run_count=2,
            passed_count=0,
            hard_gate_failures=2,
            pass_rate=0,
            mean_total_tokens=2_400,
            mean_latency_ms=7_000,
        ),
        candidate=VariantAggregate(
            variant_name="candidate",
            run_count=2,
            passed_count=2,
            hard_gate_failures=0,
            pass_rate=1,
            mean_total_tokens=2_100,
            mean_latency_ms=4_000,
        ),
        decision=ExperimentDecision.PROMOTE_CANDIDATE,
        reasons=("Candidate passes hard gates and improves the Pareto frontier",),
        provider_request_ids=tuple(f"req-{index}" for index in range(8)),
    )
    registry = ExperimentRegistry(root)
    registry.register(definition)
    registry.record_report(report)
    return experiment_id


def _promotable_candidate(skill_root, workspace_id: WorkspaceId):
    registry = SkillCandidateRegistry(skill_root / str(workspace_id))
    candidate = registry.propose(
        skill_name="commerce-diagnostic-synthesis",
        base_version="1.1.0",
        candidate_version="1.2.0",
        content=_content(),
        source_failure_codes=("no-transit-causal-certainty",),
        proposed_by="skill-evolution-runner",
    )
    report = ExperimentReport(
        experiment_id=ExperimentId.new(),
        control=VariantAggregate(
            variant_name="control",
            run_count=2,
            passed_count=0,
            hard_gate_failures=2,
            pass_rate=0,
            mean_total_tokens=2_400,
            mean_latency_ms=7_000,
        ),
        candidate=VariantAggregate(
            variant_name="candidate",
            run_count=2,
            passed_count=2,
            hard_gate_failures=0,
            pass_rate=1,
            mean_total_tokens=2_100,
            mean_latency_ms=4_000,
        ),
        decision=ExperimentDecision.PROMOTE_CANDIDATE,
        reasons=("Candidate passes hard gates and improves the Pareto frontier",),
        provider_request_ids=tuple(f"req-shadow-evidence-{index}" for index in range(8)),
    )
    registry.record_offline_evaluation(
        candidate.id,
        experiment_report=report,
        regression_passed=True,
        holdout_passed=True,
    )
    return registry.record_shadow_result(
        candidate.id,
        passed=True,
        live_run_ids=("run-shadow-001", "run-shadow-002"),
    )


def _headers(workspace_id: WorkspaceId, actor: str = "operator-a") -> dict[str, str]:
    return {
        "X-Commerce-Workspace-Id": str(workspace_id),
        "X-Commerce-Actor-Id": actor,
    }


@pytest.mark.anyio
async def test_skill_candidate_proposal_is_evidence_bound_idempotent_and_scoped(
    tmp_path,
):
    content = _content()
    experiment_root = tmp_path / "experiments"
    experiment_id = _experiment(experiment_root, content)
    service = CommerceSkillCandidateService(
        experiment_root=experiment_root,
        skill_root=tmp_path / "skills",
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_skill_candidate_service] = lambda: service
    workspace_id = WorkspaceId.new()
    body = {
        "skill_name": "commerce-diagnostic-synthesis",
        "base_version": "1.1.0",
        "candidate_version": "1.2.0",
        "content": content,
        "source_failure_codes": ["no-transit-causal-certainty"],
        "experiment_id": str(experiment_id),
        "idempotency_key": "skill-candidate-001",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/api/commerce/skill-candidates",
            headers=_headers(workspace_id),
            json=body,
        )
        replayed = await client.post(
            "/api/commerce/skill-candidates",
            headers=_headers(workspace_id),
            json=body,
        )

        assert created.status_code == 201, created.text
        assert replayed.status_code == 201, replayed.text
        assert created.json()["created"] is True
        assert replayed.json()["created"] is False
        assert created.json()["candidate"]["id"] == replayed.json()["candidate"]["id"]
        assert created.json()["candidate"]["status"] == "candidate"
        assert created.json()["candidate"]["security_scan"]["passed"] is True
        assert created.json()["candidate"]["source_experiment_id"] == str(experiment_id)
        assert created.json()["candidate"]["experiment_id"] is None
        assert created.json()["candidate"]["proposed_by"] == "operator-a"

        candidate_id = created.json()["candidate"]["id"]
        detail = await client.get(
            f"/api/commerce/skill-candidates/{candidate_id}",
            headers=_headers(workspace_id),
        )
        evidence = await client.get(
            f"/api/commerce/skill-candidates/{candidate_id}/evidence",
            headers=_headers(workspace_id),
        )
        isolated = await client.get(
            f"/api/commerce/skill-candidates/{candidate_id}",
            headers=_headers(WorkspaceId.new()),
        )
        isolated_evidence = await client.get(
            f"/api/commerce/skill-candidates/{candidate_id}/evidence",
            headers=_headers(WorkspaceId.new()),
        )
        mismatch = await client.post(
            "/api/commerce/skill-candidates",
            headers=_headers(workspace_id),
            json={
                **body,
                "content": content + "Unmeasured change.\n",
                "idempotency_key": "skill-candidate-002",
            },
        )

    assert detail.status_code == 200
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["candidate"] == detail.json()
    assert evidence.json()["experiment_role"] == "source_proposal"
    assert evidence.json()["definition"]["id"] == str(experiment_id)
    assert evidence.json()["report"]["experiment_id"] == str(experiment_id)
    assert evidence.json()["report"]["candidate"]["passed_count"] == 2
    assert evidence.json()["active_pointer"] is None
    assert isolated.status_code == 404
    assert isolated_evidence.status_code == 404
    assert mismatch.status_code == 409
    assert "content hash" in mismatch.json()["detail"].lower()


@pytest.mark.anyio
async def test_skill_candidate_promotion_active_pointer_and_rollback_are_human_gated_and_idempotent(
    tmp_path,
):
    skill_root = tmp_path / "skills"
    workspace_id = WorkspaceId.new()
    candidate = _promotable_candidate(skill_root, workspace_id)
    service = CommerceSkillCandidateService(
        experiment_root=tmp_path / "experiments",
        skill_root=skill_root,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_skill_candidate_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing_pointer = await client.get(
            f"/api/commerce/skills/{candidate.skill_name}/active",
            headers=_headers(workspace_id),
        )
        promoted = await client.post(
            f"/api/commerce/skill-candidates/{candidate.id}/promote",
            headers=_headers(workspace_id, actor="reviewer-a"),
            json={"idempotency_key": "promote-candidate-001"},
        )
        promotion_replay = await client.post(
            f"/api/commerce/skill-candidates/{candidate.id}/promote",
            headers=_headers(workspace_id, actor="reviewer-a"),
            json={"idempotency_key": "promote-candidate-001"},
        )
        active_pointer = await client.get(
            f"/api/commerce/skills/{candidate.skill_name}/active",
            headers=_headers(workspace_id),
        )
        isolated_pointer = await client.get(
            f"/api/commerce/skills/{candidate.skill_name}/active",
            headers=_headers(WorkspaceId.new()),
        )
        invalid_rollback = await client.post(
            f"/api/commerce/skills/{candidate.skill_name}/rollback",
            headers=_headers(workspace_id, actor="reviewer-b"),
            json={
                "idempotency_key": "rollback-candidate-001",
                "reason": "   ",
            },
        )
        rolled_back = await client.post(
            f"/api/commerce/skills/{candidate.skill_name}/rollback",
            headers=_headers(workspace_id, actor="reviewer-b"),
            json={
                "idempotency_key": "rollback-candidate-001",
                "reason": "Fresh holdout regression after promotion",
            },
        )
        rollback_replay = await client.post(
            f"/api/commerce/skills/{candidate.skill_name}/rollback",
            headers=_headers(workspace_id, actor="reviewer-b"),
            json={
                "idempotency_key": "rollback-candidate-001",
                "reason": "Fresh holdout regression after promotion",
            },
        )
        restored_pointer = await client.get(
            f"/api/commerce/skills/{candidate.skill_name}/active",
            headers=_headers(workspace_id),
        )
        candidate_detail = await client.get(
            f"/api/commerce/skill-candidates/{candidate.id}",
            headers=_headers(workspace_id),
        )

    assert missing_pointer.status_code == 404
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["candidate"]["status"] == "active"
    assert promoted.json()["candidate"]["reviewer_id"] == "reviewer-a"
    assert promoted.json()["active_pointer"]["version"] == "1.2.0"
    assert promoted.json()["active_pointer"]["candidate_id"] == str(candidate.id)
    assert promoted.json()["replayed"] is False
    assert promotion_replay.status_code == 200
    assert promotion_replay.json() == {**promoted.json(), "replayed": True}
    assert active_pointer.status_code == 200
    assert active_pointer.json() == promoted.json()["active_pointer"]
    assert isolated_pointer.status_code == 404
    assert invalid_rollback.status_code == 422
    assert rolled_back.status_code == 200, rolled_back.text
    assert rolled_back.json()["candidate"]["status"] == "rolled_back"
    assert rolled_back.json()["candidate"]["reviewer_id"] == "reviewer-b"
    assert rolled_back.json()["candidate"]["rollback_reason"] == "Fresh holdout regression after promotion"
    assert rolled_back.json()["active_pointer"]["version"] == "1.1.0"
    assert rolled_back.json()["active_pointer"]["candidate_id"] is None
    assert rolled_back.json()["active_pointer"]["rolled_back_candidate_id"] == str(candidate.id)
    assert rolled_back.json()["replayed"] is False
    assert rollback_replay.status_code == 200
    assert rollback_replay.json() == {**rolled_back.json(), "replayed": True}
    assert restored_pointer.json() == rolled_back.json()["active_pointer"]
    assert candidate_detail.json()["status"] == "rolled_back"


@pytest.mark.anyio
async def test_skill_candidate_promotion_rejects_missing_gate_and_idempotency_conflicts(
    tmp_path,
):
    skill_root = tmp_path / "skills"
    workspace_id = WorkspaceId.new()
    registry = SkillCandidateRegistry(skill_root / str(workspace_id))
    candidate = registry.propose(
        skill_name="commerce-diagnostic-synthesis",
        base_version="1.1.0",
        candidate_version="1.2.0",
        content=_content(),
        source_failure_codes=("no-transit-causal-certainty",),
    )
    promotable = _promotable_candidate(skill_root, workspace_id)
    service = CommerceSkillCandidateService(
        experiment_root=tmp_path / "experiments",
        skill_root=skill_root,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commerce_skill_candidate_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing_gate = await client.post(
            f"/api/commerce/skill-candidates/{candidate.id}/promote",
            headers=_headers(workspace_id, actor="reviewer-a"),
            json={"idempotency_key": "promote-shared-key-001"},
        )
        promoted = await client.post(
            f"/api/commerce/skill-candidates/{promotable.id}/promote",
            headers=_headers(workspace_id, actor="reviewer-a"),
            json={"idempotency_key": "promote-candidate-002"},
        )
        conflicting_replay = await client.post(
            f"/api/commerce/skill-candidates/{candidate.id}/promote",
            headers=_headers(workspace_id, actor="reviewer-a"),
            json={"idempotency_key": "promote-candidate-002"},
        )

    assert missing_gate.status_code == 409
    assert "offline evaluation" in missing_gate.json()["detail"].lower()
    assert promoted.status_code == 200
    assert conflicting_replay.status_code == 409
    assert "idempotency" in conflicting_replay.json()["detail"].lower()


def test_skill_promotion_recovers_after_state_append_but_before_pointer_write(
    tmp_path,
    monkeypatch,
):
    skill_root = tmp_path / "skills"
    workspace_id = WorkspaceId.new()
    candidate = _promotable_candidate(skill_root, workspace_id)
    service = CommerceSkillCandidateService(
        experiment_root=tmp_path / "experiments",
        skill_root=skill_root,
    )
    original = SkillCandidateRegistry._write_pointer

    def fail_pointer_write(path, pointer):
        raise RuntimeError("injected active pointer failure")

    monkeypatch.setattr(
        SkillCandidateRegistry,
        "_write_pointer",
        staticmethod(fail_pointer_write),
    )
    with pytest.raises(RuntimeError, match="injected active pointer failure"):
        service.promote(
            workspace_id,
            candidate.id,
            reviewer_id="reviewer-a",
            idempotency_key="promote-fault-001",
        )
    partial = service.get(workspace_id, candidate.id)
    assert partial is not None
    assert partial.status.value == "active"

    monkeypatch.setattr(
        SkillCandidateRegistry,
        "_write_pointer",
        staticmethod(original),
    )
    recovered = service.promote(
        workspace_id,
        candidate.id,
        reviewer_id="reviewer-a",
        idempotency_key="promote-fault-001",
    )

    assert recovered.candidate.status.value == "active"
    assert recovered.active_pointer.candidate_id == candidate.id
    assert recovered.replayed is True


def test_skill_rollback_recovers_after_state_append_but_before_pointer_write(
    tmp_path,
    monkeypatch,
):
    skill_root = tmp_path / "skills"
    workspace_id = WorkspaceId.new()
    candidate = _promotable_candidate(skill_root, workspace_id)
    service = CommerceSkillCandidateService(
        experiment_root=tmp_path / "experiments",
        skill_root=skill_root,
    )
    service.promote(
        workspace_id,
        candidate.id,
        reviewer_id="reviewer-a",
        idempotency_key="promote-before-rollback-001",
    )
    original = SkillCandidateRegistry._write_pointer

    def fail_pointer_write(path, pointer):
        raise RuntimeError("injected rollback pointer failure")

    monkeypatch.setattr(
        SkillCandidateRegistry,
        "_write_pointer",
        staticmethod(fail_pointer_write),
    )
    with pytest.raises(RuntimeError, match="injected rollback pointer failure"):
        service.rollback(
            workspace_id,
            candidate.skill_name,
            reviewer_id="reviewer-b",
            reason="Fresh holdout regression",
            idempotency_key="rollback-fault-001",
        )
    partial = service.get(workspace_id, candidate.id)
    assert partial is not None
    assert partial.status.value == "rolled_back"

    monkeypatch.setattr(
        SkillCandidateRegistry,
        "_write_pointer",
        staticmethod(original),
    )
    recovered = service.rollback(
        workspace_id,
        candidate.skill_name,
        reviewer_id="reviewer-b",
        reason="Fresh holdout regression",
        idempotency_key="rollback-fault-001",
    )

    assert recovered.candidate.status.value == "rolled_back"
    assert recovered.active_pointer.candidate_id is None
    assert recovered.active_pointer.rolled_back_candidate_id == candidate.id
    assert recovered.replayed is True
