"""Deterministic metric analysis and anomaly-to-Case application service."""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.api.data_service import CommerceDataService
from app.commerce.data.capabilities import CapabilityProfile
from app.commerce.domain.enums import CaseSeverity, CaseStatus, SemanticStatus
from app.commerce.domain.events import DomainEventActor
from app.commerce.domain.ids import (
    CaseId,
    CorrelationId,
    DatasetId,
    EvidenceId,
    TraceId,
    WorkspaceId,
)
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import Case, CommerceModel, Evidence, EvidenceRelation
from app.commerce.metrics.anomaly import (
    AnomalyDetector,
    AnomalySeverity,
    AnomalySignal,
    CaseCandidate,
    build_case_candidate,
)
from app.commerce.metrics.registry import (
    MetricEngine,
    MetricSnapshot,
    MetricWindow,
)
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import DuplicateEntityError, SqlCaseRepository
from app.commerce.persistence.unit_of_work import SqlCommerceUnitOfWork


class AnalysisSkip(CommerceModel):
    seller_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class AnalysisOutcome(CommerceModel):
    dataset_id: str
    workspace_id: WorkspaceId
    baseline_window: MetricWindow
    current_window: MetricWindow
    signals: tuple[AnomalySignal, ...]
    cases: tuple[Case, ...]
    skipped_sellers: tuple[AnalysisSkip, ...] = ()


