"""Allowlisted, deterministic internal Action Connectors with read-back verification."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

from app.commerce.actions.artifacts import (
    ActionArtifactPayload,
    ActionArtifactStatus,
    ActionExecutionArtifact,
    AuditCohortRow,
    AuditExportArtifact,
    ConnectorVerification,
    DataRequestArtifact,
    InternalConnectorResult,
    InternalTaskArtifact,
    MetricMonitorArtifact,
    NoOpReceiptArtifact,
)
from app.commerce.actions.contracts import (
    ActionKind,
    AuditExportParameters,
    DataRequestParameters,
    InternalTaskParameters,
    MetricMonitorParameters,
    NoOpParameters,
)
from app.commerce.domain.enums import ActionStatus
from app.commerce.persistence.actions import ActionRecord


class UnsupportedConnectorError(ValueError):
    pass


class ConnectorStateError(ValueError):
    pass


_INTERNAL_TOOL_BY_KIND = {
    ActionKind.NO_OP: "internal_no_op.record",
    ActionKind.EXPORT_AUDIT_COHORT: "internal_audit_export.create",
    ActionKind.CREATE_INTERNAL_TASK: "internal_ops_task.create",
    ActionKind.CREATE_METRIC_MONITOR: "internal_metric_monitor.create",
    ActionKind.REQUEST_MISSING_DATA: "internal_data_request.create",
}


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _verification_sha256(
    *,
    record: ActionRecord | None,
    action_id: str,
    execution_tool: str,
    payload: ActionArtifactPayload,
    status: ActionArtifactStatus,
    checks: tuple[str, ...],
) -> str:
    return _canonical_sha256(
        {
            "action_id": action_id,
            "execution_tool": execution_tool,
            "payload": payload.model_dump(mode="json"),
            "status": status.value,
            "checks": checks,
            "policy_validation_sha256": (record.decision.validated.validation_sha256 if record is not None else None),
        }
    )


class InternalConnectorRegistry:
    """Execute only fixed internal tools selected by the deterministic Policy Gate."""

    def execute(
        self,
        record: ActionRecord,
        *,
        storage_root: Path,
        occurred_at: datetime,
        audit_rows: tuple[AuditCohortRow, ...] = (),
    ) -> InternalConnectorResult:
        tool = self._execution_tool(record)
        if tool.startswith("connector:"):
            raise UnsupportedConnectorError("Real external Connector execution is not available in this version")
        if record.action.status not in {
            ActionStatus.POLICY_CHECKED,
            ActionStatus.APPROVED,
            ActionStatus.EXECUTING,
        }:
            raise ConnectorStateError(f"Action {record.action.id} is not eligible for execution")
        expected_tool = _INTERNAL_TOOL_BY_KIND.get(record.decision.validated.draft.kind)
        if expected_tool is None or tool != expected_tool:
            raise UnsupportedConnectorError("Policy execution tool is not bound to an internal Connector")

        parameters = record.decision.validated.draft.parameters
        input_sha256 = _canonical_sha256(
            {
                "decision": record.decision.model_dump(mode="json"),
                "audit_rows": [row.model_dump(mode="json") for row in audit_rows],
            }
        )
        payload, status, checks = self._create_payload(
            record,
            parameters=parameters,
            storage_root=storage_root,
            audit_rows=audit_rows,
            occurred_at=occurred_at,
        )
        verification_sha256 = _verification_sha256(
            record=record,
            action_id=str(record.action.id),
            execution_tool=tool,
            payload=payload,
            status=status,
            checks=checks,
        )
        artifact = ActionExecutionArtifact(
            workspace_id=record.action.workspace_id,
            case_id=record.action.case_id,
            action_id=record.action.id,
            execution_tool=tool,
            payload=payload,
            status=status,
            execution_input_sha256=input_sha256,
            verification_sha256=verification_sha256,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        return InternalConnectorResult(
            artifact=artifact,
            verification=ConnectorVerification(
                passed=True,
                checks=checks,
                verification_sha256=verification_sha256,
            ),
        )

    def rollback(
        self,
        artifact: ActionExecutionArtifact,
        *,
        storage_root: Path,
        occurred_at: datetime,
    ) -> InternalConnectorResult:
        payload = artifact.payload
        checks: tuple[str, ...]
        if isinstance(payload, AuditExportArtifact):
            payload, checks = self._archive_export(payload, storage_root)
        elif isinstance(payload, InternalTaskArtifact):
            checks = ("task_state_cancelled", "artifact_identity_preserved")
        elif isinstance(payload, MetricMonitorArtifact):
            checks = ("monitor_state_disabled", "artifact_identity_preserved")
        elif isinstance(payload, DataRequestArtifact):
            checks = ("data_request_cancelled", "artifact_identity_preserved")
        elif isinstance(payload, NoOpReceiptArtifact):
            checks = ("no_effect_to_reverse", "receipt_archived")
        else:  # pragma: no cover - discriminated union is exhaustive
            raise UnsupportedConnectorError("Unknown internal Action artifact")

        target_status = {
            ActionArtifactStatus.COMPLETED: ActionArtifactStatus.ARCHIVED,
            ActionArtifactStatus.AVAILABLE: ActionArtifactStatus.ARCHIVED,
            ActionArtifactStatus.OPEN: ActionArtifactStatus.CANCELLED,
            ActionArtifactStatus.ACTIVE: ActionArtifactStatus.DISABLED,
        }.get(artifact.status)
        if target_status is None:
            return InternalConnectorResult(
                artifact=artifact,
                verification=ConnectorVerification(
                    passed=True,
                    checks=("rollback_already_applied",),
                    verification_sha256=artifact.verification_sha256,
                ),
            )
        verification_sha256 = _verification_sha256(
            record=None,
            action_id=str(artifact.action_id),
            execution_tool=artifact.execution_tool,
            payload=payload,
            status=target_status,
            checks=checks,
        )
        rolled_back = artifact.rolled_back(
            payload=payload,
            verification_sha256=verification_sha256,
            occurred_at=occurred_at,
        )
        return InternalConnectorResult(
            artifact=rolled_back,
            verification=ConnectorVerification(
                passed=True,
                checks=checks,
                verification_sha256=verification_sha256,
            ),
        )

    @staticmethod
    def _execution_tool(record: ActionRecord) -> str:
        tool = record.decision.execution_tool
        if tool is not None:
            return tool
        if record.decision.validated.draft.kind is ActionKind.NO_OP:
            return _INTERNAL_TOOL_BY_KIND[ActionKind.NO_OP]
        raise UnsupportedConnectorError("Action has no allowlisted execution tool")

    def _create_payload(
        self,
        record: ActionRecord,
        *,
        parameters,
        storage_root: Path,
        audit_rows: tuple[AuditCohortRow, ...],
        occurred_at: datetime,
    ) -> tuple[ActionArtifactPayload, ActionArtifactStatus, tuple[str, ...]]:
        if isinstance(parameters, NoOpParameters):
            return (
                NoOpReceiptArtifact(reason=parameters.reason),
                ActionArtifactStatus.COMPLETED,
                ("no_external_effect", "receipt_persistable"),
            )
        if isinstance(parameters, InternalTaskParameters):
            return (
                InternalTaskArtifact(
                    owner_role=parameters.owner_role,
                    due_at=occurred_at + timedelta(days=parameters.due_days),
                    checklist=parameters.checklist,
                ),
                ActionArtifactStatus.OPEN,
                ("task_fields_match_policy", "task_due_date_bounded"),
            )
        if isinstance(parameters, MetricMonitorParameters):
            return (
                MetricMonitorArtifact(
                    metric_name=parameters.metric_name,
                    metric_observation_ids=parameters.metric_observation_ids,
                    comparison=parameters.comparison,
                    threshold=parameters.threshold,
                    cadence_hours=parameters.cadence_hours,
                    follow_up_after_days=parameters.follow_up_after_days,
                    next_evaluation_at=occurred_at + timedelta(hours=parameters.cadence_hours),
                ),
                ActionArtifactStatus.ACTIVE,
                ("monitor_contract_matches_policy", "next_check_scheduled"),
            )
        if isinstance(parameters, DataRequestParameters):
            return (
                DataRequestArtifact(
                    missing_fields=parameters.missing_fields,
                    due_at=occurred_at + timedelta(days=parameters.due_days),
                ),
                ActionArtifactStatus.OPEN,
                ("requested_fields_match_policy", "request_due_date_bounded"),
            )
        if isinstance(parameters, AuditExportParameters):
            payload = self._write_audit_export(
                record,
                parameters=parameters,
                storage_root=storage_root,
                audit_rows=audit_rows,
            )
            return (
                payload,
                ActionArtifactStatus.AVAILABLE,
                ("export_file_exists", "export_sha256_matches", "rows_bounded"),
            )
        raise UnsupportedConnectorError("External Action parameters cannot run in the internal Connector registry")

    @staticmethod
    def _write_audit_export(
        record: ActionRecord,
        *,
        parameters: AuditExportParameters,
        storage_root: Path,
        audit_rows: tuple[AuditCohortRow, ...],
    ) -> AuditExportArtifact:
        selected = audit_rows[: parameters.max_rows]
        relative = Path(
            str(record.action.workspace_id),
            str(record.action.case_id),
            "actions",
            str(record.action.id),
            f"audit.{parameters.format}",
        )
        path = storage_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if parameters.format == "jsonl":
            content = "".join(
                json.dumps(
                    row.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
                for row in selected
            ).encode("utf-8")
        else:
            output = io.StringIO(newline="")
            writer = csv.DictWriter(
                output,
                fieldnames=(
                    "evidence_id",
                    "summary",
                    "confidence",
                    "metric_observation_ids",
                ),
            )
            writer.writeheader()
            for row in selected:
                writer.writerow(
                    {
                        "evidence_id": str(row.evidence_id),
                        "summary": row.summary,
                        "confidence": row.confidence,
                        "metric_observation_ids": ";".join(str(value) for value in row.metric_observation_ids),
                    }
                )
            content = output.getvalue().encode("utf-8")
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        return AuditExportArtifact(
            format=parameters.format,
            relative_path=relative.as_posix(),
            sha256=sha256,
            row_count=len(selected),
            include_direct_identifiers=False,
        )

    @staticmethod
    def _archive_export(
        payload: AuditExportArtifact,
        storage_root: Path,
    ) -> tuple[AuditExportArtifact, tuple[str, ...]]:
        source = storage_root / payload.relative_path
        archived_relative = f"{payload.relative_path}.archived"
        target = storage_root / archived_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            if hashlib.sha256(source.read_bytes()).hexdigest() != payload.sha256:
                raise ConnectorStateError("Audit export changed before rollback verification")
            source.replace(target)
        if not target.is_file():
            raise ConnectorStateError("Audit export is missing during rollback")
        if hashlib.sha256(target.read_bytes()).hexdigest() != payload.sha256:
            raise ConnectorStateError("Archived export SHA-256 does not match")
        return (
            payload.model_copy(update={"relative_path": archived_relative}),
            ("source_export_removed", "archived_export_sha256_matches"),
        )
