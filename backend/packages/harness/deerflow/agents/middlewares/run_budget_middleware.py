"""Bound one lead-agent request by model calls, tokens, and wall time."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse, hook_config
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.tool_call_metadata import clone_ai_message_with_tool_calls
from deerflow.config.agent_run_budget_config import AgentRunBudgetConfig

RUN_BUDGET_CONTEXT_KEY = "__deerflow_agent_run_budget"
TERMINAL_DELIVERY_TOOLS = frozenset({"present_files", "render_launch_pack"})
FINALIZATION_MESSAGE = """Execution budget finalization:
- This is the final model response available before the hard execution limit.
- Do not call more research or drafting tools.
- Return a concise result from the evidence already collected.
- Clearly mark failures, uncertainty, unsupported claims, and missing evidence.
- If you are the lead agent and final files already exist, `present_files` is the only allowed terminal tool."""
SPECIALIST_FINALIZATION_MESSAGE = """Specialist execution finalization:
- This is the final model response available for this specialist.
- No tools are available. Return the concise findings, assets, or audit verdict already supported by the collected evidence now.
- Clearly label evidence gaps and unsupported claims.
- Do not narrate another intended tool call, request more time, or repeat this instruction."""
DELIVERY_FINALIZATION_MESSAGE = """Terminal delivery finalization:
- `present_files` has already succeeded for this user request. Do not call any more tools.
- Return one concise, declarative delivery summary and the evidence-bounded decision.
- Tell the user the delivered files are visible in the file card below and in the header Files control.
- Do not expose `/mnt/user-data/outputs` or another internal sandbox path as the user's way to find the files.
- Do not start another phase, propose automatic follow-up work, offer options, ask for confirmation, or end with a question.
- Do not claim an audit passed unless the exact delivered files were audited."""
DELIVERY_COMPLETE_CONTENT = "文件已经交付，本次请求到此结束。"
MODEL_CALL_TIMEOUT_CONTENT = "模型服务未能在本次运行预算内返回结果，已停止等待。请稍后重试；本次没有生成可交付文件。"
DIRECT_ANSWER_TOOL_BLOCKED_CONTENT = "本次短问题未生成有效文本回答；已停止异常工具调用，未执行搜索、子智能体或文件操作。"
DIRECT_ANSWER_MESSAGE = """Configured direct-answer scope:
- Answer this short question now without tools, subagents, files, or additional research.
- Give one clear decision, the reason, and the smallest honest validation action.
- Treat missing market data, product facts, prices, performance, and customer behavior as unknown rather than inventing them.
- Do not use prevalence or certainty language such as "most users", "usually", "everyone", "大部分", "多数", or "普遍" unless the user supplied evidence for it.
- Do not propose fake listings, undisclosed fake preorders, fabricated reviews, false scarcity, or pretending that an unbuilt product already exists.
- Keep the answer concise and declarative; do not upsell more work or end with a question."""
COMPACTED_FILE_HISTORY_MESSAGE = """Earlier successful write_file payloads were removed from executable tool arguments in model history to control cost.
The writes listed below succeeded and the files on disk are authoritative. Missing historical content means "already written", never "write this placeholder".
Do not reread or grep them merely to confirm contents or existence. Only inspect a file when a deterministic preflight error identifies an exact revision that cannot be applied from the error itself."""
COMPLETE_PACK_PRESENTATION_MESSAGE = """Configured complete Pack is ready for deterministic presentation:
- Every required output file is present and the configured specialist sequence has completed.
- Do not read or grep the files, rewrite them, research, or call another specialist.
- Call present_files now with the complete configured file set; it performs the authoritative deterministic preflight."""
COMPLETE_PACK_RESEARCH_MESSAGE = """Configured Flash Pack public-signal research starts now:
- Run the remaining bounded web_search/web_fetch attempts now, batching independent searches in one response.
- Search only for directly relevant demand, competitor/price, scenario, or objection signals for the user's product and market.
- Do not read skills, inspect files, draft artifacts, call a subagent, or narrate future research.
- Search failures and blocked pages are valid unavailable evidence; do not retry equivalent queries beyond this bounded phase.
- Search snippets are discovery signals, not verified observed_public claims. Preserve exact URLs and downgrade unsupported conclusions to estimated or unavailable."""
COMPLETE_PACK_SPECIALIST_MESSAGE = """Configured complete Pack specialist orchestration is active:
- The launch Skill is already loaded in context. Do not read `/mnt/skills`, inspect files, draft artifacts, search from the lead agent, or narrate future work.
- Call exactly the next required specialist with `task`, one dependency-safe specialist per model response.
- Give that specialist a compact brief using the user request and already-returned prerequisite findings.
- Do not call any other specialist or tool in this response."""
COMPLETE_PACK_DRAFT_MESSAGE = """Configured complete Pack drafting starts now:
- All configured specialists completed. Use only their returned findings; do not start new research.
- Call render_launch_pack exactly once with one compact `spec` object; do not generate or pass full file contents.
- Include category, target_price, decision, decision_rationale, audience, and validation_goal. Add only concise evidence, competitors, hypotheses, and experiments already supported by specialist results.
- Evidence labels must be exactly observed_public, uploaded_real, estimated, assumption, or unavailable. observed_public requires a direct source URL; search-result and image-search URLs are discovery aids, never observed_public evidence.
- Keep the whole tool argument compact (normally under 1,500 output tokens). The renderer creates canonical files, runs deterministic preflight, and presents all seven artifacts in the same tool call.
- Use write_launch_pack or write_file only as a compatibility fallback when render_launch_pack is unavailable.
- Do not read, grep, research, call task, or call present_files separately."""
COMPLETE_PACK_FLASH_DRAFT_MESSAGE = """Configured Flash Pack drafting starts now:
- The bounded public-signal research stage completed or degraded. Use only those findings; do not start new research.
- Call render_launch_pack exactly once with one compact `spec` object; do not generate or pass full file contents.
- Include category, target_price, decision, decision_rationale, audience, and validation_goal. Keep evidence and competitor rows concise; observed_public requires a direct source URL, while search snippets must be estimated or unavailable.
- Keep the whole tool argument compact (normally under 1,200 output tokens). The renderer creates, preflights, and presents all seven canonical files in the same tool call.
- Use write_launch_pack or write_file only as a compatibility fallback when render_launch_pack is unavailable.
- Do not read, grep, research, call task, or call present_files separately."""
COMPLETE_PACK_ASSEMBLY_MESSAGE = """Configured complete Pack assembly is in progress:
- At least one required output file was written successfully in this request; use the latest write_file result's missing-file list.
- Do not read, grep, research, present an incomplete Pack, or call another specialist.
- Create only the remaining configured files with write_file, using str_replace only for a necessary targeted correction."""
COMPLETE_PACK_REVISION_MESSAGE = """Configured complete Pack preflight blocked delivery:
- Use only the exact file and issue details in the latest present_files result.
- Do not read, grep, research, or call another specialist.
- Apply the smallest required corrections with write_file or str_replace. Presentation will be retried only after every correction in the batch succeeds.
- If the reported issue cannot be corrected safely, return a concise blocked result without another tool call."""
POST_SUBAGENT_FINALIZATION_MESSAGE = """Configured terminal specialist has completed:
- Do not call research, read, grep, task, clarification, or any new drafting phase.
- Use the specialist's returned findings already in context.
- If revisions are required, apply them now with the minimum write_file or str_replace calls; otherwise call present_files now.
- After any revision, call present_files on the complete configured file set. Do not perform another manual check first.
- If delivery cannot safely pass, return a concise partial/blocked result without asking a question."""
POST_SUBAGENT_FAILURE_MESSAGE = """Configured specialist workflow finished without authorizing delivery:
- Do not call any more tools, retry delivery, restart the specialist, or begin another phase.
- Return one concise, declarative partial or blocked result using the specialist status already in context.
- State that the files were not delivered and identify the unresolved audit boundary.
- Do not offer options, request confirmation, or end with a question."""
CANDIDATE_PREFLIGHT_REVISION_MESSAGE = """Candidate Launch Pack preflight failed once:
- Use the exact blocking issues in the most recent task result; do not read, grep, research, or retry the audit yet.
- Apply all listed corrections now in one response using only write_file or str_replace.
- For consumer-copy findings, remove the entire reported line or replace it with a neutral user-problem question. Do not retain any reported feature term in a title, description, concept label, disclaimer, or question.
- Keep every other file and claim unchanged. The next response will be reserved for starting the evidence checker."""
CANDIDATE_PREFLIGHT_AUDIT_MESSAGE = """Candidate Launch Pack revisions have been applied:
- Call the configured evidence-checker now using the existing seven files.
- Do not read, grep, draft, present files, or call any other specialist."""
INTERNAL_HUMAN_MESSAGE_NAMES = frozenset(
    {
        "candidate_preflight_audit",
        "candidate_preflight_revision",
        "direct_answer_execution",
        "compacted_file_history",
        "complete_pack_draft",
        "complete_pack_assembly",
        "complete_pack_presentation",
        "complete_pack_research",
        "complete_pack_revision",
        "complete_pack_specialist",
        "post_subagent_failure",
        "post_subagent_finalization",
        "run_budget_finalization",
        "terminal_delivery_finalization",
    }
)


def _current_turn_messages(messages: list[Any]) -> list[Any]:
    """Return messages belonging to the latest user request only."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage) and messages[index].name not in INTERNAL_HUMAN_MESSAGE_NAMES:
            return messages[index + 1 :]
    return messages


