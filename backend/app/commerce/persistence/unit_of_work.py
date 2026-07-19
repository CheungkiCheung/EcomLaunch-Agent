"""Atomic Commerce mutations that keep Case rows and Domain Events aligned."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.domain.enums import CaseStatus, RunPhase, RunStatus
from app.commerce.domain.events import (
    DomainEventActor,
    DomainEventEnvelope,
    NewDomainEvent,
)
from app.commerce.domain.ids import (
    CheckpointId,
    CorrelationId,
    EventId,
    RunId,
    TraceId,
)
from app.commerce.domain.lineage import CaseLineage
from app.commerce.domain.models import Case, Evidence, Hypothesis
from app.commerce.domain.runs import CommerceRun
from app.commerce.persistence.events import (
    EventSequenceConflictError,
    SqlDomainEventStore,
)
from app.commerce.persistence.lineage import SqlCaseLineageRepository
from app.commerce.persistence.repositories import (
    DuplicateEntityError,
    SqlCaseRepository,
)
from app.commerce.persistence.runs import (
    RunCheckpointRecord,
    RunLeaseCredentials,
    RunLeaseLostError,
    SqlRunCheckpointRepository,
    SqlRunLeaseRepository,
    SqlRunRepository,
)
from app.commerce.persistence.work_records import (
    SqlEvidenceRepository,
    SqlHypothesisRepository,
)


class SqlCommerceUnitOfWork:
    """Use one SQL transaction for every state mutation and authoritative event."""

    MAX_SEQUENCE_RETRIES = 20

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_case(
        self,
        case: Case,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        event = NewDomainEvent(
            workspace_id=case.workspace_id,
            case_id=case.id,
            event_type="case.created",
            occurred_at=case.opened_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            actor=actor,
            payload={
                "title": case.title,
                "severity": case.severity.value,
                "status": case.status.value,
                "version": case.version,
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlCaseRepository.create_in_session(session, case)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Case already exists: {case.id}") from exc

    async def create_case_with_lineage(
        self,
        case: Case,
        lineage: CaseLineage,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        trigger_payload: dict[str, object] | None = None,
    ) -> DomainEventEnvelope:
        self._validate_lineage_membership(case, lineage)
        event = NewDomainEvent(
            workspace_id=case.workspace_id,
            case_id=case.id,
            event_type="case.created",
            occurred_at=case.opened_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            actor=actor,
            payload={
                "title": case.title,
                "severity": case.severity.value,
                "status": case.status.value,
                "version": case.version,
                "dataset_id": str(lineage.dataset_id),
                "analysis_artifact_relative_path": (
                    lineage.analysis_artifact_relative_path
                ),
                "analysis_artifact_sha256": lineage.analysis_artifact_sha256,
                **({"trigger": trigger_payload} if trigger_payload is not None else {}),
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlCaseRepository.create_in_session(session, case)
                await SqlCaseLineageRepository.create_in_session(session, lineage)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(f"Case already exists: {case.id}") from exc

    async def attach_case_lineage(
        self,
        lineage: CaseLineage,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        event = NewDomainEvent(
            workspace_id=lineage.workspace_id,
            case_id=lineage.case_id,
            event_type="case.lineage_attached",
            occurred_at=lineage.created_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            actor=actor,
            payload={
                "dataset_id": str(lineage.dataset_id),
                "seller_entity_id": str(lineage.seller_entity_id),
                "analysis_artifact_relative_path": (
                    lineage.analysis_artifact_relative_path
                ),
                "analysis_artifact_sha256": lineage.analysis_artifact_sha256,
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlCaseLineageRepository.create_in_session(session, lineage)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Case lineage already exists: {lineage.case_id}"
            ) from exc

    async def save_case(
        self,
        case: Case,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    previous_status = await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    event_type = self._case_event_type(previous_status, case.status)
                    event = NewDomainEvent(
                        workspace_id=case.workspace_id,
                        case_id=case.id,
                        event_type=event_type,
                        occurred_at=case.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "title": case.title,
                            "severity": case.severity.value,
                            "from_status": previous_status.value,
                            "to_status": case.status.value,
                            "version": case.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic Case/Event mutation exceeded sequence retry budget"
        ) from last_error

    @staticmethod
    def _case_event_type(previous: CaseStatus, current: CaseStatus) -> str:
        if current is CaseStatus.REOPENED and previous is CaseStatus.RESOLVED:
            return "case.reopened"
        if previous is not current:
            return "case.status_changed"
        return "case.updated"

    async def create_run(
        self,
        run: CommerceRun,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        event = NewDomainEvent(
            workspace_id=run.workspace_id,
            case_id=run.case_id,
            run_id=run.id,
            event_type="run.created",
            occurred_at=run.created_at,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_event_id=causation_event_id,
            actor=actor,
            payload={
                "run_type": run.run_type.value,
                "status": run.status.value,
                "phase": run.phase.value,
                "goal": run.goal,
                "version": run.version,
            },
        )
        try:
            async with self._session_factory() as session, session.begin():
                await SqlRunRepository.create_in_session(session, run)
                return await SqlDomainEventStore.append_in_session(session, event)
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Run or idempotency key already exists: {run.id}"
            ) from exc

    async def save_run(
        self,
        run: CommerceRun,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> DomainEventEnvelope:
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    if lease is not None:
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            run.workspace_id,
                            run.id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    previous_status, previous_phase = (
                        await SqlRunRepository.save_in_session(
                            session,
                            run,
                            expected_version=expected_version,
                        )
                    )
                    event_type = self._run_event_type(
                        previous_status,
                        run.status,
                        previous_phase,
                        run.phase,
                    )
                    event = NewDomainEvent(
                        workspace_id=run.workspace_id,
                        case_id=run.case_id,
                        run_id=run.id,
                        event_type=event_type,
                        occurred_at=run.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "from_status": previous_status.value,
                            "to_status": run.status.value,
                            "from_phase": previous_phase.value,
                            "to_phase": run.phase.value,
                            "wait_reason": run.wait_reason,
                            "stop_reason": run.stop_reason,
                            "version": run.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic Run/Event mutation exceeded sequence retry budget"
        ) from last_error

    @staticmethod
    def _run_event_type(
        previous_status: RunStatus,
        current_status: RunStatus,
        previous_phase: RunPhase,
        current_phase: RunPhase,
    ) -> str:
        if previous_status is not current_status:
            return "run.status_changed"
        if previous_phase is not current_phase:
            return "run.phase_changed"
        return "run.updated"

    async def append_run_checkpoint(
        self,
        checkpoint: GoalLoopCheckpoint,
        *,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        checkpoint_id: CheckpointId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> tuple[RunCheckpointRecord, DomainEventEnvelope]:
        selected_id = checkpoint_id or CheckpointId.new()
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    run = await SqlRunRepository.get_in_session(
                        session,
                        checkpoint.workspace_id,
                        checkpoint.run_id,
                    )
                    if run is None:
                        raise ValueError(f"Run not found: {checkpoint.run_id}")
                    if run.status is RunStatus.RUNNING:
                        if lease is None:
                            raise RunLeaseLostError(
                                "Running Run Checkpoint write requires a lease"
                            )
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    elif lease is not None:
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    record = await SqlRunCheckpointRepository.append_in_session(
                        session,
                        checkpoint,
                        checkpoint_id=selected_id,
                    )
                    event = NewDomainEvent(
                        workspace_id=checkpoint.workspace_id,
                        case_id=checkpoint.case_id,
                        run_id=checkpoint.run_id,
                        event_type="run.checkpoint_saved",
                        occurred_at=record.created_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "checkpoint_id": str(record.id),
                            "checkpoint_sequence": record.sequence,
                            "checkpoint_schema_version": checkpoint.schema_version,
                            "loop_iteration": checkpoint.loop_iteration,
                        },
                    )
                    envelope = await SqlDomainEventStore.append_in_session(
                        session,
                        event,
                    )
                    return record, envelope
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic Checkpoint/Event append exceeded sequence retry budget"
        ) from last_error

    async def append_run_checkpoint_with_events(
        self,
        checkpoint: GoalLoopCheckpoint,
        *,
        prior_events: tuple[NewDomainEvent, ...],
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        checkpoint_id: CheckpointId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> tuple[RunCheckpointRecord, tuple[DomainEventEnvelope, ...]]:
        """Atomically append run events followed by one fenced Checkpoint."""

        for event in prior_events:
            if (
                event.workspace_id != checkpoint.workspace_id
                or event.case_id != checkpoint.case_id
                or event.run_id != checkpoint.run_id
            ):
                raise ValueError(
                    "Prior Checkpoint events must match Workspace, Case and Run"
                )
        selected_id = checkpoint_id or CheckpointId.new()
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    run = await SqlRunRepository.get_in_session(
                        session,
                        checkpoint.workspace_id,
                        checkpoint.run_id,
                    )
                    if run is None:
                        raise ValueError(f"Run not found: {checkpoint.run_id}")
                    if run.status is RunStatus.RUNNING:
                        if lease is None:
                            raise RunLeaseLostError(
                                "Running Run Checkpoint write requires a lease"
                            )
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )
                    elif lease is not None:
                        await SqlRunLeaseRepository.require_valid_in_session(
                            session,
                            checkpoint.workspace_id,
                            checkpoint.run_id,
                            lease,
                            checked_at=lease_checked_at or datetime.now(UTC),
                        )

                    envelopes = [
                        await SqlDomainEventStore.append_in_session(session, event)
                        for event in prior_events
                    ]
                    record = await SqlRunCheckpointRepository.append_in_session(
                        session,
                        checkpoint,
                        checkpoint_id=selected_id,
                    )
                    checkpoint_event = NewDomainEvent(
                        workspace_id=checkpoint.workspace_id,
                        case_id=checkpoint.case_id,
                        run_id=checkpoint.run_id,
                        event_type="run.checkpoint_saved",
                        occurred_at=record.created_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "checkpoint_id": str(record.id),
                            "checkpoint_sequence": record.sequence,
                            "checkpoint_schema_version": checkpoint.schema_version,
                            "loop_iteration": checkpoint.loop_iteration,
                        },
                    )
                    envelopes.append(
                        await SqlDomainEventStore.append_in_session(
                            session,
                            checkpoint_event,
                        )
                    )
                    return record, tuple(envelopes)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic prior Events/Checkpoint append exceeded sequence retry budget"
        ) from last_error

    async def append_evidence(
        self,
        case: Case,
        evidence: Evidence,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        run_id: RunId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> DomainEventEnvelope:
        """Append Evidence and its Case membership/event atomically."""

        self._validate_evidence_membership(case, evidence)
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    if run_id is not None:
                        if lease is None:
                            raise RunLeaseLostError(
                                "Agent Evidence write for a running Run requires a lease"
                            )
                        lease_row = (
                            await SqlRunLeaseRepository.require_valid_in_session(
                                session,
                                case.workspace_id,
                                run_id,
                                lease,
                                checked_at=lease_checked_at or datetime.now(UTC),
                            )
                        )
                        if lease_row.case_id != str(case.id):
                            raise ValueError("Evidence Run lease must belong to the Case")
                    await SqlEvidenceRepository.append_in_session(session, evidence)
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    event = NewDomainEvent(
                        workspace_id=case.workspace_id,
                        case_id=case.id,
                        run_id=run_id,
                        event_type="evidence.appended",
                        occurred_at=case.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "evidence_id": str(evidence.id),
                            "relation": evidence.relation.value,
                            "semantic_status": evidence.semantic_status.value,
                            "confidence": evidence.confidence,
                            "fact_ids": [str(value) for value in evidence.fact_ids],
                            "metric_observation_ids": [
                                str(value) for value in evidence.metric_observation_ids
                            ],
                            "case_version": case.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic Evidence/Case/Event mutation exceeded sequence retry budget"
        ) from last_error

    async def append_hypothesis_version(
        self,
        case: Case,
        hypothesis: Hypothesis,
        *,
        expected_version: int,
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
    ) -> DomainEventEnvelope:
        """Append a Hypothesis version and its Case membership/event atomically."""

        self._validate_hypothesis_membership(case, hypothesis)
        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    await SqlHypothesisRepository.append_version_in_session(
                        session,
                        hypothesis,
                    )
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    event = NewDomainEvent(
                        workspace_id=case.workspace_id,
                        case_id=case.id,
                        event_type="hypothesis.version_appended",
                        occurred_at=case.updated_at,
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        causation_event_id=causation_event_id,
                        actor=actor,
                        payload={
                            "hypothesis_id": str(hypothesis.id),
                            "hypothesis_version": hypothesis.version,
                            "status": hypothesis.status.value,
                            "confidence": hypothesis.confidence,
                            "supporting_evidence_ids": [
                                str(value)
                                for value in hypothesis.supporting_evidence_ids
                            ],
                            "contradicting_evidence_ids": [
                                str(value)
                                for value in hypothesis.contradicting_evidence_ids
                            ],
                            "case_version": case.version,
                        },
                    )
                    return await SqlDomainEventStore.append_in_session(session, event)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic Hypothesis/Case/Event mutation exceeded sequence retry budget"
        ) from last_error

    async def append_hypothesis_versions_with_events(
        self,
        case: Case,
        hypotheses: tuple[Hypothesis, ...],
        *,
        expected_version: int,
        prior_events: tuple[NewDomainEvent, ...],
        trace_id: TraceId,
        correlation_id: CorrelationId,
        actor: DomainEventActor,
        causation_event_id: EventId | None = None,
        run_id: RunId | None = None,
        lease: RunLeaseCredentials | None = None,
        lease_checked_at: datetime | None = None,
    ) -> tuple[DomainEventEnvelope, ...]:
        """Atomically persist one Lead/Verification result as Hypothesis versions."""

        if not hypotheses:
            raise ValueError("Hypothesis batch cannot be empty")
        references = tuple((item.id, item.version) for item in hypotheses)
        if len(references) != len(set(references)):
            raise ValueError("Hypothesis batch references must be unique")
        for hypothesis in hypotheses:
            self._validate_hypothesis_membership(case, hypothesis)
        for event in prior_events:
            if (
                event.workspace_id != case.workspace_id
                or event.case_id != case.id
                or event.run_id != run_id
            ):
                raise ValueError(
                    "Prior Hypothesis events must match Workspace, Case and Run"
                )

        last_error: IntegrityError | None = None
        for attempt in range(self.MAX_SEQUENCE_RETRIES):
            try:
                async with self._session_factory() as session, session.begin():
                    if run_id is not None:
                        if lease is None:
                            raise RunLeaseLostError(
                                "Agent Hypothesis write for a running Run requires a lease"
                            )
                        lease_row = (
                            await SqlRunLeaseRepository.require_valid_in_session(
                                session,
                                case.workspace_id,
                                run_id,
                                lease,
                                checked_at=lease_checked_at or datetime.now(UTC),
                            )
                        )
                        if lease_row.case_id != str(case.id):
                            raise ValueError(
                                "Hypothesis Run lease must belong to the Case"
                            )
                    elif lease is not None:
                        raise ValueError("Hypothesis lease requires a Run ID")

                    envelopes = [
                        await SqlDomainEventStore.append_in_session(session, event)
                        for event in prior_events
                    ]
                    for hypothesis in hypotheses:
                        await SqlHypothesisRepository.append_version_in_session(
                            session,
                            hypothesis,
                        )
                    await SqlCaseRepository.save_in_session(
                        session,
                        case,
                        expected_version=expected_version,
                    )
                    result_causation_id = (
                        envelopes[-1].id if envelopes else causation_event_id
                    )
                    for hypothesis in hypotheses:
                        event = NewDomainEvent(
                            workspace_id=case.workspace_id,
                            case_id=case.id,
                            run_id=run_id,
                            event_type="hypothesis.version_appended",
                            occurred_at=case.updated_at,
                            trace_id=trace_id,
                            correlation_id=correlation_id,
                            causation_event_id=result_causation_id,
                            actor=actor,
                            payload={
                                "hypothesis_id": str(hypothesis.id),
                                "hypothesis_version": hypothesis.version,
                                "status": hypothesis.status.value,
                                "confidence": hypothesis.confidence,
                                "supporting_evidence_ids": [
                                    str(value)
                                    for value in hypothesis.supporting_evidence_ids
                                ],
                                "contradicting_evidence_ids": [
                                    str(value)
                                    for value in hypothesis.contradicting_evidence_ids
                                ],
                                "case_version": case.version,
                            },
                        )
                        envelopes.append(
                            await SqlDomainEventStore.append_in_session(session, event)
                        )
                    return tuple(envelopes)
            except IntegrityError as exc:
                last_error = exc
                await asyncio.sleep(0.001 * (attempt + 1))
        raise EventSequenceConflictError(
            "Atomic Hypothesis batch/Case/Event mutation exceeded sequence retry budget"
        ) from last_error

    @staticmethod
    def _validate_evidence_membership(case: Case, evidence: Evidence) -> None:
        if evidence.workspace_id != case.workspace_id:
            raise ValueError("Evidence workspace must match Case workspace")
        if evidence.case_id != case.id:
            raise ValueError("Evidence Case must match the target Case")
        if evidence.id not in case.evidence_ids:
            raise ValueError("Case must include the appended Evidence ID")

    @staticmethod
    def _validate_hypothesis_membership(case: Case, hypothesis: Hypothesis) -> None:
        if hypothesis.workspace_id != case.workspace_id:
            raise ValueError("Hypothesis workspace must match Case workspace")
        if hypothesis.case_id != case.id:
            raise ValueError("Hypothesis Case must match the target Case")
        if hypothesis.id not in case.hypothesis_ids:
            raise ValueError("Case must include the appended Hypothesis ID")

    @staticmethod
    def _validate_lineage_membership(case: Case, lineage: CaseLineage) -> None:
        if lineage.workspace_id != case.workspace_id:
            raise ValueError("Case lineage workspace must match Case workspace")
        if lineage.case_id != case.id:
            raise ValueError("Case lineage Case must match target Case")
