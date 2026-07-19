"""Deterministic projections from Lead claims through fresh Verification."""

from __future__ import annotations

from app.commerce.agents.goal_loop import GoalLoopProgress
from app.commerce.agents.lead import LeadSynthesisResult
from app.commerce.agents.verification import ClaimVerdict, VerificationResult
from app.commerce.domain.enums import HypothesisStatus
from app.commerce.domain.ids import CaseId, WorkspaceId
from app.commerce.domain.models import Hypothesis


def project_proposed_hypotheses(
    *,
    workspace_id: WorkspaceId,
    case_id: CaseId,
    lead: LeadSynthesisResult,
) -> tuple[Hypothesis, ...]:
    """Turn Lead claims into first-class immutable Domain Hypotheses."""

    hypothesis_ids = tuple(claim.hypothesis_id for claim in lead.claims)
    if len(hypothesis_ids) != len(set(hypothesis_ids)):
        raise ValueError("Lead claims must have unique Hypothesis IDs")
    return tuple(
        Hypothesis(
            id=claim.hypothesis_id,
            workspace_id=workspace_id,
            case_id=case_id,
            statement=claim.statement,
            status=HypothesisStatus.PROPOSED,
            confidence=claim.confidence,
            supporting_evidence_ids=claim.evidence_ids,
            version=1,
        )
        for claim in lead.claims
    )


def project_verified_hypotheses(
    proposed: tuple[Hypothesis, ...],
    verification: VerificationResult,
) -> tuple[Hypothesis, ...]:
    """Append one status version per claim without allowing statement rewrites."""

    if len(proposed) != len(verification.claims):
        raise ValueError("Verification must cover every proposed Hypothesis")
    by_index = {claim.claim_index: claim for claim in verification.claims}
    if set(by_index) != set(range(len(proposed))) or len(by_index) != len(
        verification.claims
    ):
        raise ValueError("Verification claim indices must be unique and contiguous")

    verified: list[Hypothesis] = []
    for index, hypothesis in enumerate(proposed):
        verdict = by_index[index]
        if verdict.claim != hypothesis.statement:
            raise ValueError("Verification cannot rewrite a Hypothesis statement")
        status = {
            ClaimVerdict.PASS: HypothesisStatus.SUPPORTED,
            ClaimVerdict.REPAIR: HypothesisStatus.INVESTIGATING,
            ClaimVerdict.REJECT: HypothesisStatus.REJECTED,
        }[verdict.verdict]
        confidence = (
            hypothesis.confidence
            if verdict.verdict is ClaimVerdict.PASS
            else min(hypothesis.confidence, 0.5)
            if verdict.verdict is ClaimVerdict.REPAIR
            else 0.0
        )
        verified.append(
            hypothesis.model_copy(
                update={
                    "status": status,
                    "confidence": confidence,
                    "version": hypothesis.version + 1,
                }
            )
        )
    return tuple(verified)


def verification_goal_progress(
    verification: VerificationResult,
) -> GoalLoopProgress:
    """Map Verification to an explicit achieved or replan-required Loop signal."""

    if verification.overall_verdict is ClaimVerdict.PASS:
        return GoalLoopProgress(goal_achieved=True)
    gaps = tuple(
        f"claim[{claim.claim_index}] {claim.verdict.value}: "
        + ",".join(sorted(code.value for code in claim.issue_codes))
        for claim in verification.claims
        if claim.verdict is not ClaimVerdict.PASS
    )
    return GoalLoopProgress(
        partial_goal_achieved=True,
        verification_replan_required=True,
        remaining_evidence_gaps=gaps,
    )
