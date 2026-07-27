"""Evidence-bound, workspace-scoped Skill Candidate proposal service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from app.commerce.domain.ids import (
    ExperimentId,
    SkillCandidateId,
    WorkspaceId,
)
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.experiment import (
    ExperimentDecision,
    ExperimentDefinition,
    ExperimentReport,
)
from app.commerce.evaluation.skill_evolution import (
    ActiveSkillPointer,
    SkillCandidate,
    SkillCandidateRegistry,
    SkillCandidateStatus,
    SkillEvolutionError,
)


class SkillCandidateEvidenceNotFoundError(LookupError):
    pass


class SkillCandidateProposalConflictError(ValueError):
    pass


class SkillCandidateNotFoundError(LookupError):
    pass


class SkillCandidateTransitionConflictError(ValueError):
    pass


@dataclass(frozen=True)
class SkillCandidateProposalResult:
    candidate: SkillCandidate
    created: bool


@dataclass(frozen=True)
class SkillCandidateTransitionResult:
    candidate: SkillCandidate
    active_pointer: ActiveSkillPointer
    replayed: bool


@dataclass(frozen=True)
class SkillCandidateEvidenceResult:
    candidate: SkillCandidate
    experiment_role: Literal["offline_evaluation", "source_proposal"] | None
    definition: ExperimentDefinition | None
    report: ExperimentReport | None
    active_pointer: ActiveSkillPointer | None


class _SkillCandidateTransitionReceipt(CommerceModel):
    schema_version: str = "commerce.skill-candidate-transition-receipt@1.0.0"
    operation: Literal["promote", "rollback"]
    actor_id: str
    request_sha256: str
    candidate: SkillCandidate
    active_pointer: ActiveSkillPointer


def skill_candidate_id_from_idempotency(
    workspace_id: WorkspaceId,
    actor_id: str,
    idempotency_key: str,
) -> SkillCandidateId:
    key_sha256 = hashlib.sha256(idempotency_key.encode()).hexdigest()
    value = uuid5(
        NAMESPACE_URL,
        (f"commerce.skill-candidate@1:{workspace_id}:{actor_id}:{key_sha256}"),
    )
    return SkillCandidateId(f"skillcand_{value.hex}")


class CommerceSkillCandidateService:
    def __init__(self, *, experiment_root: Path, skill_root: Path) -> None:
        self._experiment_root = experiment_root
        self._skill_root = skill_root

    def propose(
        self,
        workspace_id: WorkspaceId,
        *,
        actor_id: str,
        idempotency_key: str,
        skill_name: str,
        base_version: str,
        candidate_version: str,
        content: str,
        source_failure_codes: tuple[str, ...],
        experiment_id: ExperimentId,
    ) -> SkillCandidateProposalResult:
        definition, report = self._load_experiment(experiment_id)
        self._validate_evidence_binding(
            definition,
            report,
            skill_name=skill_name,
            candidate_version=candidate_version,
            content=content,
        )
        registry = self._registry(workspace_id)
        candidate_id = skill_candidate_id_from_idempotency(
            workspace_id,
            actor_id,
            idempotency_key,
        )
        existing = registry.get(candidate_id)
        if existing is not None:
            expected_hash = hashlib.sha256(content.encode()).hexdigest()
            if any(
                (
                    existing.skill_name != skill_name,
                    existing.base_version != base_version,
                    existing.candidate_version != candidate_version,
                    existing.content_sha256 != expected_hash,
                    existing.source_failure_codes != source_failure_codes,
                    existing.source_experiment_id != experiment_id,
                    existing.proposed_by != actor_id,
                )
            ):
                raise SkillCandidateProposalConflictError("Skill Candidate idempotency key conflicts with prior proposal")
            return SkillCandidateProposalResult(existing, False)
        candidate = registry.propose(
            candidate_id=candidate_id,
            skill_name=skill_name,
            base_version=base_version,
            candidate_version=candidate_version,
            content=content,
            source_failure_codes=source_failure_codes,
            proposed_by=actor_id,
            source_experiment_report=report,
        )
        return SkillCandidateProposalResult(candidate, True)

    def get(
        self,
        workspace_id: WorkspaceId,
        candidate_id: SkillCandidateId,
    ) -> SkillCandidate | None:
        return self._registry(workspace_id).get(candidate_id)

    def list(self, workspace_id: WorkspaceId) -> tuple[SkillCandidate, ...]:
        return self._registry(workspace_id).list_candidates()

    def evidence(
        self,
        workspace_id: WorkspaceId,
        candidate_id: SkillCandidateId,
    ) -> SkillCandidateEvidenceResult:
        registry = self._registry(workspace_id)
        candidate = registry.get(candidate_id)
        if candidate is None:
            raise SkillCandidateNotFoundError("Skill Candidate was not found")
        experiment_id = candidate.experiment_id or candidate.source_experiment_id
        experiment_role: Literal["offline_evaluation", "source_proposal"] | None
        if candidate.experiment_id is not None:
            experiment_role = "offline_evaluation"
        elif candidate.source_experiment_id is not None:
            experiment_role = "source_proposal"
        else:
            experiment_role = None
        definition: ExperimentDefinition | None = None
        report: ExperimentReport | None = None
        if experiment_id is not None:
            definition, report = self._load_experiment(experiment_id)
        try:
            active_pointer = registry.active_pointer(candidate.skill_name)
        except SkillEvolutionError as exc:
            raise SkillCandidateTransitionConflictError(str(exc)) from exc
        return SkillCandidateEvidenceResult(
            candidate=candidate,
            experiment_role=experiment_role,
            definition=definition,
            report=report,
            active_pointer=active_pointer,
        )

    def promote(
        self,
        workspace_id: WorkspaceId,
        candidate_id: SkillCandidateId,
        *,
        reviewer_id: str,
        idempotency_key: str,
    ) -> SkillCandidateTransitionResult:
        request_sha256 = self._request_sha256(
            operation="promote",
            subject=str(candidate_id),
            actor_id=reviewer_id,
        )
        receipt_path = self._receipt_path(
            workspace_id,
            actor_id=reviewer_id,
            idempotency_key=idempotency_key,
        )
        replay = self._replay_receipt(receipt_path, request_sha256=request_sha256)
        if replay is not None:
            return replay
        registry = self._registry(workspace_id)
        current = registry.get(candidate_id)
        if current is None:
            raise SkillCandidateNotFoundError("Skill Candidate was not found")
        recovered = current.status is SkillCandidateStatus.ACTIVE
        try:
            if recovered:
                candidate, pointer = registry.recover_active_pointer(
                    candidate_id,
                    reviewer_id=reviewer_id,
                )
            else:
                candidate = registry.promote(candidate_id, reviewer_id=reviewer_id)
                pointer = registry.active_pointer(candidate.skill_name)
        except SkillEvolutionError as exc:
            raise SkillCandidateTransitionConflictError(str(exc)) from exc
        if pointer is None or pointer.candidate_id != candidate.id:
            raise SkillCandidateTransitionConflictError("Active Skill pointer does not match the promoted Candidate")
        receipt = _SkillCandidateTransitionReceipt(
            operation="promote",
            actor_id=reviewer_id,
            request_sha256=request_sha256,
            candidate=candidate,
            active_pointer=pointer,
        )
        recorded = self._record_receipt(receipt_path, receipt)
        if recovered and not recorded.replayed:
            return SkillCandidateTransitionResult(
                candidate=recorded.candidate,
                active_pointer=recorded.active_pointer,
                replayed=True,
            )
        return recorded

    def active_pointer(
        self,
        workspace_id: WorkspaceId,
        skill_name: str,
    ) -> ActiveSkillPointer | None:
        try:
            return self._registry(workspace_id).active_pointer(skill_name)
        except SkillEvolutionError as exc:
            raise SkillCandidateTransitionConflictError(str(exc)) from exc

    def rollback(
        self,
        workspace_id: WorkspaceId,
        skill_name: str,
        *,
        reviewer_id: str,
        reason: str,
        idempotency_key: str,
    ) -> SkillCandidateTransitionResult:
        request_sha256 = self._request_sha256(
            operation="rollback",
            subject=skill_name,
            actor_id=reviewer_id,
            reason=reason.strip(),
        )
        receipt_path = self._receipt_path(
            workspace_id,
            actor_id=reviewer_id,
            idempotency_key=idempotency_key,
        )
        replay = self._replay_receipt(receipt_path, request_sha256=request_sha256)
        if replay is not None:
            return replay
        registry = self._registry(workspace_id)
        current_pointer = registry.active_pointer(skill_name)
        if current_pointer is None:
            raise SkillCandidateNotFoundError("Active Skill pointer was not found")
        current_candidate_id = (
            current_pointer.rolled_back_candidate_id
            or current_pointer.candidate_id
        )
        if current_candidate_id is None:
            raise SkillCandidateTransitionConflictError(
                "Active Skill pointer has no Candidate identity"
            )
        current_candidate = registry.get(current_candidate_id)
        recovered = (
            current_candidate is not None
            and current_candidate.status is SkillCandidateStatus.ROLLED_BACK
        )
        try:
            if recovered:
                candidate, pointer = registry.recover_rollback_pointer(
                    skill_name,
                    reviewer_id=reviewer_id,
                    reason=reason,
                )
            else:
                candidate = registry.rollback(
                    skill_name,
                    reviewer_id=reviewer_id,
                    reason=reason,
                )
                pointer = registry.active_pointer(skill_name)
        except SkillEvolutionError as exc:
            raise SkillCandidateTransitionConflictError(str(exc)) from exc
        if pointer is None or pointer.rolled_back_candidate_id != candidate.id:
            raise SkillCandidateTransitionConflictError("Active Skill pointer does not match the rolled-back Candidate")
        receipt = _SkillCandidateTransitionReceipt(
            operation="rollback",
            actor_id=reviewer_id,
            request_sha256=request_sha256,
            candidate=candidate,
            active_pointer=pointer,
        )
        recorded = self._record_receipt(receipt_path, receipt)
        if recovered and not recorded.replayed:
            return SkillCandidateTransitionResult(
                candidate=recorded.candidate,
                active_pointer=recorded.active_pointer,
                replayed=True,
            )
        return recorded

    def _registry(self, workspace_id: WorkspaceId) -> SkillCandidateRegistry:
        return SkillCandidateRegistry(self._skill_root / str(workspace_id))

    def _receipt_path(
        self,
        workspace_id: WorkspaceId,
        *,
        actor_id: str,
        idempotency_key: str,
    ) -> Path:
        command_sha256 = hashlib.sha256(f"{actor_id}\0{idempotency_key}".encode()).hexdigest()
        return self._skill_root / str(workspace_id) / "commands" / f"{command_sha256}.json"

    @staticmethod
    def _request_sha256(
        *,
        operation: Literal["promote", "rollback"],
        subject: str,
        actor_id: str,
        reason: str | None = None,
    ) -> str:
        payload = {
            "actor_id": actor_id,
            "operation": operation,
            "reason": reason,
            "subject": subject,
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()

    @staticmethod
    def _replay_receipt(
        path: Path,
        *,
        request_sha256: str,
    ) -> SkillCandidateTransitionResult | None:
        if not path.is_file():
            return None
        try:
            receipt = _SkillCandidateTransitionReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SkillCandidateTransitionConflictError("Skill transition receipt is invalid") from exc
        if receipt.request_sha256 != request_sha256:
            raise SkillCandidateTransitionConflictError(
                "Skill transition idempotency key conflicts with a prior request"
            )
        return SkillCandidateTransitionResult(
            candidate=receipt.candidate,
            active_pointer=receipt.active_pointer,
            replayed=True,
        )

    @staticmethod
    def _record_receipt(
        path: Path,
        receipt: _SkillCandidateTransitionReceipt,
    ) -> SkillCandidateTransitionResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(
                    receipt.model_dump(mode="json"),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
        except FileExistsError:
            replay = CommerceSkillCandidateService._replay_receipt(
                path,
                request_sha256=receipt.request_sha256,
            )
            if replay is None:
                raise SkillCandidateTransitionConflictError("Skill transition receipt was not persisted")
            return replay
        return SkillCandidateTransitionResult(
            candidate=receipt.candidate,
            active_pointer=receipt.active_pointer,
            replayed=False,
        )

    def _load_experiment(
        self,
        experiment_id: ExperimentId,
    ) -> tuple[ExperimentDefinition, ExperimentReport]:
        definition_path = self._experiment_root / "definitions" / f"{experiment_id}.json"
        report_path = self._experiment_root / "reports" / f"{experiment_id}.json"
        if not definition_path.is_file() or not report_path.is_file():
            raise SkillCandidateEvidenceNotFoundError("Experiment Definition or Report was not found")
        try:
            definition = ExperimentDefinition.model_validate_json(definition_path.read_text(encoding="utf-8"))
            report = ExperimentReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SkillCandidateProposalConflictError("Experiment evidence is invalid") from exc
        if definition.id != experiment_id or report.experiment_id != experiment_id:
            raise SkillCandidateProposalConflictError("Experiment evidence identity does not match")
        return definition, report

    @staticmethod
    def _validate_evidence_binding(
        definition: ExperimentDefinition,
        report: ExperimentReport,
        *,
        skill_name: str,
        candidate_version: str,
        content: str,
    ) -> None:
        if report.decision is not ExperimentDecision.PROMOTE_CANDIDATE:
            raise SkillCandidateProposalConflictError("Experiment did not promote the Candidate variant")
        expected_runs = len(definition.case_keys) * definition.repetitions
        if report.candidate.variant_name != definition.candidate.name or report.candidate.run_count != expected_runs or report.candidate.hard_gate_failures != 0 or report.candidate.pass_rate != 1:
            raise SkillCandidateProposalConflictError("Experiment Candidate evidence is incomplete")
        request_ids = report.provider_request_ids
        if len(request_ids) < expected_runs * 2 or len(request_ids) != len(set(request_ids)):
            raise SkillCandidateProposalConflictError("Experiment does not contain fresh generation and verification evidence")
        expected_skill_version = f"{skill_name}@{candidate_version}-candidate"
        if definition.candidate.skill_version != expected_skill_version:
            raise SkillCandidateProposalConflictError("Candidate version does not match the Experiment Definition")
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if definition.candidate.skill_content_sha256 != content_hash:
            raise SkillCandidateProposalConflictError("Candidate content hash does not match the Experiment Definition")
