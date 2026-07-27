"""Fail-closed deterministic validation for model- or user-proposed Actions."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import StrEnum

from app.commerce.actions.contracts import (
    ActionDraft,
    MetricMonitorParameters,
    ValidatedActionDraft,
)
from app.commerce.agents.contracts import LeadContextPacket
from app.commerce.domain.enums import HypothesisStatus, SemanticStatus


class ActionValidationReason(StrEnum):
    IDENTITY_MISMATCH = "identity_mismatch"
    EVIDENCE_OUTSIDE_CONTEXT = "evidence_outside_context"
    HYPOTHESIS_OUTSIDE_CONTEXT = "hypothesis_outside_context"
    HYPOTHESIS_NOT_VERIFIED = "hypothesis_not_verified"
    HYPOTHESIS_EVIDENCE_MISMATCH = "hypothesis_evidence_mismatch"
    METRIC_OUTSIDE_CONTEXT = "metric_outside_context"
    METRIC_NOT_EVIDENCED = "metric_not_evidenced"
    METRIC_NAME_MISMATCH = "metric_name_mismatch"
    INVALID_THRESHOLD = "invalid_threshold"


class ActionValidationError(ValueError):
    def __init__(self, reason: ActionValidationReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class ActionValidator:
    """Validate identity, evidence, verified hypotheses, metrics, and preconditions."""

    def validate(
        self,
        draft: ActionDraft,
        context: LeadContextPacket,
    ) -> ValidatedActionDraft:
        if (
            draft.workspace_id != context.case.workspace_id
            or draft.case_id != context.case.case_id
        ):
            raise ActionValidationError(
                ActionValidationReason.IDENTITY_MISMATCH,
                "Action Draft must belong to the supplied Case context",
            )
        evidence_by_id = {item.evidence_id: item for item in context.evidence}
        if not set(draft.evidence_ids).issubset(evidence_by_id):
            raise ActionValidationError(
                ActionValidationReason.EVIDENCE_OUTSIDE_CONTEXT,
                "Action references Evidence outside the persisted context",
            )
        hypotheses_by_id = {
            item.hypothesis_id: item for item in context.hypotheses
        }
        if not set(draft.hypothesis_ids).issubset(hypotheses_by_id):
            raise ActionValidationError(
                ActionValidationReason.HYPOTHESIS_OUTSIDE_CONTEXT,
                "Action references Hypotheses outside the persisted context",
            )
        selected_hypotheses = tuple(
            hypotheses_by_id[value] for value in draft.hypothesis_ids
        )
        if any(
            item.status != HypothesisStatus.SUPPORTED.value
            for item in selected_hypotheses
        ):
            raise ActionValidationError(
                ActionValidationReason.HYPOTHESIS_NOT_VERIFIED,
                "Action requires fresh-verified supported Hypotheses",
            )
        selected_evidence = set(draft.evidence_ids)
        if any(
            not set(item.evidence_ids).issubset(selected_evidence)
            for item in selected_hypotheses
        ):
            raise ActionValidationError(
                ActionValidationReason.HYPOTHESIS_EVIDENCE_MISMATCH,
                "Action Evidence must cover every selected Hypothesis",
            )

        metrics = {
            item.metric_observation_id: item
            for item in (
                *context.analysis.baseline_metrics,
                *context.analysis.current_metrics,
                *context.analysis.supplemental_metrics,
            )
        }
        expected_ids = set(draft.expected_signal_metric_ids)
        if not expected_ids.issubset(metrics) or not expected_ids.issubset(
            context.manifest.included_metric_observation_ids
        ):
            raise ActionValidationError(
                ActionValidationReason.METRIC_OUTSIDE_CONTEXT,
                "Action expected signals reference Metrics outside context",
            )
        evidenced_metric_ids = {
            metric_id
            for evidence_id in draft.evidence_ids
            for metric_id in evidence_by_id[evidence_id].metric_observation_ids
        }
        if not expected_ids.issubset(evidenced_metric_ids):
            raise ActionValidationError(
                ActionValidationReason.METRIC_NOT_EVIDENCED,
                "Action expected signals must be cited by selected Evidence",
            )
        if isinstance(draft.parameters, MetricMonitorParameters):
            parameter_ids = set(draft.parameters.metric_observation_ids)
            if not parameter_ids.issubset(metrics):
                raise ActionValidationError(
                    ActionValidationReason.METRIC_OUTSIDE_CONTEXT,
                    "Metric monitor references Metrics outside context",
                )
            if parameter_ids != expected_ids:
                raise ActionValidationError(
                    ActionValidationReason.METRIC_NOT_EVIDENCED,
                    "Metric monitor references must equal expected signals",
                )
            monitored = tuple(metrics[value] for value in parameter_ids)
            if any(
                item.metric_name != draft.parameters.metric_name
                or item.semantic_status
                in {SemanticStatus.UNKNOWN, SemanticStatus.BLOCKED}
                for item in monitored
            ):
                raise ActionValidationError(
                    ActionValidationReason.METRIC_NAME_MISMATCH,
                    "Metric monitor name must match known deterministic Metrics",
                )
            if any(item.unit == "ratio" for item in monitored) and not (
                Decimal("0") <= draft.parameters.threshold <= Decimal("1")
            ):
                raise ActionValidationError(
                    ActionValidationReason.INVALID_THRESHOLD,
                    "Ratio monitor threshold must be between zero and one",
                )

        validation_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "draft": draft.model_dump(mode="json"),
                    "context_sha256": context.manifest.context_sha256,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return ValidatedActionDraft(
            draft=draft,
            validation_sha256=validation_sha256,
        )
