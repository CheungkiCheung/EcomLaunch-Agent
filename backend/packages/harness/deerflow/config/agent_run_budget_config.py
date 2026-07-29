"""Per-agent execution budgets for bounded lead-agent runs."""

from pydantic import BaseModel, Field


class AgentRunBudgetConfig(BaseModel):
    """Limits that stop one user request from expanding without bound.

    The lead-agent call and token limits are enforced at model boundaries. A
    completed text answer is never replaced merely because it crossed a limit;
    the limits prevent additional non-terminal tool work. Subagent count,
    duplicate specialist calls, and specialist timeouts are enforced before a
    subagent execution starts.
    """

    max_lead_model_calls: int = Field(
        ge=1,
        description="Maximum lead-agent model responses that may continue into non-terminal tool work",
    )
    max_subagent_calls: int = Field(
        ge=0,
        description="Maximum subagent executions started during one user request",
    )
    max_total_tokens: int = Field(
        ge=1,
        description="Maximum observed lead + merged subagent tokens before further tool work is stopped",
    )
    max_execution_seconds: int = Field(
        ge=1,
        description="Wall-time budget used to clamp subagent timeouts and stop further tool work",
    )
    deduplicate_subagents: bool = Field(
        default=True,
        description="Allow each subagent type to run at most once per user request",
    )
    stop_message: str = Field(
        default="本次任务已达到执行预算，已停止继续调用工具。当前结果可能是部分完成，请以已生成文件和明确标注的证据缺口为准。",
        min_length=1,
        description="User-facing message used when the run budget stops additional tool work",
    )
