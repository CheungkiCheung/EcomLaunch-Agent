"""Capability-first deterministic routing for Commerce Path Agents."""

from __future__ import annotations

from enum import StrEnum

from app.commerce.agents.contracts import (
    PathAgentSpec,
    PathType,
    default_path_agent_specs,
)
from app.commerce.data.capabilities import (
    CapabilityProfile,
    CapabilityStatus,
)
from app.commerce.domain.models import CommerceModel
from app.commerce.metrics.registry import MetricName


class RouteReasonCode(StrEnum):
    SELECTED_SIGNAL_MATCH = "selected_signal_match"
    SELECTED_EXPLICIT_REQUEST = "selected_explicit_request"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    NO_RELEVANT_SIGNAL = "no_relevant_signal"


class CaseSignalSummary(CommerceModel):
    metric_names: frozenset[MetricName] = frozenset()
    requested_paths: frozenset[PathType] = frozenset()


class PathRouteDecision(CommerceModel):
    path_type: PathType
    selected: bool
    reason_codes: frozenset[RouteReasonCode]


class PathAssignment(CommerceModel):
    path_type: PathType
    spec: PathAgentSpec


class DynamicPathPlan(CommerceModel):
    assignments: tuple[PathAssignment, ...]
    decisions: tuple[PathRouteDecision, ...]

    def decision(self, path_type: PathType) -> PathRouteDecision:
        for decision in self.decisions:
            if decision.path_type is path_type:
                return decision
        raise KeyError(path_type.value)


_RELEVANT_METRICS = {
    PathType.FULFILLMENT: frozenset(
        {
            MetricName.LATE_DELIVERY_RATE,
            MetricName.HANDLING_TIME_HOURS,
            MetricName.TRANSIT_TIME_HOURS,
            MetricName.DELIVERY_DURATION_HOURS,
        }
    ),
    PathType.SELLER_PEER: frozenset({MetricName.PEER_LATE_DELIVERY_RATE}),
    PathType.REVIEW_EXPERIENCE: frozenset(
        {MetricName.AVERAGE_REVIEW_SCORE, MetricName.LOW_RATING_RATE}
    ),
}


class DynamicPathRouter:
    """Route zero to three independent evidence paths using rules first."""

    def __init__(self, specs: tuple[PathAgentSpec, ...] | None = None) -> None:
        self._specs = specs or default_path_agent_specs()

    def route(
        self,
        capabilities: CapabilityProfile,
        signals: CaseSignalSummary,
    ) -> DynamicPathPlan:
        assignments: list[PathAssignment] = []
        decisions: list[PathRouteDecision] = []
        for spec in self._specs:
            unavailable = any(
                capabilities.capability(capability).status
                is CapabilityStatus.UNAVAILABLE
                for capability in spec.required_capabilities
            )
            if unavailable:
                decisions.append(
                    PathRouteDecision(
                        path_type=spec.path_type,
                        selected=False,
                        reason_codes=frozenset(
                            {RouteReasonCode.CAPABILITY_UNAVAILABLE}
                        ),
                    )
                )
                continue

            explicit = spec.path_type in signals.requested_paths
            signal_match = bool(
                signals.metric_names & _RELEVANT_METRICS[spec.path_type]
            )
            if not explicit and not signal_match:
                decisions.append(
                    PathRouteDecision(
                        path_type=spec.path_type,
                        selected=False,
                        reason_codes=frozenset({RouteReasonCode.NO_RELEVANT_SIGNAL}),
                    )
                )
                continue

            reasons = {
                RouteReasonCode.SELECTED_EXPLICIT_REQUEST
                if explicit
                else RouteReasonCode.SELECTED_SIGNAL_MATCH
            }
            assignments.append(PathAssignment(path_type=spec.path_type, spec=spec))
            decisions.append(
                PathRouteDecision(
                    path_type=spec.path_type,
                    selected=True,
                    reason_codes=frozenset(reasons),
                )
            )
        return DynamicPathPlan(
            assignments=tuple(assignments[:3]),
            decisions=tuple(decisions),
        )
