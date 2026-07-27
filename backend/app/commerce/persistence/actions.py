"""Action and Approval repositories with Workspace and idempotency boundaries."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commerce.actions.approval import (
    ApprovalDecisionCommand,
    ApprovalRequest,
)
from app.commerce.actions.policy import ActionPolicyDecision
from app.commerce.domain.ids import (
    ActionId,
    ApprovalId,
    CaseId,
    WorkspaceId,
)
from app.commerce.domain.models import Action, CommerceModel
from app.commerce.persistence.models import (
    ActionRow,
    ApprovalDecisionRow,
    ApprovalRequestRow,
)
from app.commerce.persistence.repositories import DuplicateEntityError


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ActionRecord(CommerceModel):
    action: Action
    decision: ActionPolicyDecision
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def keep_decision_projection_consistent(self):
        if self.action != self.decision.action:
            raise ValueError("Action Record projection must match Policy Decision")
        return self

    @classmethod
    def from_policy(
        cls,
        decision: ActionPolicyDecision,
        *,
        occurred_at: datetime,
    ) -> ActionRecord:
        return cls(
            action=decision.action,
            decision=decision,
            created_at=occurred_at,
            updated_at=occurred_at,
            version=1,
        )

    def with_action(
        self,
        action: Action,
        *,
        occurred_at: datetime,
    ) -> ActionRecord:
        if action.id != self.action.id:
            raise ValueError("Action update cannot change identity")
        decision = self.decision.model_copy(update={"action": action})
        return ActionRecord(
            action=action,
            decision=decision,
            created_at=self.created_at,
            updated_at=max(occurred_at, self.updated_at),
            version=self.version + 1,
        )


def _action_values(record: ActionRecord) -> dict:
    return {
        "workspace_id": str(record.action.workspace_id),
        "case_id": str(record.action.case_id),
        "kind": record.decision.validated.draft.kind.value,
        "status": record.action.status.value,
        "policy_level": record.decision.level.value,
        "risk_level": record.action.risk_level.value,
        "decision_json": record.decision.model_dump(mode="json"),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "version": record.version,
    }


def _row_to_action(row: ActionRow) -> ActionRecord:
    decision = ActionPolicyDecision.model_validate(row.decision_json)
    return ActionRecord(
        action=decision.action,
        decision=decision,
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
        version=row.version,
    )


class SqlActionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, record: ActionRecord) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                await self.create_in_session(session, record)
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Action already exists: {record.action.id}"
            ) from exc

    @staticmethod
    async def create_in_session(
        session: AsyncSession,
        record: ActionRecord,
    ) -> None:
        session.add(
            ActionRow(
                action_id=str(record.action.id),
                **_action_values(record),
            )
        )
        await session.flush()

    async def get(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionRecord | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ActionRow).where(
                    ActionRow.workspace_id == str(workspace_id),
                    ActionRow.action_id == str(action_id),
                )
            )
            return _row_to_action(row) if row is not None else None

    @staticmethod
    async def get_in_session(
        session: AsyncSession,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ActionRecord | None:
        row = await session.scalar(
            select(ActionRow).where(
                ActionRow.workspace_id == str(workspace_id),
                ActionRow.action_id == str(action_id),
            )
        )
        return _row_to_action(row) if row is not None else None

    @staticmethod
    async def save_in_session(
        session: AsyncSession,
        record: ActionRecord,
        *,
        expected_version: int,
    ) -> None:
        if record.version != expected_version + 1:
            raise ValueError("Saved Action version must advance by one")
        result = await session.execute(
            update(ActionRow)
            .where(
                ActionRow.workspace_id == str(record.action.workspace_id),
                ActionRow.action_id == str(record.action.id),
                ActionRow.version == expected_version,
            )
            .values(**_action_values(record))
        )
        if result.rowcount != 1:
            raise ValueError("Action changed or disappeared during update")

    async def list_case(
        self,
        workspace_id: WorkspaceId,
        case_id: CaseId,
    ) -> tuple[ActionRecord, ...]:
        statement = (
            select(ActionRow)
            .where(
                ActionRow.workspace_id == str(workspace_id),
                ActionRow.case_id == str(case_id),
            )
            .order_by(ActionRow.created_at.asc(), ActionRow.action_id.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(_row_to_action(row) for row in rows)


def _row_to_approval(row: ApprovalRequestRow) -> ApprovalRequest:
    return ApprovalRequest.model_validate(row.request_json)


def _row_to_decision(row: ApprovalDecisionRow) -> ApprovalDecisionCommand:
    return ApprovalDecisionCommand.model_validate(row.decision_json)


class SqlApprovalRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, request: ApprovalRequest) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                await self.create_in_session(session, request)
        except IntegrityError as exc:
            raise DuplicateEntityError(
                f"Approval request already exists for Action: {request.action_id}"
            ) from exc

    @staticmethod
    async def create_in_session(
        session: AsyncSession,
        request: ApprovalRequest,
    ) -> None:
        session.add(
            ApprovalRequestRow(
                approval_id=str(request.id),
                workspace_id=str(request.workspace_id),
                case_id=str(request.case_id),
                action_id=str(request.action_id),
                status=request.status.value,
                request_json=request.model_dump(mode="json"),
                created_at=request.created_at,
                updated_at=request.updated_at,
                version=request.version,
            )
        )
        await session.flush()

    async def get(
        self,
        workspace_id: WorkspaceId,
        approval_id: ApprovalId,
    ) -> ApprovalRequest | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ApprovalRequestRow).where(
                    ApprovalRequestRow.workspace_id == str(workspace_id),
                    ApprovalRequestRow.approval_id == str(approval_id),
                )
            )
            return _row_to_approval(row) if row is not None else None

    @staticmethod
    async def get_in_session(
        session: AsyncSession,
        workspace_id: WorkspaceId,
        approval_id: ApprovalId,
    ) -> ApprovalRequest | None:
        row = await session.scalar(
            select(ApprovalRequestRow).where(
                ApprovalRequestRow.workspace_id == str(workspace_id),
                ApprovalRequestRow.approval_id == str(approval_id),
            )
        )
        return _row_to_approval(row) if row is not None else None

    @staticmethod
    async def save_in_session(
        session: AsyncSession,
        request: ApprovalRequest,
        *,
        expected_version: int,
    ) -> None:
        if request.version != expected_version + 1:
            raise ValueError("Saved Approval version must advance by one")
        result = await session.execute(
            update(ApprovalRequestRow)
            .where(
                ApprovalRequestRow.workspace_id == str(request.workspace_id),
                ApprovalRequestRow.approval_id == str(request.id),
                ApprovalRequestRow.version == expected_version,
            )
            .values(
                status=request.status.value,
                request_json=request.model_dump(mode="json"),
                updated_at=request.updated_at,
                version=request.version,
            )
        )
        if result.rowcount != 1:
            raise ValueError("Approval changed or disappeared during update")

    async def get_by_action(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
    ) -> ApprovalRequest | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ApprovalRequestRow).where(
                    ApprovalRequestRow.workspace_id == str(workspace_id),
                    ApprovalRequestRow.action_id == str(action_id),
                )
            )
            return _row_to_approval(row) if row is not None else None

    async def append_decision(
        self,
        command: ApprovalDecisionCommand,
    ) -> ApprovalDecisionCommand:
        existing = await self.get_decision_by_idempotency(
            command.workspace_id,
            command.action_id,
            command.idempotency_key_sha256,
        )
        if existing is not None:
            if existing != command:
                raise DuplicateEntityError(
                    "Approval idempotency key was reused with another decision"
                )
            return existing
        try:
            async with self._session_factory() as session, session.begin():
                await self.append_decision_in_session(session, command)
            return command
        except IntegrityError as exc:
            concurrent = await self.get_decision_by_idempotency(
                command.workspace_id,
                command.action_id,
                command.idempotency_key_sha256,
            )
            if concurrent == command:
                return concurrent
            raise DuplicateEntityError(
                "Approval decision or idempotency key already exists"
            ) from exc

    @staticmethod
    async def append_decision_in_session(
        session: AsyncSession,
        command: ApprovalDecisionCommand,
    ) -> None:
        session.add(
            ApprovalDecisionRow(
                decision_id=str(command.id),
                approval_id=str(command.approval_id),
                workspace_id=str(command.workspace_id),
                case_id=str(command.case_id),
                action_id=str(command.action_id),
                idempotency_key_sha256=command.idempotency_key_sha256,
                decision_json=command.model_dump(mode="json"),
                created_at=command.created_at,
            )
        )
        await session.flush()

    async def get_decision_by_idempotency(
        self,
        workspace_id: WorkspaceId,
        action_id: ActionId,
        idempotency_key_sha256: str,
    ) -> ApprovalDecisionCommand | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(ApprovalDecisionRow).where(
                    ApprovalDecisionRow.workspace_id == str(workspace_id),
                    ApprovalDecisionRow.action_id == str(action_id),
                    ApprovalDecisionRow.idempotency_key_sha256
                    == idempotency_key_sha256,
                )
            )
            return _row_to_decision(row) if row is not None else None