def _message_total_tokens(message: Any) -> int:
    usage = getattr(message, "usage_metadata", None)
    if not isinstance(usage, dict):
        return 0
    value = usage.get("total_tokens", 0)
    return value if isinstance(value, int) and value > 0 else 0


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts)


def _latest_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and message.name not in INTERNAL_HUMAN_MESSAGE_NAMES:
            return _message_text(message)
    return ""


def _compact_write_file_args(args: Any) -> tuple[Any, dict[str, Any] | None]:
    if not isinstance(args, dict):
        return args, None
    content = args.get("content")
    if not isinstance(content, str) or len(content) <= 512:
        return args, None

    path = args.get("file_path") or args.get("filepath") or args.get("path") or "the output file"
    compacted = dict(args)
    compacted.pop("content", None)
    metadata = {
        "path": path,
        "bytes": len(content.encode("utf-8")),
        "status": "success",
    }
    return compacted, metadata


def _compact_write_file_history(messages: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    completed_write_ids = {str(message.tool_call_id) for message in messages if isinstance(message, ToolMessage) and message.status != "error" and not str(message.content).lstrip().startswith("Error:")}
    compacted_messages: list[Any] = []
    compacted_writes: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, AIMessage) or not message.tool_calls:
            compacted_messages.append(message)
            continue

        changed_ids: dict[str, dict[str, Any]] = {}
        compacted_calls: list[dict[str, Any]] = []
        for tool_call in message.tool_calls:
            copied_call = dict(tool_call)
            call_id = copied_call.get("id")
            if copied_call.get("name") == "write_file" and isinstance(call_id, str) and call_id in completed_write_ids:
                compacted_args, metadata = _compact_write_file_args(copied_call.get("args"))
                if metadata is not None:
                    copied_call["args"] = compacted_args
                    if call_id:
                        changed_ids[call_id] = compacted_args
                    compacted_writes.append(metadata)
            compacted_calls.append(copied_call)

        if not changed_ids:
            compacted_messages.append(message)
            continue

        additional_kwargs = dict(message.additional_kwargs or {})
        raw_tool_calls = additional_kwargs.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            compacted_raw_calls: list[Any] = []
            for raw_call in raw_tool_calls:
                if not isinstance(raw_call, dict) or raw_call.get("id") not in changed_ids:
                    compacted_raw_calls.append(raw_call)
                    continue
                raw_copy = dict(raw_call)
                function = raw_copy.get("function")
                if isinstance(function, dict):
                    function_copy = dict(function)
                    function_copy["arguments"] = json.dumps(changed_ids[raw_call["id"]], ensure_ascii=False)
                    raw_copy["function"] = function_copy
                compacted_raw_calls.append(raw_copy)
            additional_kwargs["tool_calls"] = compacted_raw_calls

        compacted_messages.append(
            message.model_copy(
                update={
                    "tool_calls": compacted_calls,
                    "additional_kwargs": additional_kwargs,
                }
            )
        )
    return compacted_messages, compacted_writes


