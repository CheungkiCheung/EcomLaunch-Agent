"""Case-scoped assembly of prepared Path specs into a bounded fan-out."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.commerce.agents.evidence_barrier import EvidenceBarrier
from app.commerce.agents.fanout_checkpoint import FanoutCheckpointLedger
from app.commerce.agents.goal_loop import GoalLoopCheckpoint
from app.commerce.agents.subagent_committer import CommerceSubagentCommitter
from app.commerce.agents.subagent_fanout import (
    CommerceSubagentFanout,
    CommerceSubagentFanoutEntry,
    CommerceSubagentFanoutResult,
)
from app.commerce.agents.subagent_supervisor import CommerceSubagentSupervisor
from app.commerce.domain.ids import (
    AgentTaskId,
    CorrelationId,
    RunId,
    TraceId,
)
from app.commerce.evaluation.real_model_preflight import run_real_model_preflight
from app.commerce.persistence.runs import RunLeaseCredentials, SqlRunLeaseRepository


class CommerceSubagentPreflightError(RuntimeError):
    """Raised before fan-out when a fresh real-model gate is blocked."""


ToolBuilder = Callable[[Any], tuple[Any, ...]]
PreflightGate = Callable[[str], Awaitable[None]]
SupervisorFactory = Callable[..., Any]


@dataclass(frozen=True)
class PreparedCommercePath:
    """One versioned Path spec plus its context-scoped Tool factory."""

    spec: Any
    tool_builder: ToolBuilder


async def _default_preflight_gate(model_alias: str) -> None:
    result = await asyncio.to_thread(
        run_real_model_preflight,
        model_alias=model_alias,
    )
    if not result.passed:
        raise CommerceSubagentPreflightError(
            f"Fresh model preflight blocked: {result.status.value}"
        )


class CommerceSubagentCoordinator:
    """Create stable Path tasks and execute them through the common Harness."""

    def __init__(
        self,
        *,
        committer: CommerceSubagentCommitter,
        leases: SqlRunLeaseRepository,
        barrier: EvidenceBarrier,
        lease_ttl: timedelta,
        preflight_gate: PreflightGate = _default_preflight_gate,
        supervisor_factory: SupervisorFactory = CommerceSubagentSupervisor,
        fanout: CommerceSubagentFanout | None = None,
        poll_interval_seconds: float = 0.25,
        max_polls: int = 1_200,
    ) -> None:
        self._committer = committer
        self._leases = leases
        self._barrier = barrier
        self._lease_ttl = lease_ttl
        self._preflight_gate = preflight_gate
        self._supervisor_factory = supervisor_factory
        self._fanout = fanout or CommerceSubagentFanout(barrier=barrier)
        self._poll_interval_seconds = poll_interval_seconds
        self._max_polls = max_polls

    async def run(
        self,
        *,
        prepared_paths: tuple[PreparedCommercePath, ...],
        run_id: RunId,
        base_checkpoint: GoalLoopCheckpoint,
        lease: RunLeaseCredentials,
        correlation_id: CorrelationId,
    ) -> CommerceSubagentFanoutResult:
        if not prepared_paths:
            return await self._fanout.run(())
        if len(prepared_paths) > 3:
            raise ValueError("Commerce Coordinator supports at most three Paths")
        await asyncio.gather(
            *(
                self._preflight_gate(item.spec.plan.assignment.model_alias)
                for item in prepared_paths
            )
        )

        tasks = tuple(
            item.spec.build_task(
                run_id=run_id,
                task_id=self._task_id(run_id, item.spec.plan.context.path_type.value),
                lease_worker_id=lease.worker_id,
                fencing_token=lease.fencing_token,
                trace_id=TraceId.new(),
                correlation_id=correlation_id,
            )
            for item in prepared_paths
        )
        ledger = FanoutCheckpointLedger(base=base_checkpoint, tasks=tasks)
        entries: list[CommerceSubagentFanoutEntry] = []
        for prepared, task in zip(prepared_paths, tasks, strict=True):
            context = prepared.spec.plan.context
            adapter = prepared.spec.build_adapter(
                tools=prepared.tool_builder(context)
            )
            supervisor = self._supervisor_factory(
                adapter=adapter,
                committer=self._committer,
                leases=self._leases,
                lease_ttl=self._lease_ttl,
                poll_interval_seconds=self._poll_interval_seconds,
                max_polls=self._max_polls,
            )
            entries.append(
                CommerceSubagentFanoutEntry(
                    task=task,
                    context=context,
                    manifest=context.manifest,
                    pre_checkpoint=ledger.pre_checkpoint(task),
                    post_checkpoint_builder=ledger.post_checkpoint_builder(task),
                    lease=lease,
                    supervisor=supervisor,
                )
            )
        return await self._fanout.run(tuple(entries))

    @staticmethod
    def _task_id(run_id: RunId, path_type: str) -> AgentTaskId:
        return AgentTaskId(
            f"task_{uuid5(NAMESPACE_URL, f'{run_id}:{path_type}').hex}"
        )
