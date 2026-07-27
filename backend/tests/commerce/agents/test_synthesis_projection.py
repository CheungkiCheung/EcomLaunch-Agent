"""Deterministic Lead claim, Verification, and Hypothesis projections."""

from __future__ import annotations

from app.commerce.agents.claim_policy import unsupported_causal_phrases
from app.commerce.agents.lead import LeadClaim, LeadSynthesisResult
from app.commerce.agents.synthesis import (
    project_proposed_hypotheses,
    project_verified_hypotheses,
    verification_goal_progress,
)
from app.commerce.agents.verification import (
    ClaimVerdict,
    ClaimVerification,
    VerificationIssueCode,
    VerificationResult,
)
from app.commerce.domain.enums import HypothesisStatus
from app.commerce.domain.ids import (
    CaseId,
    EvidenceId,
    HypothesisId,
    MetricObservationId,
    WorkspaceId,
)


def _lead_result() -> LeadSynthesisResult:
    return LeadSynthesisResult(
        claims=(
            LeadClaim(
                hypothesis_id=HypothesisId.new(),
                statement="Seller handling did not worsen in the current window.",
                confidence=0.91,
                evidence_ids=(EvidenceId.new(),),
            ),
            LeadClaim(
                hypothesis_id=HypothesisId.new(),
                statement="Carrier transit time worsened in the current window.",
                confidence=0.94,
                evidence_ids=(EvidenceId.new(),),
            ),
        ),
        context_sha256="a" * 64,
    )


def _verification(
    lead: LeadSynthesisResult,
    verdicts: tuple[ClaimVerdict, ...],
) -> VerificationResult:
    claims = tuple(
        ClaimVerification(
            claim_index=index,
            claim=lead_claim.statement,
            verdict=verdict,
            issue_codes=(
                frozenset()
                if verdict is ClaimVerdict.PASS
                else frozenset({VerificationIssueCode.MISSING_EVIDENCE})
            ),
            reason=(
                "Supported by the supplied deterministic metrics."
                if verdict is ClaimVerdict.PASS
                else "The supplied evidence is not sufficient for this claim."
            ),
            evidence_ids=lead_claim.evidence_ids,
            metric_observation_ids=(MetricObservationId.new(),),
        )
        for index, (lead_claim, verdict) in enumerate(zip(lead.claims, verdicts, strict=True))
    )
    overall = (
        ClaimVerdict.REJECT
        if ClaimVerdict.REJECT in verdicts
        else ClaimVerdict.REPAIR
        if ClaimVerdict.REPAIR in verdicts
        else ClaimVerdict.PASS
    )
    return VerificationResult(
        overall_verdict=overall,
        claims=claims,
        context_sha256="b" * 64,
    )


def test_lead_claims_become_traceable_proposed_hypotheses():
    workspace_id = WorkspaceId.new()
    case_id = CaseId.new()
    lead = _lead_result()

    hypotheses = project_proposed_hypotheses(
        workspace_id=workspace_id,
        case_id=case_id,
        lead=lead,
    )

    assert tuple(item.id for item in hypotheses) == tuple(
        claim.hypothesis_id for claim in lead.claims
    )
    assert all(item.status is HypothesisStatus.PROPOSED for item in hypotheses)
    assert tuple(item.supporting_evidence_ids for item in hypotheses) == tuple(
        claim.evidence_ids for claim in lead.claims
    )
    assert all(item.version == 1 for item in hypotheses)


def test_verification_creates_contiguous_status_versions_without_rewriting_claims():
    lead = _lead_result()
    proposed = project_proposed_hypotheses(
        workspace_id=WorkspaceId.new(),
        case_id=CaseId.new(),
        lead=lead,
    )
    verification = _verification(
        lead,
        (ClaimVerdict.PASS, ClaimVerdict.REJECT),
    )

    verified = project_verified_hypotheses(proposed, verification)

    assert tuple(item.statement for item in verified) == tuple(
        item.statement for item in proposed
    )
    assert tuple(item.version for item in verified) == (2, 2)
    assert tuple(item.status for item in verified) == (
        HypothesisStatus.SUPPORTED,
        HypothesisStatus.REJECTED,
    )
    assert verified[0].confidence == proposed[0].confidence
    assert verified[1].confidence == 0


def test_non_pass_verification_requires_explicit_replan_while_pass_achieves_goal():
    lead = _lead_result()
    passed = verification_goal_progress(
        _verification(lead, (ClaimVerdict.PASS, ClaimVerdict.PASS))
    )
    rejected = verification_goal_progress(
        _verification(lead, (ClaimVerdict.PASS, ClaimVerdict.REJECT))
    )

    assert passed.goal_achieved is True
    assert passed.verification_replan_required is False
    assert rejected.goal_achieved is False
    assert rejected.partial_goal_achieved is True
    assert rejected.verification_replan_required is True
    assert rejected.remaining_evidence_gaps


def test_diagnostic_claim_policy_rejects_causal_overclaim_markers():
    assert unsupported_causal_phrases(
        "The delay was driven primarily by carrier transit."
    ) == ("driven primarily by",)
    assert unsupported_causal_phrases(
        "Delivery duration is attributable to the transit increase."
    ) == ("attributable to",)
    assert unsupported_causal_phrases(
        "Transit increased, indicating carrier performance worsened."
    ) == ("indicating",)
    assert not unsupported_causal_phrases(
        "Observed deterioration is concentrated in transit rather than handling."
    )