def _has_completed_terminal_delivery(messages: list[Any]) -> bool:
    """Return whether ``present_files`` succeeded in the latest user turn."""
    turn_messages = _current_turn_messages(messages)
    delivery_call_ids = {
        str(tool_call.get("id"))
        for message in turn_messages
        if isinstance(message, AIMessage)
        for tool_call in (message.tool_calls or [])
        if tool_call.get("name") in TERMINAL_DELIVERY_TOOLS and tool_call.get("id")
    }
    if not delivery_call_ids:
        return False

    return any(
        isinstance(message, ToolMessage)
        and str(message.tool_call_id) in delivery_call_ids
        and message.status != "error"
        and "Successfully presented files" in str(message.content)
        for message in turn_messages
    )


class RunBudgetMiddleware(AgentMiddleware[AgentState]):
    """Prevent an agent run from repeatedly expanding after useful work exists."""

    def __init__(self, config: AgentRunBudgetConfig):
        super().__init__()
        self.config = config

    def _initialize(self, runtime: Runtime) -> None:
        context = getattr(runtime, "context", None)
        if not isinstance(context, dict):
            return

        started_at = time.monotonic()
        context[RUN_BUDGET_CONTEXT_KEY] = {
            "config": self.config.model_dump(),
            "started_at_monotonic": started_at,
            "deadline_monotonic": started_at + self.config.max_execution_seconds,
            "subagent_calls_started": 0,
            "subagent_types_started": set(),
            "subagent_types_completed": set(),
            "required_output_files_written": set(),
        }

    def _remaining_model_call_seconds(self, runtime: Runtime) -> float | None:
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict):
            return None
        deadline = budget_state.get("deadline_monotonic")
        if not isinstance(deadline, (int, float)):
            return None
        remaining = max(0.0, float(deadline) - time.monotonic())
        if self.config.max_model_call_seconds is None:
            return remaining
        return min(remaining, float(self.config.max_model_call_seconds))

    @staticmethod
    def _model_call_timeout_response(timeout_seconds: float) -> AIMessage:
        return AIMessage(
            content=MODEL_CALL_TIMEOUT_CONTENT,
            additional_kwargs={
                "deerflow_error_fallback": True,
                "hide_from_ui": True,
                "error_type": "RunBudgetModelTimeout",
                "error_reason": "run_budget_timeout",
                "error_detail": f"Lead model call exceeded its {timeout_seconds:.1f}s effective run-budget cap",
            },
        )

    @override
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._initialize(runtime)
        return None

    @override
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._initialize(runtime)
        return None

    def _stop_reason(self, messages: list[Any], runtime: Runtime) -> str | None:
        turn_messages = _current_turn_messages(messages)
        lead_model_calls = sum(isinstance(message, AIMessage) for message in turn_messages)
        if lead_model_calls >= self.config.max_lead_model_calls:
            return f"主智能体模型调用上限 {self.config.max_lead_model_calls} 次"

        total_tokens = sum(_message_total_tokens(message) for message in turn_messages)
        if total_tokens >= self.config.max_total_tokens:
            return f"Token 上限 {self.config.max_total_tokens}"

        context = getattr(runtime, "context", None)
        if isinstance(context, dict):
            budget_state = context.get(RUN_BUDGET_CONTEXT_KEY)
            if isinstance(budget_state, dict):
                # Verification loop exhausted: stop revising, deliver partial.
                if budget_state.get("loop_exhausted") is True:
                    return "验证循环已达最大修订次数，停止继续修改，交付当前结果"
                deadline = budget_state.get("deadline_monotonic")
                if isinstance(deadline, (int, float)) and time.monotonic() >= deadline:
                    return f"时间上限 {self.config.max_execution_seconds} 秒"

        return None

    def _finalization_reason(self, messages: list[Any], runtime: Runtime) -> str | None:
        turn_messages = _current_turn_messages(messages)
        lead_model_calls = sum(isinstance(message, AIMessage) for message in turn_messages)
        if lead_model_calls >= self.config.max_lead_model_calls - 1:
            return "model_calls"

        total_tokens = sum(_message_total_tokens(message) for message in turn_messages)
        token_warning_threshold = max(1, int(self.config.max_total_tokens * 0.8))
        if total_tokens >= token_warning_threshold:
            return "tokens"

        context = getattr(runtime, "context", None)
        if isinstance(context, dict):
            budget_state = context.get(RUN_BUDGET_CONTEXT_KEY)
            if isinstance(budget_state, dict):
                deadline = budget_state.get("deadline_monotonic")
                if isinstance(deadline, (int, float)):
                    remaining = deadline - time.monotonic()
                    warning_window = max(5, min(30, self.config.max_execution_seconds // 5))
                    if remaining <= warning_window:
                        return "wall_time"

        return None

    def _is_direct_answer_request(self, messages: list[Any]) -> bool:
        patterns = self.config.direct_answer_patterns or []
        if not patterns:
            return False
        user_text = _latest_user_text(messages)
        if not user_text:
            return False

        exclude_patterns = self.config.direct_answer_exclude_patterns or []
        if any(re.search(pattern, user_text, re.IGNORECASE) for pattern in exclude_patterns):
            return False
        return any(re.search(pattern, user_text, re.IGNORECASE) for pattern in patterns)

    def _is_complete_workflow_request(self, messages: list[Any]) -> bool:
        """Return True when the latest user text matches the configured
        complete-workflow patterns (e.g. "Launch Validation Pack")."""
        patterns = self.config.complete_workflow_patterns or []
        if not patterns:
            return False
        user_text = _latest_user_text(messages)
        if not user_text:
            return False
        return any(re.search(pattern, user_text, re.IGNORECASE) for pattern in patterns)

    def _has_failed_preflight(self, messages: list[Any]) -> bool:
        """Return whether the latest ``present_files`` attempt failed.

        An earlier failed preflight is part of a healthy verification loop. It
        must stop forcing the model back into that loop after a later retry has
        successfully delivered the pack.
        """
        present_outcomes = [result for _, name, _args, result in self._tool_outcomes(messages) if name in TERMINAL_DELIVERY_TOOLS]
        return bool(present_outcomes) and not self._tool_succeeded(present_outcomes[-1])

    def _terminal_subagent_completed(self, runtime: Runtime) -> bool:
        subagent_type = self.config.finalize_after_subagent
        if not subagent_type:
            return False
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict):
            return False
        completed_types = budget_state.get("subagent_types_completed", set())
        if not isinstance(completed_types, set):
            completed_types = set(completed_types) if isinstance(completed_types, (list, tuple)) else set()
        return subagent_type in completed_types

    def _terminal_subagent_finished(self, runtime: Runtime) -> bool:
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict):
            return False
        return budget_state.get("terminal_subagent_finished") is True or self._terminal_subagent_completed(runtime)

    def _terminal_delivery_blocked(self, runtime: Runtime) -> bool:
        if not self._required_subagents_completed(runtime):
            return True
        if not self.config.require_evidence_checker:
            return False
        if not self._evidence_checker_completed(runtime):
            return True
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        return isinstance(budget_state, dict) and budget_state.get("evidence_checker_verdict") == "blocked"

    def _evidence_checker_completed(self, runtime: Runtime) -> bool:
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict):
            return False
        budget_config = budget_state.get("config")
        if isinstance(budget_config, dict) and not budget_config.get("require_evidence_checker"):
            return True
        return budget_state.get("evidence_checker_completed") is True

    def _required_subagents_completed(self, runtime: Runtime) -> bool:
        required = self.config.required_completed_subagents or []
        if not required:
            return True
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict):
            return False
        completed = budget_state.get("subagent_types_completed", set())
        if not isinstance(completed, set):
            completed = set(completed) if isinstance(completed, (list, tuple)) else set()
        degraded = budget_state.get("subagent_types_degraded", {})
        degraded_names = set(degraded) if isinstance(degraded, dict) else set()
        return all(name in completed or name in degraded_names for name in required)

    def _next_required_subagent(self, runtime: Runtime) -> str | None:
        required = self.config.required_completed_subagents or []
        if not required:
            return None
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict):
            return required[0]
        completed = budget_state.get("subagent_types_completed", set())
        if not isinstance(completed, set):
            completed = set(completed) if isinstance(completed, (list, tuple)) else set()
        degraded = budget_state.get("subagent_types_degraded", {})
        degraded_names = set(degraded) if isinstance(degraded, dict) else set()
        return next((name for name in required if name not in completed and name not in degraded_names), None)

    def _terminal_delivery_is_ready(self, runtime: Runtime) -> bool:
        if not self._required_subagents_completed(runtime):
            return False
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict) or not self._evidence_checker_completed(runtime):
            return False
        if not self.config.require_evidence_checker:
            return True
        verdict = budget_state.get("evidence_checker_verdict")
        if verdict == "pass":
            return True
        if verdict == "revise":
            return budget_state.get("post_terminal_revision_started") is True
        return False

    def _configured_present_files_call(self, runtime: Runtime) -> dict[str, Any] | None:
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict):
            return None
        budget_config = budget_state.get("config")
        required_files = budget_config.get("required_output_files") if isinstance(budget_config, dict) else None
        if not isinstance(required_files, list) or not required_files:
            return None
        filepaths = [f"/mnt/user-data/outputs/{name}" for name in required_files if isinstance(name, str) and name]
        if not filepaths:
            return None
        return {
            "name": "present_files",
            "args": {"filepaths": filepaths},
            "id": f"call_terminal_present_{uuid.uuid4().hex}",
            "type": "tool_call",
        }

    def _configured_complete_pack_research_calls(self, messages: list[Any]) -> list[dict[str, Any]]:
        remaining = max(
            0,
            self.config.complete_pack_initial_research_calls - self._complete_pack_research_attempts(messages),
        )
        if remaining == 0:
            return []
        user_text = re.sub(r"\s+", " ", _latest_user_text(messages)).strip()
        if not user_text:
            return []
        query_suffixes = [
            "市场需求 竞品 价格 公开信号",
            "用户痛点 使用场景 公开评价",
        ]
        calls: list[dict[str, Any]] = []
        for index in range(remaining):
            suffix = query_suffixes[index % len(query_suffixes)]
            calls.append(
                {
                    "name": "web_search",
                    "args": {"query": f"{user_text[:240]} {suffix}", "max_results": 5},
                    "id": f"call_complete_pack_search_{uuid.uuid4().hex}",
                    "type": "tool_call",
                }
            )
        return calls

    @staticmethod
    def _tool_outcomes(messages: list[Any]) -> list[tuple[int, str, dict[str, Any], ToolMessage]]:
        calls: dict[str, tuple[str, dict[str, Any]]] = {}
        outcomes: list[tuple[int, str, dict[str, Any], ToolMessage]] = []
        for index, message in enumerate(_current_turn_messages(messages)):
            if isinstance(message, AIMessage):
                for call in message.tool_calls or []:
                    call_id = call.get("id")
                    name = call.get("name")
                    args = call.get("args")
                    if isinstance(call_id, str) and call_id and isinstance(name, str):
                        calls[call_id] = (name, args if isinstance(args, dict) else {})
                continue
            if not isinstance(message, ToolMessage):
                continue
            call = calls.get(str(message.tool_call_id))
            if call is not None:
                outcomes.append((index, call[0], call[1], message))
        return outcomes

    @staticmethod
    def _tool_succeeded(message: ToolMessage) -> bool:
        return message.status != "error" and not str(message.content).lstrip().startswith("Error:")

    def _complete_pack_written_names(self, messages: list[Any], runtime: Runtime) -> set[str]:
        required = self.config.required_output_files or []
        required_names = {name for name in required if isinstance(name, str) and name}
        if not required_names:
            return set()

        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        confirmed: set[str] = set()
        if isinstance(budget_state, dict):
            written = budget_state.get("required_output_files_written")
            if isinstance(written, set):
                confirmed.update(name for name in written if isinstance(name, str))
            elif isinstance(written, (list, tuple)):
                confirmed.update(name for name in written if isinstance(name, str))

        for _, name, args, result in self._tool_outcomes(messages):
            if name not in {"write_file", "str_replace"} or not self._tool_succeeded(result):
                continue
            path = args.get("path") or args.get("file_path") or args.get("filepath")
            if not isinstance(path, str):
                continue
            prefix = "/mnt/user-data/outputs/"
            if not path.startswith(prefix):
                continue
            relative = path[len(prefix) :].strip("/")
            if relative and "/" not in relative:
                confirmed.add(relative)
        return confirmed.intersection(required_names)

    def _complete_pack_files_ready(self, messages: list[Any], runtime: Runtime) -> bool:
        required_names = {name for name in (self.config.required_output_files or []) if isinstance(name, str) and name}
        if not required_names:
            return False
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if isinstance(budget_state, dict) and budget_state.get("required_output_files_ready") is True:
            return True
        return required_names.issubset(self._complete_pack_written_names(messages, runtime))

    def _complete_pack_research_attempts(self, messages: list[Any]) -> int:
        return sum(
            1
            for _, name, _args, _result in self._tool_outcomes(messages)
            if name in {"web_search", "web_fetch"}
        )

    def _complete_pack_phase(self, messages: list[Any], runtime: Runtime) -> str | None:
        if not self.config.auto_present_complete_pack:
            return None
        if not self._terminal_delivery_is_ready(runtime):
            return None
        required_research = self.config.complete_pack_initial_research_calls
        if (
            required_research > 0
            and not self._complete_pack_written_names(messages, runtime)
            and self._complete_pack_research_attempts(messages) < required_research
        ):
            return "research"
        if not self._complete_pack_files_ready(messages, runtime):
            return "assemble" if self._complete_pack_written_names(messages, runtime) else "draft"

        outcomes = self._tool_outcomes(messages)
        present_outcomes = [outcome for outcome in outcomes if outcome[1] in TERMINAL_DELIVERY_TOOLS]
        if not present_outcomes:
            return "present"

        last_present = present_outcomes[-1]
        if self._tool_succeeded(last_present[3]):
            return None

        revision_outcomes = [outcome for outcome in outcomes if outcome[0] > last_present[0] and outcome[1] in {"write_file", "str_replace"}]
        if not revision_outcomes:
            return "revise"
        return "present" if all(self._tool_succeeded(result) for _, _, _, result in revision_outcomes) else "revise"

    def _candidate_preflight_state(self, runtime: Runtime) -> tuple[int, bool]:
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if not isinstance(budget_state, dict) or budget_state.get("terminal_subagent_finished") is True:
            return 0, False
        failures = budget_state.get("terminal_preflight_failures", 0)
        failures = failures if isinstance(failures, int) and failures >= 0 else 0
        return failures, budget_state.get("candidate_preflight_revision_started") is True

    def _mark_candidate_preflight_revision(self, tool_calls: list[dict[str, Any]], runtime: Runtime) -> None:
        failures, revision_started = self._candidate_preflight_state(runtime)
        if failures != 1 or revision_started:
            return
        if not any(call.get("name") in {"write_file", "str_replace"} for call in tool_calls):
            return
        context = getattr(runtime, "context", None)
        budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
        if isinstance(budget_state, dict):
            budget_state["candidate_preflight_revision_started"] = True

    def _filter_post_subagent_tool_calls(self, tool_calls: list[dict[str, Any]], runtime: Runtime) -> list[dict[str, Any]]:
        """Keep only deterministic revision/delivery calls after the terminal specialist."""
        if self._terminal_delivery_blocked(runtime):
            return []
        revision_calls = [call for call in tool_calls if call.get("name") in {"write_file", "str_replace"}]
        if revision_calls:
            context = getattr(runtime, "context", None)
            budget_state = context.get(RUN_BUDGET_CONTEXT_KEY) if isinstance(context, dict) else None
            if isinstance(budget_state, dict):
                budget_state["post_terminal_revision_started"] = True
            return revision_calls
        present_calls = [call for call in tool_calls if call.get("name") == "present_files"]
        if present_calls and self._terminal_delivery_is_ready(runtime):
            return present_calls[:1]
        if self._terminal_delivery_is_ready(runtime):
            configured_call = self._configured_present_files_call(runtime)
            if configured_call is not None:
                return [configured_call]
        return []

    def _augment_request(self, request: ModelRequest) -> ModelRequest:
        if self.config.compact_write_file_history:
            compacted_messages, compacted_writes = _compact_write_file_history(request.messages)
            if compacted_writes:
                compacted_summary = json.dumps(compacted_writes, ensure_ascii=False, separators=(",", ":"))
                request = request.override(
                    messages=[
                        *compacted_messages,
                        HumanMessage(
                            content=f"{COMPACTED_FILE_HISTORY_MESSAGE}\nSuccessful writes: {compacted_summary}",
                            name="compacted_file_history",
                            additional_kwargs={"hide_from_ui": True},
                        ),
                    ]
                )

        if self._is_direct_answer_request(request.messages):
            messages = [
                *request.messages,
                HumanMessage(
                    content=DIRECT_ANSWER_MESSAGE,
                    name="direct_answer_execution",
                    additional_kwargs={"hide_from_ui": True},
                ),
            ]
            return request.override(messages=messages, tools=[])

        next_required_subagent = self._next_required_subagent(request.runtime)
        if self._is_complete_workflow_request(request.messages) and next_required_subagent is not None:
            finalization_message = f"{COMPLETE_PACK_SPECIALIST_MESSAGE}\n- Next required specialist: {next_required_subagent}."
            finalization_name = "complete_pack_specialist"
            request = request.override(tools=[tool for tool in request.tools if getattr(tool, "name", None) == "task"])
        elif _has_completed_terminal_delivery(request.messages):
            finalization_message = DELIVERY_FINALIZATION_MESSAGE
            finalization_name = "terminal_delivery_finalization"
        elif self._terminal_subagent_finished(request.runtime):
            if self._terminal_delivery_blocked(request.runtime):
                finalization_message = POST_SUBAGENT_FAILURE_MESSAGE
                finalization_name = "post_subagent_failure"
                request = request.override(tools=[])
            else:
                finalization_message = POST_SUBAGENT_FINALIZATION_MESSAGE
                finalization_name = "post_subagent_finalization"
                allowed_tools = {"write_file", "str_replace", "present_files"}
                request = request.override(tools=[tool for tool in request.tools if getattr(tool, "name", None) in allowed_tools])
        elif self._candidate_preflight_state(request.runtime)[0] == 1:
            _, revision_started = self._candidate_preflight_state(request.runtime)
            if revision_started:
                finalization_message = CANDIDATE_PREFLIGHT_AUDIT_MESSAGE
                finalization_name = "candidate_preflight_audit"
                allowed_tools = {"task"}
            else:
                finalization_message = CANDIDATE_PREFLIGHT_REVISION_MESSAGE
                finalization_name = "candidate_preflight_revision"
                allowed_tools = {"write_file", "str_replace"}
            request = request.override(tools=[tool for tool in request.tools if getattr(tool, "name", None) in allowed_tools])
        elif (complete_pack_phase := self._complete_pack_phase(request.messages, request.runtime)) is not None:
            if complete_pack_phase == "present":
                finalization_message = COMPLETE_PACK_PRESENTATION_MESSAGE
                finalization_name = "complete_pack_presentation"
                allowed_tools = {"present_files"}
            elif complete_pack_phase == "revise":
                finalization_message = COMPLETE_PACK_REVISION_MESSAGE
                finalization_name = "complete_pack_revision"
                allowed_tools = {"write_file", "str_replace"}
            elif complete_pack_phase == "draft":
                finalization_message = (
                    COMPLETE_PACK_FLASH_DRAFT_MESSAGE
                    if self.config.complete_pack_initial_research_calls > 0
                    else COMPLETE_PACK_DRAFT_MESSAGE
                )
                finalization_name = "complete_pack_draft"
                allowed_tools = {"render_launch_pack", "write_launch_pack", "write_file"}
            elif complete_pack_phase == "research":
                completed_research = self._complete_pack_research_attempts(request.messages)
                remaining_research = max(0, self.config.complete_pack_initial_research_calls - completed_research)
                finalization_message = f"{COMPLETE_PACK_RESEARCH_MESSAGE}\n- Remaining research attempts in this phase: {remaining_research}."
                finalization_name = "complete_pack_research"
                allowed_tools = {"web_search", "web_fetch"}
            else:
                finalization_message = COMPLETE_PACK_ASSEMBLY_MESSAGE
                finalization_name = "complete_pack_assembly"
                allowed_tools = {"write_file", "str_replace"}
            request = request.override(tools=[tool for tool in request.tools if getattr(tool, "name", None) in allowed_tools])
        elif self._finalization_reason(request.messages, request.runtime) is not None:
            finalization_message = SPECIALIST_FINALIZATION_MESSAGE if self.config.force_final_text_on_warning else FINALIZATION_MESSAGE
            finalization_name = "run_budget_finalization"
            if self.config.force_final_text_on_warning:
                request = request.override(tools=[])
        else:
            return request
        messages = [
            *request.messages,
            HumanMessage(
                content=finalization_message,
                name=finalization_name,
                additional_kwargs={"hide_from_ui": True},
            ),
        ]
        return request.override(messages=messages)

    def _apply(self, state: AgentState, runtime: Runtime) -> dict | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        tool_calls = list(last.tool_calls or [])
        # Direct-answer routing is terminal after exactly one model response.
        # The pre-model hook removes all tools, but this guard is still needed
        # before the generic complete-Pack state machine below: otherwise an
        # agent with auto_present_complete_pack enabled can inject research and
        # renderer calls after a valid short answer, causing an endless loop.
        if self._is_direct_answer_request(messages[:-1]):
            if not tool_calls:
                return None
            existing_content = last.content.strip() if isinstance(last.content, str) else ""
            return {
                "messages": [
                    clone_ai_message_with_tool_calls(
                        last,
                        [],
                        content=existing_content or DIRECT_ANSWER_TOOL_BLOCKED_CONTENT,
                    )
                ]
            }
        self._mark_candidate_preflight_revision(tool_calls, runtime)
        if self._terminal_subagent_finished(runtime) and not _has_completed_terminal_delivery(messages[:-1]):
            filtered_calls = self._filter_post_subagent_tool_calls(tool_calls, runtime)
            if filtered_calls != tool_calls:
                existing_content = last.content.strip() if isinstance(last.content, str) else ""
                if not filtered_calls and self._terminal_delivery_blocked(runtime):
                    existing_content = "证据审计未完成或已阻止交付；文件未向用户展示，本次请求以部分完成状态结束。"
                return {"messages": [clone_ai_message_with_tool_calls(last, filtered_calls, content=existing_content)]}

        next_required_subagent = self._next_required_subagent(runtime)
        if self._is_complete_workflow_request(messages[:-1]) and next_required_subagent is not None and tool_calls:
            task_calls = [
                call
                for call in tool_calls
                if call.get("name") == "task"
                and isinstance(call.get("args"), dict)
                and call["args"].get("subagent_type") == next_required_subagent
            ][:1]
            if task_calls != tool_calls:
                if task_calls:
                    return {"messages": [clone_ai_message_with_tool_calls(last, task_calls, content="")]}
                reason = self._stop_reason(messages, runtime)
                if reason is None:
                    return {"jump_to": "model"}
                return {
                    "messages": [
                        clone_ai_message_with_tool_calls(
                            last,
                            [],
                            content=f"Launch Pack 专家流程未完成。停止原因：{reason}。",
                        )
                    ]
                }

        complete_pack_phase = self._complete_pack_phase(messages[:-1], runtime)
        if complete_pack_phase == "present":
            present_calls = [call for call in tool_calls if call.get("name") == "present_files"]
            configured_call = self._configured_present_files_call(runtime)
            # Always use the configured canonical filename set. Some providers
            # normalize hyphens to underscores in tool arguments, which used to
            # present non-existent aliases and report a false success.
            filtered_calls = present_calls[:1]
            if configured_call is not None:
                configured_paths = configured_call["args"]["filepaths"]
                presented_paths = (
                    filtered_calls[0].get("args", {}).get("filepaths")
                    if filtered_calls
                    else None
                )
                if presented_paths != configured_paths:
                    filtered_calls = [configured_call]
            if filtered_calls != tool_calls:
                return {"messages": [clone_ai_message_with_tool_calls(last, filtered_calls, content="")]}
        elif complete_pack_phase in {"research", "draft", "assemble", "revise"} and tool_calls:
            if complete_pack_phase == "research":
                allowed_revision_tools = {"web_search", "web_fetch"}
            else:
                allowed_revision_tools = {"render_launch_pack", "write_launch_pack", "write_file"} if complete_pack_phase == "draft" else {"write_file", "str_replace"}
            revision_calls = [call for call in tool_calls if call.get("name") in allowed_revision_tools]
            if revision_calls != tool_calls:
                # A model can still emit a forbidden read/search/task call even
                # after the complete-Pack phase has restricted the tool set.
                # Returning an empty AI message would make LangGraph treat the
                # run as successfully completed with no artifacts. Re-enter the
                # model while budget remains so the phase instruction can steer
                # it toward the required write_file calls.
                if not revision_calls:
                    if complete_pack_phase == "research":
                        configured_calls = self._configured_complete_pack_research_calls(messages[:-1])
                        if configured_calls:
                            return {"messages": [clone_ai_message_with_tool_calls(last, configured_calls, content="")]}
                    reason = self._stop_reason(messages, runtime)
                    if reason is None:
                        return {"jump_to": "model"}
                    stopped = clone_ai_message_with_tool_calls(
                        last,
                        [],
                        content=(
                            f"Launch Pack 未完成修订或交付，仍有必需文件未通过确定性预检。\n\n"
                            f"停止原因：{reason}。"
                        ),
                    )
                    return {"messages": [stopped]}
                existing_content = last.content.strip() if isinstance(last.content, str) else ""
                return {"messages": [clone_ai_message_with_tool_calls(last, revision_calls, content=existing_content)]}

        if complete_pack_phase in {"research", "draft", "assemble", "revise"} and not tool_calls:
            if complete_pack_phase == "research":
                configured_calls = self._configured_complete_pack_research_calls(messages[:-1])
                if configured_calls:
                    return {"messages": [clone_ai_message_with_tool_calls(last, configured_calls, content="")]}
            reason = self._stop_reason(messages, runtime)
            if reason is None:
                # A toolless model response is an intent, not a terminal result:
                # re-enter the model so it can emit the required write/presentation
                # call, including after a deterministic preflight failure.
                return {"jump_to": "model"}
            stopped = clone_ai_message_with_tool_calls(
                last,
                [],
                content=(f"Launch Pack 未完成修订或交付，仍有必需文件未通过确定性预检。\n\n停止原因：{reason}。"),
            )
            return {"messages": [stopped]}

        # A completed text response is already terminal and useful. Budgets stop
        # further work; they do not overwrite an answer after it has been written.
        if not tool_calls:
            # A complete-workflow request (Launch Validation Pack) must not end
            # with a toolless text response before every required specialist
            # has completed — models occasionally narrate "I'll start the
            # researcher" without emitting the task call, which LangGraph would
            # otherwise treat as a finished answer.
            if self._is_complete_workflow_request(messages) and not self._required_subagents_completed(runtime):
                reason = self._stop_reason(messages, runtime)
                if reason is None:
                    return {"jump_to": "model"}
            # Fallback: if a present_files preflight already failed for this
            # request (the pack exists but delivery was blocked), a toolless
            # response must not end the run — re-enter the model so it can
            # revise the flagged files and retry delivery. This covers cases
            # where budget_state sync is unreliable (e.g. subagent runs in a
            # background thread).
            if self._is_complete_workflow_request(messages) and self._has_failed_preflight(messages):
                reason = self._stop_reason(messages, runtime)
                if reason is None:
                    return {"jump_to": "model"}
            return None

        if _has_completed_terminal_delivery(messages[:-1]):
            existing_content = last.content.strip() if isinstance(last.content, str) else ""
            stopped = clone_ai_message_with_tool_calls(
                last,
                [],
                content=existing_content or DELIVERY_COMPLETE_CONTENT,
            )
            return {"messages": [stopped]}

        reason = self._stop_reason(messages, runtime)
        if reason is None:
            return None

        terminal_calls = [tool_call for tool_call in tool_calls if tool_call.get("name") in TERMINAL_DELIVERY_TOOLS]
        if terminal_calls:
            delivery_contract_enabled = bool(self.config.required_completed_subagents) or self.config.require_evidence_checker
            if delivery_contract_enabled and not self._terminal_delivery_is_ready(runtime):
                stopped = clone_ai_message_with_tool_calls(
                    last,
                    [],
                    content="配置的专家流程或证据审计未完成；文件未向用户展示，本次请求以部分完成状态结束。",
                )
                return {"messages": [stopped]}
            if len(terminal_calls) == len(tool_calls):
                return None
            return {"messages": [clone_ai_message_with_tool_calls(last, terminal_calls)]}

        existing_content = last.content.strip() if isinstance(last.content, str) else ""
        stop_content = f"{self.config.stop_message}\n\n停止原因：{reason}。"
        if existing_content:
            stop_content = f"{existing_content}\n\n{stop_content}"

        stopped = clone_ai_message_with_tool_calls(last, [], content=stop_content)
        return {"messages": [stopped]}

    @hook_config(can_jump_to=["model"])
    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._apply(state, runtime)

    @override
    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._apply(state, runtime)

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        return handler(self._augment_request(request))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        updated_request = self._augment_request(request)
        timeout_seconds = self._remaining_model_call_seconds(request.runtime)
        if timeout_seconds is None:
            return await handler(updated_request)
        if timeout_seconds <= 0:
            return self._model_call_timeout_response(0.0)
        timeout_scope = asyncio.timeout(timeout_seconds)
        try:
            async with timeout_scope:
                return await handler(updated_request)
        except TimeoutError:
            if not timeout_scope.expired():
                raise
            return self._model_call_timeout_response(timeout_seconds)
