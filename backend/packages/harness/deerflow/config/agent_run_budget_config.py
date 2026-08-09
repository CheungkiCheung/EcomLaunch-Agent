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
    allowed_subagent_types: list[str] | None = Field(
        default=None,
        description=("Optional allowlist of subagent types for this agent. None preserves DeerFlow's default behavior; an empty list disables subagent delegation."),
    )
    subagent_dependencies: dict[str, list[str]] | None = Field(
        default=None,
        description=("Optional specialist ordering constraints. A dependency is enforced when its specialist is also scheduled or has already started in the same user request, while standalone specialist calls remain available."),
    )
    direct_answer_patterns: list[str] | None = Field(
        default=None,
        description="Optional regular expressions that force a one-response, no-tool answer for configured short-query shapes",
    )
    direct_answer_exclude_patterns: list[str] | None = Field(
        default=None,
        description="Optional regular expressions that keep tools available even when a direct-answer pattern also matches",
    )
    complete_workflow_patterns: list[str] | None = Field(
        default=None,
        description="Optional regular expressions that activate all configured specialist dependencies for a complete workflow request",
    )
    complete_pack_initial_research_calls: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of bounded web_search/web_fetch attempts required before a single-agent complete Pack starts drafting. "
            "Failed attempts still count so unavailable public search degrades instead of blocking delivery."
        ),
    )
    required_completed_subagents: list[str] | None = Field(
        default=None,
        description="Optional specialist types that must complete before a configured complete pack can be presented",
    )
    compact_write_file_history: bool = Field(
        default=False,
        description="Replace large historical write_file payloads with compact file references on later lead-agent model calls",
    )
    finalize_after_subagent: str | None = Field(
        default=None,
        description="Optional specialist whose completion limits remaining lead-agent work to final file revision and presentation",
    )
    required_output_files: list[str] | None = Field(
        default=None,
        description="Optional complete-pack filename contract used by terminal delivery preflight",
    )
    auto_present_complete_pack: bool = Field(
        default=False,
        description=(
            "Once all required output files are present and required specialists have completed, "
            "limit the lead agent to deterministic presentation; a failed preflight temporarily "
            "allows only targeted file revision before presentation is retried"
        ),
    )
    require_evidence_checker: bool = Field(
        default=False,
        description="Require a successful evidence-checker subagent run before a complete configured pack can be presented",
    )
    validate_pack_before_present: bool = Field(
        default=False,
        description="Run deterministic evidence/source and no-sample consumer-claim checks before presenting a complete configured pack",
    )
    validate_pack_before_evidence: bool = Field(
        default=False,
        description="Run the configured complete-pack preflight before starting the terminal evidence specialist",
    )
    force_final_text_on_warning: bool = Field(
        default=False,
        description="Remove tools from the final warned model response so a bounded specialist must return its collected findings",
    )
    stop_message: str = Field(
        default="本次任务已达到执行预算，已停止继续调用工具。当前结果可能是部分完成，请以已生成文件和明确标注的证据缺口为准。",
        min_length=1,
        description="User-facing message used when the run budget stops additional tool work",
    )
