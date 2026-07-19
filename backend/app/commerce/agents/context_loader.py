"""Fail-closed loading of persisted Commerce Case state into initial Agent context."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

from pydantic import Field, SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.budget import BudgetSnapshot, BudgetUsage
from app.commerce.agents.contracts import (
    AgentBudgetLimit,
    AnomalyDigest,
    CaseAnalysisDigest,
    CaseHeader,
    ContextManifest,
    EvidenceDigest,
    HypothesisDigest,
    LeadContextPacket,
    MetricObservationDigest,
    canonical_context_sha256,
    estimate_context_tokens,
    hidden_evaluation_label_paths,
)
from app.commerce.agents.goal_loop import GoalLoopCheckpoint, GoalLoopState
from app.commerce.api.data_service import (
    CommerceDataService,
    DatasetNotFoundError,
    DatasetView,
)
from app.commerce.data.capabilities import CapabilityProfile, CapabilityStatus
from app.commerce.data.intake import DataIntakeError
from app.commerce.domain.enums import RunStatus, RunType
from app.commerce.domain.ids import (
    CaseId,
    DatasetId,
    EntityId,
    FactId,
    MetricObservationId,
    RunId,
    WorkspaceId,
)
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import (
    Case,
    CommerceModel,
    Evidence,
    Hypothesis,
    MetricObservation,
)
from app.commerce.domain.runs import CommerceRun
from app.commerce.metrics.anomaly import AnomalySignal
from app.commerce.metrics.registry import MetricSnapshot
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import SqlCaseRepository
from app.commerce.persistence.runs import (
    SqlRunCheckpointRepository,
    SqlRunRepository,
)
from app.commerce.persistence.work_records import (
    SqlEvidenceRepository,
    SqlHypothesisRepository,
)


class ContextLoadReason(StrEnum):
    RUN_NOT_FOUND = "run_not_found"
    RUN_NOT_EXECUTABLE = "run_not_executable"
    CHECKPOINT_ALREADY_EXISTS = "checkpoint_already_exists"
    CASE_NOT_FOUND = "case_not_found"
    LINEAGE_NOT_FOUND = "lineage_not_found"
    LINEAGE_INVALID = "lineage_invalid"
    DATASET_MANIFEST_NOT_FOUND = "dataset_manifest_not_found"
    DATASET_MANIFEST_INVALID = "dataset_manifest_invalid"
    DATASET_IDENTITY_MISMATCH = "dataset_identity_mismatch"
    ARTIFACT_PATH_UNSAFE = "artifact_path_unsafe"
    ARTIFACT_NOT_FOUND = "artifact_not_found"
    ARTIFACT_HASH_MISMATCH = "artifact_hash_mismatch"
    ARTIFACT_INVALID = "artifact_invalid"
    ARTIFACT_IDENTITY_MISMATCH = "artifact_identity_mismatch"
    CAPABILITY_MISMATCH = "capability_mismatch"
    CASE_REFERENCE_MISMATCH = "case_reference_mismatch"
    HIDDEN_EVALUATION_LABEL = "hidden_evaluation_label"
    CONTEXT_BUDGET_EXCEEDED = "context_budget_exceeded"


class ContextLoadError(RuntimeError):
    def __init__(self, reason: ContextLoadReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class CaseAnalysisArtifact(CommerceModel):
    """Strict persisted artifact schema written by deterministic analysis."""

    schema_version: str = Field(
        pattern=r"^commerce\.case-analysis-context@[0-9]+\.[0-9]+\.[0-9]+$"
    )
    workspace_id: WorkspaceId
    dataset_id: DatasetId
    case_id: CaseId
    seller_external_key: str = Field(min_length=1)
    seller_entity_id: EntityId
    baseline: MetricSnapshot
    current: MetricSnapshot
    signals: tuple[AnomalySignal, ...] = Field(min_length=1)
    capabilities: CapabilityProfile


class InitialContextLoad(CommerceModel):
    run: CommerceRun
    packet: LeadContextPacket
    state: GoalLoopState
    checkpoint: GoalLoopCheckpoint


class ContextPacketLoader:
    """Build canonical minimal context only from verified persisted state."""

    def __init__(
        self,
        *,
        data_service: CommerceDataService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._data = data_service
        self._cases = SqlCaseRepository(session_factory)
        self._lineage = SqlCaseLineageRepository(session_factory)
        self._evidence = SqlEvidenceRepository(session_factory)
        self._hypotheses = SqlHypothesisRepository(session_factory)
        self._runs = SqlRunRepository(session_factory)
        self._checkpoints = SqlRunCheckpointRepository(session_factory)

    async def load_initial(
        self,
        workspace_id: WorkspaceId,
        run_id: RunId,
        *,
        budget: AgentBudgetLimit,
        resume_token: SecretStr | None = None,
    ) -> InitialContextLoad:
        run = await self._runs.get(workspace_id, run_id)
        if run is None:
            raise ContextLoadError(
                ContextLoadReason.RUN_NOT_FOUND,
                f"Investigation Run not found: {run_id}",
            )
        if run.run_type is not RunType.CASE_INVESTIGATION:
            raise ContextLoadError(
                ContextLoadReason.RUN_NOT_EXECUTABLE,
                f"Run {run_id} is not a Case investigation",
            )
        if run.status is not RunStatus.RUNNING:
            raise ContextLoadError(
                ContextLoadReason.RUN_NOT_EXECUTABLE,
                f"Run {run_id} must hold a fenced execution lease before context loading",
            )
        latest = await self._checkpoints.get_latest(workspace_id, run_id)
        if latest is not None:
            raise ContextLoadError(
                ContextLoadReason.CHECKPOINT_ALREADY_EXISTS,
                f"Run {run_id} already has a Checkpoint and must use resume loading",
            )

        packet = await self.load_case_packet(
            workspace_id,
            run.case_id,
            goal=run.goal,
            budget=budget,
        )
        resume_token_sha256 = None
        if resume_token is not None:
            resume_token_sha256 = hashlib.sha256(
                resume_token.get_secret_value().encode("utf-8")
            ).hexdigest()
        state = GoalLoopState(
            workspace_id=workspace_id,
            run_id=run.id,
            case_id=run.case_id,
            goal=run.goal,
            loop_iteration=0,
            evidence_ids=packet.manifest.included_evidence_ids,
            hypothesis_ids=tuple(item.hypothesis_id for item in packet.hypotheses),
            context_sha256=packet.manifest.context_sha256,
            resume_token_sha256=resume_token_sha256,
        )
        checkpoint = GoalLoopCheckpoint(
            workspace_id=workspace_id,
            run_id=run.id,
            case_id=run.case_id,
            goal=run.goal,
            loop_iteration=0,
            budget_snapshot=BudgetSnapshot(limit=budget, usage=BudgetUsage()),
            evidence_ids=state.evidence_ids,
            hypothesis_ids=state.hypothesis_ids,
            context_sha256=state.context_sha256,
            resume_token_sha256=state.resume_token_sha256,
        )
        return InitialContextLoad(
            run=run,
            packet=packet,
            state=state,
            checkpoint=checkpoint,
        )

    async def load_case_packet(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
        *,
        goal: str,
        budget: AgentBudgetLimit,
    ) -> LeadContextPacket:
        case = await self._cases.get(workspace_id, case_id)
        if case is None:
            raise ContextLoadError(
                ContextLoadReason.CASE_NOT_FOUND,
                f"Case not found: {case_id}",
            )
        lineage = await self._load_lineage(workspace_id, case_id)
        view = self._load_dataset_view(workspace_id, lineage.dataset_id)
        artifact, artifact_sha256 = self._load_artifact(lineage)
        self._validate_dataset_identity(workspace_id, lineage.dataset_id, view)
        self._validate_artifact(lineage, artifact, view)

        normalized = self._data.normalize(workspace_id, lineage.dataset_id)
        evidence = await self._load_evidence(case)
        hypotheses = await self._load_hypotheses(case, evidence)
        self._validate_source_references(
            evidence,
            artifact,
            normalized_fact_ids=frozenset(fact.id for fact in normalized.facts),
        )
        return self._build_packet(
            case=case,
            lineage=lineage,
            artifact=artifact,
            artifact_sha256=artifact_sha256,
            evidence=evidence,
            hypotheses=hypotheses,
            goal=goal,
            budget=budget,
        )

    async def _load_lineage(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> CaseLineage:
        try:
            lineage = await self._lineage.get(workspace_id, case_id)
        except ValidationError as exc:
            reason = (
                ContextLoadReason.ARTIFACT_PATH_UNSAFE
                if "relative derived path" in str(exc)
                else ContextLoadReason.LINEAGE_INVALID
            )
            raise ContextLoadError(reason, f"Stored Case lineage is invalid: {case_id}") from exc
        if lineage is None:
            raise ContextLoadError(
                ContextLoadReason.LINEAGE_NOT_FOUND,
                f"Case lineage not found: {case_id}",
            )
        return lineage

    def _load_dataset_view(
        self,
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
    ) -> DatasetView:
        storage_root = self._data.storage_root.resolve()
        workspace_root = self._data.storage_root / str(workspace_id)
        dataset_root = workspace_root / str(dataset_id)
        resolved_dataset_root = dataset_root.resolve()
        if (
            workspace_root.is_symlink()
            or dataset_root.is_symlink()
            or not resolved_dataset_root.is_relative_to(storage_root)
        ):
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_PATH_UNSAFE,
                "Dataset storage path escaped the configured Commerce storage root",
            )
        manifest_path = dataset_root / "manifest.json"
        if not manifest_path.is_file():
            raise ContextLoadError(
                ContextLoadReason.DATASET_MANIFEST_NOT_FOUND,
                f"Dataset manifest not found: {dataset_id}",
            )
        try:
            return self._data.get_view(workspace_id, dataset_id)
        except DatasetNotFoundError as exc:
            raise ContextLoadError(
                ContextLoadReason.DATASET_MANIFEST_NOT_FOUND,
                f"Dataset manifest not found: {dataset_id}",
            ) from exc
        except (DataIntakeError, ValidationError, ValueError) as exc:
            raise ContextLoadError(
                ContextLoadReason.DATASET_MANIFEST_INVALID,
                f"Dataset manifest or deterministic view is invalid: {dataset_id}",
            ) from exc

    def _load_artifact(
        self,
        lineage: CaseLineage,
    ) -> tuple[CaseAnalysisArtifact, str]:
        relative = PurePosixPath(lineage.analysis_artifact_relative_path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or len(relative.parts) != 2
            or relative.parts[0] != "derived"
        ):
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_PATH_UNSAFE,
                "Case analysis artifact path escaped the Dataset derived directory",
            )
        dataset_root = (
            self._data.storage_root
            / str(lineage.workspace_id)
            / str(lineage.dataset_id)
        )
        artifact_path = dataset_root.joinpath(*relative.parts)
        resolved_root = dataset_root.resolve()
        resolved_path = artifact_path.resolve()
        if not resolved_path.is_relative_to(resolved_root) or any(
            part.is_symlink()
            for part in (dataset_root / relative.parts[0], artifact_path)
        ):
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_PATH_UNSAFE,
                "Case analysis artifact resolved outside immutable Dataset storage",
            )
        if not artifact_path.is_file():
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_NOT_FOUND,
                f"Case analysis artifact not found: {relative.as_posix()}",
            )
        payload_bytes = artifact_path.read_bytes()
        actual_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        if actual_sha256 != lineage.analysis_artifact_sha256:
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_HASH_MISMATCH,
                "Case analysis artifact SHA-256 does not match persisted lineage",
            )
        try:
            raw: Any = json.loads(payload_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_INVALID,
                "Case analysis artifact is not valid UTF-8 JSON",
            ) from exc
        leaked = hidden_evaluation_label_paths(raw, path="$.analysis_artifact")
        if leaked:
            raise ContextLoadError(
                ContextLoadReason.HIDDEN_EVALUATION_LABEL,
                f"Case context contains hidden evaluation labels: {', '.join(leaked)}",
            )
        try:
            # JSON-mode validation preserves Decimal metric values. Validating the
            # already-decoded Python dict would select float from MetricValue's
            # union and silently lose deterministic precision.
            return CaseAnalysisArtifact.model_validate_json(payload_bytes), actual_sha256
        except ValidationError as exc:
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_INVALID,
                "Case analysis artifact does not match its versioned schema",
            ) from exc

    @staticmethod
    def _validate_dataset_identity(
        workspace_id: WorkspaceId,
        dataset_id: DatasetId,
        view: DatasetView,
    ) -> None:
        if (
            view.manifest.workspace_id != workspace_id
            or view.manifest.dataset_id != dataset_id
            or view.capabilities.workspace_id != workspace_id
            or view.capabilities.dataset_id != dataset_id
        ):
            raise ContextLoadError(
                ContextLoadReason.DATASET_IDENTITY_MISMATCH,
                "Dataset Manifest or Capability Profile identity does not match lineage",
            )

    @classmethod
    def _validate_artifact(
        cls,
        lineage: CaseLineage,
        artifact: CaseAnalysisArtifact,
        view: DatasetView,
    ) -> None:
        identity_matches = (
            artifact.workspace_id == lineage.workspace_id
            and artifact.dataset_id == lineage.dataset_id
            and artifact.case_id == lineage.case_id
            and artifact.seller_external_key == lineage.seller_external_key
            and str(artifact.seller_entity_id) == str(lineage.seller_entity_id)
            and artifact.baseline.seller_id == lineage.seller_external_key
            and artifact.current.seller_id == lineage.seller_external_key
            and artifact.baseline.seller_entity_id == lineage.seller_entity_id
            and artifact.current.seller_entity_id == lineage.seller_entity_id
            and cls._same_instant(
                artifact.baseline.window.start, lineage.baseline_start
            )
            and cls._same_instant(artifact.baseline.window.end, lineage.baseline_end)
            and cls._same_instant(artifact.current.window.start, lineage.current_start)
            and cls._same_instant(artifact.current.window.end, lineage.current_end)
        )
        if not identity_matches:
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_IDENTITY_MISMATCH,
                "Case analysis artifact identity or windows do not match lineage",
            )
        if artifact.capabilities != view.capabilities:
            raise ContextLoadError(
                ContextLoadReason.CAPABILITY_MISMATCH,
                "Stored Case capability context differs from the current Dataset view",
            )
        signal_ids = tuple(signal.id for signal in artifact.signals)
        if len(signal_ids) != len(set(signal_ids)) or set(signal_ids) != set(
            lineage.anomaly_ids
        ):
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_IDENTITY_MISMATCH,
                "Case analysis Anomaly IDs do not match lineage",
            )
        cls._validate_metric_and_signal_references(lineage, artifact)

    @staticmethod
    def _validate_metric_and_signal_references(
        lineage: CaseLineage,
        artifact: CaseAnalysisArtifact,
    ) -> None:
        baseline = {item.id: item for item in artifact.baseline.observations}
        current = {item.id: item for item in artifact.current.observations}
        if len(baseline) != len(artifact.baseline.observations) or len(current) != len(
            artifact.current.observations
        ):
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_INVALID,
                "Case analysis MetricObservation IDs must be unique",
            )
        signal_metric_ids: list[MetricObservationId] = []
        for signal in artifact.signals:
            baseline_item = baseline.get(signal.baseline_observation_id)
            current_item = current.get(signal.current_observation_id)
            if baseline_item is None or current_item is None:
                raise ContextLoadError(
                    ContextLoadReason.ARTIFACT_IDENTITY_MISMATCH,
                    "Anomaly references a MetricObservation outside its snapshots",
                )
            if (
                baseline_item.metric_name != signal.metric_name.value
                or current_item.metric_name != signal.metric_name.value
                or Decimal(str(baseline_item.value)) != signal.baseline_value
                or Decimal(str(current_item.value)) != signal.current_value
            ):
                raise ContextLoadError(
                    ContextLoadReason.ARTIFACT_IDENTITY_MISMATCH,
                    "Anomaly values do not match deterministic MetricSnapshots",
                )
            signal_metric_ids.extend(
                (signal.baseline_observation_id, signal.current_observation_id)
            )
        if set(signal_metric_ids) != set(lineage.metric_observation_ids):
            raise ContextLoadError(
                ContextLoadReason.ARTIFACT_IDENTITY_MISMATCH,
                "Anomaly MetricObservation IDs do not match Case lineage",
            )

    async def _load_evidence(self, case: Case) -> tuple[Evidence, ...]:
        persisted = await self._evidence.list_case(case.workspace_id, case.id)
        by_id = {item.id: item for item in persisted}
        if set(by_id) != set(case.evidence_ids) or len(by_id) != len(persisted):
            raise ContextLoadError(
                ContextLoadReason.CASE_REFERENCE_MISMATCH,
                "Case Evidence membership differs from append-only Evidence records",
            )
        return tuple(by_id[evidence_id] for evidence_id in case.evidence_ids)

    async def _load_hypotheses(
        self,
        case: Case,
        evidence: tuple[Evidence, ...],
    ) -> tuple[Hypothesis, ...]:
        known_evidence_ids = frozenset(item.id for item in evidence)
        loaded: list[Hypothesis] = []
        for hypothesis_id in case.hypothesis_ids:
            hypothesis = await self._hypotheses.get_latest(
                case.workspace_id,
                hypothesis_id,
            )
            references = (
                frozenset(hypothesis.supporting_evidence_ids)
                | frozenset(hypothesis.contradicting_evidence_ids)
                if hypothesis is not None
                else frozenset()
            )
            if (
                hypothesis is None
                or hypothesis.case_id != case.id
                or hypothesis.workspace_id != case.workspace_id
                or not references.issubset(known_evidence_ids)
            ):
                raise ContextLoadError(
                    ContextLoadReason.CASE_REFERENCE_MISMATCH,
                    "Case Hypothesis membership or Evidence references are invalid",
                )
            loaded.append(hypothesis)
        return tuple(loaded)

    @staticmethod
    def _validate_source_references(
        evidence: tuple[Evidence, ...],
        artifact: CaseAnalysisArtifact,
        *,
        normalized_fact_ids: frozenset[FactId],
    ) -> None:
        metric_ids = frozenset(
            observation.id
            for observation in (
                *artifact.baseline.observations,
                *artifact.current.observations,
            )
        )
        for item in evidence:
            if not frozenset(item.fact_ids).issubset(normalized_fact_ids):
                raise ContextLoadError(
                    ContextLoadReason.CASE_REFERENCE_MISMATCH,
                    f"Evidence {item.id} references Facts outside the Dataset",
                )
            if not frozenset(item.metric_observation_ids).issubset(metric_ids):
                raise ContextLoadError(
                    ContextLoadReason.CASE_REFERENCE_MISMATCH,
                    f"Evidence {item.id} references Metrics outside Case context",
                )

    @classmethod
    def _build_packet(
        cls,
        *,
        case: Case,
        lineage: CaseLineage,
        artifact: CaseAnalysisArtifact,
        artifact_sha256: str,
        evidence: tuple[Evidence, ...],
        hypotheses: tuple[Hypothesis, ...],
        goal: str,
        budget: AgentBudgetLimit,
    ) -> LeadContextPacket:
        evidence_digests = tuple(
            EvidenceDigest(
                evidence_id=item.id,
                summary=item.summary,
                semantic_status=item.semantic_status,
                confidence=item.confidence,
                fact_ids=item.fact_ids,
                metric_observation_ids=item.metric_observation_ids,
            )
            for item in evidence
        )
        hypothesis_digests = tuple(
            HypothesisDigest(
                hypothesis_id=item.id,
                statement=item.statement,
                status=item.status.value,
                confidence=item.confidence,
                evidence_ids=tuple(
                    dict.fromkeys(
                        (
                            *item.supporting_evidence_ids,
                            *item.contradicting_evidence_ids,
                        )
                    )
                ),
            )
            for item in hypotheses
        )
        analysis = CaseAnalysisDigest(
            dataset_id=lineage.dataset_id,
            seller_entity_id=lineage.seller_entity_id,
            seller_external_key=lineage.seller_external_key,
            baseline_window=artifact.baseline.window,
            current_window=artifact.current.window,
            baseline_metrics=tuple(
                cls._metric_digest(item) for item in artifact.baseline.observations
            ),
            current_metrics=tuple(
                cls._metric_digest(item) for item in artifact.current.observations
            ),
            anomalies=tuple(
                AnomalyDigest(
                    anomaly_id=item.id,
                    metric_name=item.metric_name,
                    baseline_observation_id=item.baseline_observation_id,
                    current_observation_id=item.current_observation_id,
                    baseline_value=item.baseline_value,
                    current_value=item.current_value,
                    absolute_change=item.absolute_change,
                    relative_change=item.relative_change,
                    direction=item.direction,
                    severity=item.severity,
                    confidence=item.confidence,
                    baseline_sample_size=item.baseline_sample_size,
                    current_sample_size=item.current_sample_size,
                    sample_adequate=item.sample_adequate,
                    reason=item.reason,
                )
                for item in artifact.signals
            ),
        )
        capabilities = frozenset(
            assessment.name
            for assessment in artifact.capabilities.capabilities
            if assessment.status
            in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
        )
        metric_ids = tuple(
            item.metric_observation_id
            for item in (*analysis.baseline_metrics, *analysis.current_metrics)
        )
        fact_ids = tuple(
            dict.fromkeys(fact_id for item in evidence for fact_id in item.fact_ids)
        )
        manifest = ContextManifest(
            context_version="commerce-context@1.0.0",
            workspace_id=case.workspace_id,
            case_id=case.id,
            dataset_id=lineage.dataset_id,
            source_artifact_sha256=artifact_sha256,
            context_sha256="0" * 64,
            estimated_tokens=0,
            included_evidence_ids=tuple(item.id for item in evidence),
            included_fact_ids=fact_ids,
            included_metric_observation_ids=metric_ids,
            included_anomaly_ids=tuple(item.id for item in artifact.signals),
            redactions=(
                "metric.source_fact_ids replaced by source_fact_count",
                "raw Dataset rows available only through scoped Tools",
            ),
        )
        packet = LeadContextPacket(
            case=CaseHeader(
                workspace_id=case.workspace_id,
                case_id=case.id,
                title=case.title,
                severity=case.severity,
                status=case.status,
                version=case.version,
            ),
            goal=goal,
            manifest=manifest,
            budget=budget,
            capabilities=capabilities,
            capability_profile=artifact.capabilities,
            analysis=analysis,
            evidence=evidence_digests,
            hypotheses=hypothesis_digests,
        )
        estimated_tokens = estimate_context_tokens(packet)
        context_sha256 = canonical_context_sha256(packet)
        if estimated_tokens > budget.max_tokens:
            raise ContextLoadError(
                ContextLoadReason.CONTEXT_BUDGET_EXCEEDED,
                f"Context estimate {estimated_tokens} exceeds budget {budget.max_tokens}",
            )
        return packet.model_copy(
            update={
                "manifest": packet.manifest.model_copy(
                    update={
                        "estimated_tokens": estimated_tokens,
                        "context_sha256": context_sha256,
                    }
                )
            }
        )

    @staticmethod
    def _metric_digest(item: MetricObservation) -> MetricObservationDigest:
        return MetricObservationDigest(
            metric_observation_id=item.id,
            metric_name=item.metric_name,
            semantic_status=item.semantic_status,
            value=item.value,
            unit=item.unit,
            formula_version=item.formula_version,
            window_start=item.window_start,
            window_end=item.window_end,
            sample_size=item.sample_size,
            numerator=item.numerator,
            denominator=item.denominator,
            source_fact_count=len(item.source_fact_ids),
            unknown_reason=item.unknown_reason,
        )

    @staticmethod
    def _same_instant(left: datetime, right: datetime) -> bool:
        def normalized(value: datetime) -> datetime:
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        return normalized(left) == normalized(right)