class CommerceAnalysisService:
    """Run deterministic metric analysis and persist anomaly Cases atomically."""

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._data = data_service
        self._session_factory = session_factory
        self._engine = MetricEngine()
        self._detector = AnomalyDetector()

    async def analyze(
        self,
        workspace_id: WorkspaceId,
        dataset_id,
        *,
        baseline_window: MetricWindow,
        current_window: MetricWindow,
        seller_id: str | None = None,
    ) -> AnalysisOutcome:
        view = self._data.get_view(workspace_id, dataset_id)
        normalized = self._data.normalize(workspace_id, dataset_id)
        seller_ids = tuple(
            sorted(
                {
                    entity.external_key
                    for entity in normalized.entities
                    if entity.entity_type.value == "seller"
                }
            )
        )
        if seller_id is not None:
            if seller_id not in seller_ids:
                raise ValueError(f"Unknown seller in Dataset: {seller_id}")
            seller_ids = (seller_id,)

        all_signals: list[AnomalySignal] = []
        cases: list[Case] = []
        skipped: list[AnalysisSkip] = []
        artifact_sellers: list[dict] = []
        for current_seller_id in seller_ids:
            try:
                baseline = self._engine.compute_seller_window(
                    normalized,
                    seller_id=current_seller_id,
                    window=baseline_window,
                )
                current = self._engine.compute_seller_window(
                    normalized,
                    seller_id=current_seller_id,
                    window=current_window,
                )
                signals = self._detector.detect(baseline, current)
            except (KeyError, ValueError) as exc:
                skipped.append(
                    AnalysisSkip(seller_id=current_seller_id, reason=str(exc))
                )
                continue
            artifact_sellers.append(
                {
                    "seller_id": current_seller_id,
                    "baseline": baseline.model_dump(mode="json"),
                    "current": current.model_dump(mode="json"),
                    "signal_ids": [str(signal.id) for signal in signals],
                }
            )
            if not signals:
                continue
            candidate = build_case_candidate(current, signals)
            case = await self._persist_candidate(
                workspace_id,
                dataset_id,
                candidate,
                signals,
                baseline,
                current,
                view.capabilities,
            )
            all_signals.extend(signals)
            cases.append(case)

        artifact_payload = {
            "schema_version": "1.0",
            "dataset_id": str(dataset_id),
            "workspace_id": str(workspace_id),
            "baseline_window": baseline_window.model_dump(mode="json"),
            "current_window": current_window.model_dump(mode="json"),
            "sellers": artifact_sellers,
            "case_ids": [str(case.id) for case in cases],
        }
        artifact_key = hashlib.sha256(
            json.dumps(artifact_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        self._data.write_derived_artifact(
            workspace_id,
            dataset_id,
            filename=f"analysis-{artifact_key}.json",
            payload=artifact_payload,
        )
        return AnalysisOutcome(
            dataset_id=str(dataset_id),
            workspace_id=workspace_id,
            baseline_window=baseline_window,
            current_window=current_window,
            signals=tuple(all_signals),
            cases=tuple(cases),
            skipped_sellers=tuple(skipped),
        )

    async def _persist_candidate(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        candidate: CaseCandidate,
        signals: tuple[AnomalySignal, ...],
        baseline: MetricSnapshot,
        current: MetricSnapshot,
        capabilities: CapabilityProfile,
    ) -> Case:
        repository = SqlCaseRepository(self._session_factory)
        lineage_repository = SqlCaseLineageRepository(self._session_factory)
        persisted_case_id = CaseId(
            f"case_{uuid5(NAMESPACE_URL, f'{dataset_id}:{candidate.fingerprint}').hex}"
        )
        context_payload = {
            "schema_version": "commerce.case-analysis-context@1.0.0",
            "workspace_id": str(workspace_id),
            "dataset_id": str(dataset_id),
            "case_id": str(persisted_case_id),
            "seller_external_key": current.seller_id,
            "seller_entity_id": str(current.seller_entity_id),
            "baseline": baseline.model_dump(mode="json"),
            "current": current.model_dump(mode="json"),
            "signals": [signal.model_dump(mode="json") for signal in signals],
            "capabilities": capabilities.model_dump(mode="json"),
        }
        context_key = hashlib.sha256(
            json.dumps(context_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        context_filename = f"case-context-{context_key}.json"
        context_path = self._data.write_derived_artifact(
            workspace_id,
            dataset_id,
            filename=context_filename,
            payload=context_payload,
        )
        lineage = CaseLineage(
            workspace_id=workspace_id,
            case_id=persisted_case_id,
            dataset_id=dataset_id,
            seller_entity_id=current.seller_entity_id,
            seller_external_key=current.seller_id,
            baseline_start=baseline.window.start,
            baseline_end=baseline.window.end,
            current_start=current.window.start,
            current_end=current.window.end,
            anomaly_ids=tuple(signal.id for signal in signals),
            metric_observation_ids=tuple(
                dict.fromkeys(
                    observation_id
                    for signal in signals
                    for observation_id in (
                        signal.baseline_observation_id,
                        signal.current_observation_id,
                    )
                )
            ),
            analysis_artifact_relative_path=f"derived/{context_filename}",
            analysis_artifact_sha256=hashlib.sha256(
                context_path.read_bytes()
            ).hexdigest(),
            created_at=candidate.window.end,
        )
        existing = await repository.get(workspace_id, persisted_case_id)
        if existing is not None:
            if await lineage_repository.get(workspace_id, persisted_case_id) is None:
                try:
                    await SqlCommerceUnitOfWork(
                        self._session_factory
                    ).attach_case_lineage(
                        lineage,
                        trace_id=TraceId.new(),
                        correlation_id=CorrelationId.new(),
                        actor=DomainEventActor.SYSTEM,
                    )
                except DuplicateEntityError:
                    pass
            return existing

        case = Case(
            id=persisted_case_id,
            workspace_id=workspace_id,
            title=(
                f"Deterministic anomaly for seller {candidate.seller_entity_id}"
            ),
            severity=self._case_severity(candidate.severity),
            status=CaseStatus.NEW,
            summary=(
                f"Dataset {dataset_id} produced {len(signals)} anomaly signal(s) "
                f"for metrics: {', '.join(sorted(candidate.metric_names))}. "
                "This is a diagnostic signal, not a causal claim."
            ),
            opened_at=candidate.window.end,
            updated_at=candidate.window.end,
        )
        trace_id = TraceId.new()
        correlation_id = CorrelationId.new()
        uow = SqlCommerceUnitOfWork(self._session_factory)
        try:
            created_event = await uow.create_case_with_lineage(
                case,
                lineage,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.SYSTEM,
            )
        except DuplicateEntityError:
            persisted = await repository.get(workspace_id, case.id)
            if persisted is None:
                raise
            return persisted

        current_case = case
        for signal in signals:
            evidence = Evidence(
                id=EvidenceId(
                    f"evd_{uuid5(NAMESPACE_URL, f'{case.id}:{signal.id}').hex}"
                ),
                workspace_id=workspace_id,
                case_id=case.id,
                summary=(
                    f"{signal.metric_name} changed from {signal.baseline_value} "
                    f"to {signal.current_value}: {signal.reason}"
                ),
                relation=EvidenceRelation.SUPPORTS,
                semantic_status=SemanticStatus.DERIVED,
                confidence=signal.confidence,
                metric_observation_ids=(
                    signal.baseline_observation_id,
                    signal.current_observation_id,
                ),
            )
            updated_case = current_case.model_copy(
                update={
                    "evidence_ids": (*current_case.evidence_ids, evidence.id),
                    "version": current_case.version + 1,
                }
            )
            await uow.append_evidence(
                updated_case,
                evidence,
                expected_version=current_case.version,
                trace_id=trace_id,
                correlation_id=correlation_id,
                actor=DomainEventActor.SYSTEM,
                causation_event_id=created_event.id,
            )
            current_case = updated_case
        return current_case

    @staticmethod
    def _case_severity(severity: AnomalySeverity) -> CaseSeverity:
        return {
            AnomalySeverity.INFO: CaseSeverity.LOW,
            AnomalySeverity.LOW: CaseSeverity.LOW,
            AnomalySeverity.MEDIUM: CaseSeverity.MEDIUM,
            AnomalySeverity.HIGH: CaseSeverity.HIGH,
            AnomalySeverity.CRITICAL: CaseSeverity.CRITICAL,
        }[severity]
