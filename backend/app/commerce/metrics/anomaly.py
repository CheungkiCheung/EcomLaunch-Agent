"""Metric-aware anomaly detection and deterministic Case candidate merging."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from app.commerce.domain.enums import SemanticStatus
from app.commerce.domain.ids import AnomalyId, CaseId, EntityId, MetricObservationId
from app.commerce.metrics.registry import MetricName, MetricSnapshot, MetricWindow


class AnomalySeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {
            AnomalySeverity.INFO: 0,
            AnomalySeverity.LOW: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.HIGH: 3,
            AnomalySeverity.CRITICAL: 4,
        }[self]


class AnomalyDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"


class AnomalyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnomalyRule(AnomalyModel):
    metric_name: MetricName
    adverse_direction: AnomalyDirection
    medium_threshold: Decimal
    high_threshold: Decimal
    critical_threshold: Decimal
    minimum_sample_size: int = Field(ge=1)


class AnomalySignal(AnomalyModel):
    id: AnomalyId
    seller_entity_id: EntityId
    metric_name: MetricName
    baseline_observation_id: MetricObservationId
    current_observation_id: MetricObservationId
    baseline_value: Decimal
    current_value: Decimal
    absolute_change: Decimal
    relative_change: Decimal | None
    direction: AnomalyDirection
    severity: AnomalySeverity
    confidence: float = Field(ge=0.0, le=1.0)
    baseline_sample_size: int = Field(ge=0)
    current_sample_size: int = Field(ge=0)
    sample_adequate: bool
    current_window: MetricWindow
    reason: str = Field(min_length=1)


class CaseCandidate(AnomalyModel):
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    suggested_case_id: CaseId
    seller_entity_id: EntityId
    window: MetricWindow
    signal_ids: tuple[AnomalyId, ...] = Field(min_length=1)
    metric_names: frozenset[MetricName] = Field(min_length=1)
    severity: AnomalySeverity
    confidence: float = Field(ge=0.0, le=1.0)
    version: int = Field(default=1, ge=1)

    def merge(self, incoming: Self) -> Self:
        if self.fingerprint != incoming.fingerprint:
            raise ValueError("Cannot merge Case candidates with different fingerprints")
        severity = self.severity if self.severity.rank >= incoming.severity.rank else incoming.severity
        return self.model_copy(
            update={
                "signal_ids": tuple(dict.fromkeys((*self.signal_ids, *incoming.signal_ids))),
                "metric_names": self.metric_names | incoming.metric_names,
                "severity": severity,
                "confidence": max(self.confidence, incoming.confidence),
                "version": self.version + 1,
            }
        )


class AnomalyDetector:
    """Apply metric-specific adverse-direction thresholds with sample gates."""

    RULES = (
        AnomalyRule(
            metric_name=MetricName.LATE_DELIVERY_RATE,
            adverse_direction=AnomalyDirection.INCREASE,
            medium_threshold=Decimal("0.05"),
            high_threshold=Decimal("0.15"),
            critical_threshold=Decimal("0.30"),
            minimum_sample_size=15,
        ),
        AnomalyRule(
            metric_name=MetricName.AVERAGE_REVIEW_SCORE,
            adverse_direction=AnomalyDirection.DECREASE,
            medium_threshold=Decimal("0.30"),
            high_threshold=Decimal("0.60"),
            critical_threshold=Decimal("1.20"),
            minimum_sample_size=15,
        ),
        AnomalyRule(
            metric_name=MetricName.LOW_RATING_RATE,
            adverse_direction=AnomalyDirection.INCREASE,
            medium_threshold=Decimal("0.10"),
            high_threshold=Decimal("0.20"),
            critical_threshold=Decimal("0.40"),
            minimum_sample_size=15,
        ),
        AnomalyRule(
            metric_name=MetricName.HANDLING_TIME_HOURS,
            adverse_direction=AnomalyDirection.INCREASE,
            medium_threshold=Decimal("12"),
            high_threshold=Decimal("48"),
            critical_threshold=Decimal("96"),
            minimum_sample_size=15,
        ),
        AnomalyRule(
            metric_name=MetricName.TRANSIT_TIME_HOURS,
            adverse_direction=AnomalyDirection.INCREASE,
            medium_threshold=Decimal("24"),
            high_threshold=Decimal("96"),
            critical_threshold=Decimal("192"),
            minimum_sample_size=15,
        ),
        AnomalyRule(
            metric_name=MetricName.DELIVERY_DURATION_HOURS,
            adverse_direction=AnomalyDirection.INCREASE,
            medium_threshold=Decimal("24"),
            high_threshold=Decimal("96"),
            critical_threshold=Decimal("192"),
            minimum_sample_size=15,
        ),
    )

    def detect(self, baseline: MetricSnapshot, current: MetricSnapshot) -> tuple[AnomalySignal, ...]:
        if baseline.seller_id != current.seller_id:
            raise ValueError("Baseline and current snapshots must belong to the same seller")

        baseline_metrics = {observation.metric_name: observation for observation in baseline.observations}
        current_metrics = {observation.metric_name: observation for observation in current.observations}
        signals: list[AnomalySignal] = []

        for rule in self.RULES:
            baseline_observation = baseline_metrics.get(rule.metric_name.value)
            current_observation = current_metrics.get(rule.metric_name.value)
            if baseline_observation is None or current_observation is None:
                continue
            if (
                baseline_observation.semantic_status is not SemanticStatus.DERIVED
                or current_observation.semantic_status is not SemanticStatus.DERIVED
                or baseline_observation.value is None
                or current_observation.value is None
            ):
                continue

            baseline_value = Decimal(str(baseline_observation.value))
            current_value = Decimal(str(current_observation.value))
            change = current_value - baseline_value
            adverse_change = change if rule.adverse_direction is AnomalyDirection.INCREASE else -change
            if adverse_change < rule.medium_threshold:
                continue

            severity = self._severity(rule, adverse_change)
            baseline_sample = baseline_observation.sample_size or 0
            current_sample = current_observation.sample_size or 0
            minimum_sample = min(baseline_sample, current_sample)
            sample_adequate = minimum_sample >= rule.minimum_sample_size
            if not sample_adequate:
                severity = AnomalySeverity.LOW
            confidence = self._confidence(severity, minimum_sample, rule.minimum_sample_size, sample_adequate)
            direction = AnomalyDirection.INCREASE if change >= 0 else AnomalyDirection.DECREASE
            relative_change = None if baseline_value == 0 else change / abs(baseline_value)
            key = (
                f"{current.seller_id}:{rule.metric_name.value}:"
                f"{current.window.start.isoformat()}:{current.window.end.isoformat()}"
            )
            signals.append(
                AnomalySignal(
                    id=AnomalyId(f"anom_{uuid5(NAMESPACE_URL, key).hex}"),
                    seller_entity_id=current.seller_entity_id,
                    metric_name=rule.metric_name,
                    baseline_observation_id=baseline_observation.id,
                    current_observation_id=current_observation.id,
                    baseline_value=baseline_value,
                    current_value=current_value,
                    absolute_change=change,
                    relative_change=relative_change,
                    direction=direction,
                    severity=severity,
                    confidence=confidence,
                    baseline_sample_size=baseline_sample,
                    current_sample_size=current_sample,
                    sample_adequate=sample_adequate,
                    current_window=current.window,
                    reason=(
                        f"{rule.metric_name.value} moved {direction.value} by {abs(change)}; "
                        f"adverse threshold={rule.medium_threshold}."
                    ),
                )
            )
        return tuple(signals)

    @staticmethod
    def _severity(rule: AnomalyRule, adverse_change: Decimal) -> AnomalySeverity:
        if adverse_change >= rule.critical_threshold:
            return AnomalySeverity.CRITICAL
        if adverse_change >= rule.high_threshold:
            return AnomalySeverity.HIGH
        return AnomalySeverity.MEDIUM

    @staticmethod
    def _confidence(
        severity: AnomalySeverity,
        sample_size: int,
        minimum_sample_size: int,
        sample_adequate: bool,
    ) -> float:
        base = {
            AnomalySeverity.INFO: 0.2,
            AnomalySeverity.LOW: 0.4,
            AnomalySeverity.MEDIUM: 0.65,
            AnomalySeverity.HIGH: 0.85,
            AnomalySeverity.CRITICAL: 0.95,
        }[severity]
        if sample_adequate:
            return base
        sample_factor = min(1.0, sample_size / minimum_sample_size)
        return min(0.4, base * sample_factor)


def build_case_candidate(snapshot: MetricSnapshot, signals: tuple[AnomalySignal, ...]) -> CaseCandidate:
    if not signals:
        raise ValueError("At least one anomaly signal is required")
    if any(signal.seller_entity_id != snapshot.seller_entity_id for signal in signals):
        raise ValueError("All anomaly signals must belong to the snapshot seller")
    if any(signal.current_window != snapshot.window for signal in signals):
        raise ValueError("All anomaly signals must belong to the snapshot window")

    raw_fingerprint = (
        f"{snapshot.seller_id}:{snapshot.window.start.isoformat()}:{snapshot.window.end.isoformat()}"
    )
    fingerprint = hashlib.sha256(raw_fingerprint.encode()).hexdigest()
    severity = max((signal.severity for signal in signals), key=lambda item: item.rank)
    return CaseCandidate(
        fingerprint=fingerprint,
        suggested_case_id=CaseId(f"case_{uuid5(NAMESPACE_URL, f'commerce-case:{fingerprint}').hex}"),
        seller_entity_id=snapshot.seller_entity_id,
        window=snapshot.window,
        signal_ids=tuple(dict.fromkeys(signal.id for signal in signals)),
        metric_names=frozenset(signal.metric_name for signal in signals),
        severity=severity,
        confidence=max(signal.confidence for signal in signals),
    )
