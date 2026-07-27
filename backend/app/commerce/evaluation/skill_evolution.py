"""Immutable Skill Candidates with eval, shadow, promotion, and rollback gates."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from app.commerce.domain.ids import ExperimentId, SkillCandidateId
from app.commerce.domain.models import CommerceModel
from app.commerce.evaluation.experiment import (
    ExperimentDecision,
    ExperimentReport,
)


class SkillCandidateStatus(StrEnum):
    CANDIDATE = "candidate"
    OFFLINE_EVALUATED = "offline_evaluated"
    SHADOW = "shadow"
    ACTIVE = "active"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class SkillEvolutionError(ValueError):
    pass


class SkillSecurityScan(CommerceModel):
    passed: bool
    findings: tuple[str, ...] = ()
    scanner_version: str = "commerce-skill-security@1.0.0"


class ActiveSkillPointer(CommerceModel):
    """Workspace-scoped pointer updated only by reviewed promotion or rollback."""

    schema_version: str = "commerce.active-skill-pointer@1.0.0"
    skill_name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    candidate_id: SkillCandidateId | None
    previous_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    reviewer_id: str = Field(min_length=1, max_length=128)
    rolled_back_candidate_id: SkillCandidateId | None = None
    rollback_reviewer_id: str | None = Field(default=None, min_length=1, max_length=128)
    rollback_reason: str | None = Field(default=None, min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def keep_pointer_consistent(self) -> Self:
        rollback_values = (
            self.rolled_back_candidate_id,
            self.rollback_reviewer_id,
            self.rollback_reason,
        )
        if self.candidate_id is not None and any(value is not None for value in rollback_values):
            raise ValueError("Active Skill pointer cannot also describe a rollback")
        if self.candidate_id is None and any(value is None for value in rollback_values):
            raise ValueError("Rolled-back Skill pointer requires complete rollback evidence")
        return self


class SkillCandidate(CommerceModel):
    schema_version: str = "commerce.skill-candidate@1.0.0"
    id: SkillCandidateId = Field(default_factory=SkillCandidateId.new)
    skill_name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    base_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    candidate_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_failure_codes: tuple[str, ...] = Field(min_length=1)
    security_scan: SkillSecurityScan
    proposed_by: str = Field(default="system", min_length=1, max_length=128)
    status: SkillCandidateStatus = SkillCandidateStatus.CANDIDATE
    source_experiment_id: ExperimentId | None = None
    source_experiment_decision: ExperimentDecision | None = None
    experiment_id: ExperimentId | None = None
    experiment_decision: ExperimentDecision | None = None
    regression_passed: bool | None = None
    holdout_passed: bool | None = None
    shadow_passed: bool | None = None
    shadow_live_run_ids: tuple[str, ...] = ()
    reviewer_id: str | None = Field(default=None, min_length=1)
    rollback_reason: str | None = Field(default=None, min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def keep_candidate_consistent(self) -> Self:
        if self.base_version == self.candidate_version:
            raise ValueError("Skill Candidate must change the version")
        if self.content_sha256 != hashlib.sha256(self.content.encode()).hexdigest():
            raise ValueError("Skill Candidate content hash does not match")
        if len(self.source_failure_codes) != len(set(self.source_failure_codes)):
            raise ValueError("Skill Candidate failure codes must be unique")
        if (self.experiment_id is None) != (self.experiment_decision is None):
            raise ValueError("Skill Candidate Experiment ID and decision must appear together")
        if (self.source_experiment_id is None) != (self.source_experiment_decision is None):
            raise ValueError("Skill Candidate source Experiment ID and decision must appear together")
        if self.status in {
            SkillCandidateStatus.OFFLINE_EVALUATED,
            SkillCandidateStatus.SHADOW,
            SkillCandidateStatus.ACTIVE,
        } and any(
            value is None
            for value in (
                self.experiment_id,
                self.experiment_decision,
                self.regression_passed,
                self.holdout_passed,
            )
        ):
            raise ValueError("Evaluated Skill Candidate requires Experiment evidence")
        if self.status in {SkillCandidateStatus.SHADOW, SkillCandidateStatus.ACTIVE}:
            if self.shadow_passed is not True or len(self.shadow_live_run_ids) < 2:
                raise ValueError("Shadow Skill Candidate requires two passing live Runs")
        if self.status is SkillCandidateStatus.ACTIVE and self.reviewer_id is None:
            raise ValueError("Active Skill Candidate requires human review")
        if self.status is SkillCandidateStatus.ROLLED_BACK and (self.reviewer_id is None or self.rollback_reason is None):
            raise ValueError("Rolled-back Skill Candidate requires reviewer and reason")
        return self


_SECURITY_RULES = (
    (re.compile(r"(?i)\b(?:api[_-]?key|secret|password)\s*[=:]"), "embedded-secret"),
    (re.compile(r"(?i)\bsk-[a-z0-9]{8,}"), "credential-shaped-token"),
    (re.compile(r"(?i)\brm\s+-rf\b"), "destructive-shell"),
    (re.compile(r"(?i)\bgit\s+push\b"), "external-state-mutation"),
    (re.compile(r"(?i)modify\s+(?:the\s+)?active\s+skill"), "direct-active-edit"),
    (re.compile(r"(?i)\bskill_manage\b"), "runtime-skill-manage"),
)


class SkillCandidateRegistry:
    """Only Promotion Service may update the Active Skill pointer."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def propose(
        self,
        *,
        candidate_id: SkillCandidateId | None = None,
        skill_name: str,
        base_version: str,
        candidate_version: str,
        content: str,
        source_failure_codes: tuple[str, ...],
        proposed_by: str = "system",
        source_experiment_report: ExperimentReport | None = None,
    ) -> SkillCandidate:
        findings = tuple(code for pattern, code in _SECURITY_RULES if pattern.search(content))
        scan = SkillSecurityScan(passed=not findings, findings=findings)
        candidate = SkillCandidate(
            id=candidate_id or SkillCandidateId.new(),
            skill_name=skill_name,
            base_version=base_version,
            candidate_version=candidate_version,
            content=content,
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            source_failure_codes=source_failure_codes,
            security_scan=scan,
            proposed_by=proposed_by,
            source_experiment_id=(source_experiment_report.experiment_id if source_experiment_report is not None else None),
            source_experiment_decision=(source_experiment_report.decision if source_experiment_report is not None else None),
        )
        self._write_new(
            self._root / "candidates" / f"{candidate.id}.json",
            candidate.model_dump(mode="json"),
        )
        self._append_state(candidate)
        return candidate

    def record_offline_evaluation(
        self,
        candidate_id: SkillCandidateId,
        *,
        experiment_report: ExperimentReport,
        regression_passed: bool,
        holdout_passed: bool,
    ) -> SkillCandidate:
        candidate = self._latest(candidate_id)
        if candidate.status is not SkillCandidateStatus.CANDIDATE:
            raise SkillEvolutionError("Skill Candidate is not awaiting offline evaluation")
        if not candidate.security_scan.passed:
            raise SkillEvolutionError("Skill Candidate failed security scan")
        if experiment_report.decision is not ExperimentDecision.PROMOTE_CANDIDATE:
            raise SkillEvolutionError("Experiment did not approve the Skill Candidate")
        if not regression_passed or not holdout_passed:
            raise SkillEvolutionError("Regression and holdout must both pass")
        updated = self._transition(
            candidate,
            status=SkillCandidateStatus.OFFLINE_EVALUATED,
            experiment_id=experiment_report.experiment_id,
            experiment_decision=experiment_report.decision,
            regression_passed=True,
            holdout_passed=True,
        )
        self._append_state(updated)
        return updated

    def get(self, candidate_id: SkillCandidateId) -> SkillCandidate | None:
        try:
            return self._latest(candidate_id)
        except SkillEvolutionError:
            return None

    def list_candidates(self) -> tuple[SkillCandidate, ...]:
        state_root = self._root / "states"
        if not state_root.is_dir():
            return ()
        candidates = []
        for candidate_root in sorted(state_root.iterdir()):
            if not candidate_root.is_dir():
                continue
            try:
                candidates.append(self._latest(SkillCandidateId(candidate_root.name)))
            except (SkillEvolutionError, ValueError):
                continue
        return tuple(candidates)

    def record_shadow_result(
        self,
        candidate_id: SkillCandidateId,
        *,
        passed: bool,
        live_run_ids: tuple[str, ...],
    ) -> SkillCandidate:
        candidate = self._latest(candidate_id)
        if candidate.status is not SkillCandidateStatus.OFFLINE_EVALUATED:
            raise SkillEvolutionError("Skill Candidate is not awaiting shadow evaluation")
        if not passed or len(set(live_run_ids)) < 2:
            raise SkillEvolutionError("Shadow requires two distinct passing live Runs")
        updated = self._transition(
            candidate,
            status=SkillCandidateStatus.SHADOW,
            shadow_passed=True,
            shadow_live_run_ids=live_run_ids,
        )
        self._append_state(updated)
        return updated

    def promote(
        self,
        candidate_id: SkillCandidateId,
        *,
        reviewer_id: str,
    ) -> SkillCandidate:
        candidate = self._latest(candidate_id)
        if candidate.status is SkillCandidateStatus.CANDIDATE:
            raise SkillEvolutionError("Skill Candidate requires offline evaluation")
        if candidate.status is SkillCandidateStatus.OFFLINE_EVALUATED:
            raise SkillEvolutionError("Skill Candidate requires passing shadow Runs")
        if candidate.status is not SkillCandidateStatus.SHADOW:
            raise SkillEvolutionError("Skill Candidate is not promotable")
        if not reviewer_id.strip():
            raise SkillEvolutionError("Promotion requires a human reviewer")
        reviewer_id = reviewer_id.strip()
        pointer_path = self._root / "active" / f"{candidate.skill_name}.json"
        if pointer_path.exists():
            current = self.active_pointer(candidate.skill_name)
            if current is None or current.version != candidate.base_version:
                raise SkillEvolutionError("Active Skill version differs from Candidate base")
        active = self._transition(
            candidate,
            status=SkillCandidateStatus.ACTIVE,
            reviewer_id=reviewer_id,
        )
        self._append_state(active)
        self._write_pointer(
            pointer_path,
            ActiveSkillPointer(
                skill_name=candidate.skill_name,
                version=candidate.candidate_version,
                candidate_id=candidate.id,
                previous_version=candidate.base_version,
                reviewer_id=reviewer_id,
            ),
        )
        return active

    def rollback(
        self,
        skill_name: str,
        *,
        reviewer_id: str,
        reason: str,
    ) -> SkillCandidate:
        reviewer_id = reviewer_id.strip()
        reason = reason.strip()
        if not reviewer_id:
            raise SkillEvolutionError("Rollback requires a human reviewer")
        if not reason:
            raise SkillEvolutionError("Rollback requires a reason")
        pointer_path = self._root / "active" / f"{skill_name}.json"
        pointer = self.active_pointer(skill_name)
        if pointer is None:
            raise SkillEvolutionError("Active Skill pointer was not found")
        if pointer.candidate_id is None:
            raise SkillEvolutionError("Active Skill pointer does not reference a promotable Candidate")
        candidate = self._latest(pointer.candidate_id)
        if candidate.status is not SkillCandidateStatus.ACTIVE:
            raise SkillEvolutionError("Active Skill Candidate projection is inconsistent")
        rolled_back = self._transition(
            candidate,
            status=SkillCandidateStatus.ROLLED_BACK,
            reviewer_id=reviewer_id,
            rollback_reason=reason,
        )
        self._append_state(rolled_back)
        self._write_pointer(
            pointer_path,
            ActiveSkillPointer(
                skill_name=candidate.skill_name,
                version=candidate.base_version,
                candidate_id=None,
                previous_version=candidate.base_version,
                reviewer_id=pointer.reviewer_id,
                rolled_back_candidate_id=candidate.id,
                rollback_reviewer_id=reviewer_id,
                rollback_reason=reason,
            ),
        )
        return rolled_back

    def active_pointer(self, skill_name: str) -> ActiveSkillPointer | None:
        path = self._root / "active" / f"{skill_name}.json"
        if not path.is_file():
            return None
        try:
            return ActiveSkillPointer.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SkillEvolutionError("Active Skill pointer is invalid") from exc

    def recover_active_pointer(
        self,
        candidate_id: SkillCandidateId,
        *,
        reviewer_id: str,
    ) -> tuple[SkillCandidate, ActiveSkillPointer]:
        candidate = self._latest(candidate_id)
        reviewer_id = reviewer_id.strip()
        if (
            candidate.status is not SkillCandidateStatus.ACTIVE
            or candidate.reviewer_id != reviewer_id
        ):
            raise SkillEvolutionError(
                "Active Skill Candidate does not match the recovery command"
            )
        current = self.active_pointer(candidate.skill_name)
        if current is not None and current.version != candidate.base_version:
            if (
                current.candidate_id == candidate.id
                and current.version == candidate.candidate_version
                and current.reviewer_id == reviewer_id
            ):
                return candidate, current
            raise SkillEvolutionError("Active Skill pointer conflicts with Candidate recovery")
        pointer = ActiveSkillPointer(
            skill_name=candidate.skill_name,
            version=candidate.candidate_version,
            candidate_id=candidate.id,
            previous_version=candidate.base_version,
            reviewer_id=reviewer_id,
        )
        self._write_pointer(
            self._root / "active" / f"{candidate.skill_name}.json",
            pointer,
        )
        return candidate, pointer

    def recover_rollback_pointer(
        self,
        skill_name: str,
        *,
        reviewer_id: str,
        reason: str,
    ) -> tuple[SkillCandidate, ActiveSkillPointer]:
        reviewer_id = reviewer_id.strip()
        reason = reason.strip()
        current = self.active_pointer(skill_name)
        if current is None:
            raise SkillEvolutionError("Rollback recovery requires the prior Active pointer")
        candidate_id = current.rolled_back_candidate_id or current.candidate_id
        if candidate_id is None:
            raise SkillEvolutionError("Rollback recovery pointer has no Candidate identity")
        candidate = self._latest(candidate_id)
        if (
            candidate.status is not SkillCandidateStatus.ROLLED_BACK
            or candidate.reviewer_id != reviewer_id
            or candidate.rollback_reason != reason
        ):
            raise SkillEvolutionError(
                "Rolled-back Skill Candidate does not match the recovery command"
            )
        if current.candidate_id is None:
            if (
                current.rolled_back_candidate_id == candidate.id
                and current.version == candidate.base_version
                and current.rollback_reviewer_id == reviewer_id
                and current.rollback_reason == reason
            ):
                return candidate, current
            raise SkillEvolutionError("Rolled-back Skill pointer conflicts with recovery")
        pointer = ActiveSkillPointer(
            skill_name=candidate.skill_name,
            version=candidate.base_version,
            candidate_id=None,
            previous_version=candidate.base_version,
            reviewer_id=current.reviewer_id,
            rolled_back_candidate_id=candidate.id,
            rollback_reviewer_id=reviewer_id,
            rollback_reason=reason,
        )
        self._write_pointer(
            self._root / "active" / f"{candidate.skill_name}.json",
            pointer,
        )
        return candidate, pointer

    def active_version(self, skill_name: str) -> str | None:
        pointer = self.active_pointer(skill_name)
        return pointer.version if pointer is not None else None

    def _latest(self, candidate_id: SkillCandidateId) -> SkillCandidate:
        state_root = self._root / "states" / str(candidate_id)
        paths = sorted(state_root.glob("*.json"))
        if not paths:
            raise SkillEvolutionError("Skill Candidate was not found")
        return SkillCandidate.model_validate_json(paths[-1].read_text(encoding="utf-8"))

    def _append_state(self, candidate: SkillCandidate) -> Path:
        return self._write_new(
            self._root / "states" / str(candidate.id) / f"{candidate.version:06d}.json",
            candidate.model_dump(mode="json"),
        )

    @staticmethod
    def _transition(
        candidate: SkillCandidate,
        *,
        status: SkillCandidateStatus,
        **updates,
    ) -> SkillCandidate:
        return SkillCandidate.model_validate(
            {
                **candidate.model_dump(mode="python"),
                **updates,
                "status": status,
                "updated_at": datetime.now(UTC),
                "version": candidate.version + 1,
            }
        )

    @staticmethod
    def _write_new(path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        return path

    @staticmethod
    def _write_pointer(path: Path, pointer: ActiveSkillPointer) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                pointer.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return path
