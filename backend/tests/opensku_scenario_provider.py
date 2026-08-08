"""Deterministic one-time recorder for OpenSKU product replay fixtures.

CI never uses this provider. ``scripts/build_opensku_replay_fixture.py`` drives
the real Gateway with it to produce a hash-keyed fixture; CI then replays that
fixture through ``ReplayChatModel``.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, SystemMessage, message_to_dict
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from replay_provider import _canonical_messages, hash_messages

LAUNCH_MARKER = "OPENSKU_REPLAY_LAUNCH_ULTRA"
GROWTH_MARKER = "OPENSKU_REPLAY_GROWTH_ANALYSIS"

PACK_FILES = [
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
]

_lock = threading.Lock()
_recorded_turns: list[dict[str, Any]] = []


def reset_recorded_turns() -> None:
    with _lock:
        _recorded_turns.clear()


def recorded_turns() -> list[dict[str, Any]]:
    with _lock:
        return list(_recorded_turns)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block if isinstance(block, str) else str(block.get("text", "")) for block in content if isinstance(block, str) or isinstance(block, dict))
    return str(content)


def _all_text(messages: list[BaseMessage]) -> str:
    return "\n".join(_content_text(message.content) for message in messages)


def _first_system_text(messages: list[BaseMessage]) -> str:
    for message in messages:
        if isinstance(message, SystemMessage):
            return _content_text(message.content).strip()
    return ""


def _tool_calls(messages: list[BaseMessage], name: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        calls.extend(call for call in message.tool_calls if call.get("name") == name)
    return calls


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def _task(subagent_type: str, description: str, prompt: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            _tool_call(
                "task",
                {
                    "description": description,
                    "prompt": f"{LAUNCH_MARKER}\n{prompt}",
                    "subagent_type": subagent_type,
                },
                f"call-task-{subagent_type}",
            )
        ],
    )


def _launch_pack_write_calls() -> list[dict[str, Any]]:
    files = {
        "launch-war-room.html": ('<!doctype html><html lang="zh-CN"><body><main><h1>OpenSKU Launch Replay</h1><p>当前无样品、无规格；本页仅汇总公开信号、假设和七天验证动作。</p></main></body></html>'),
        "evidence-ledger.json": "{broken",
        "competitor-table.csv": "name,evidence_label,source_url\n公开类目页,observed_public,https://example.com/category\n",
        "positioning-brief.md": (
            "# 定位验证简报\n\n假设为通勤用户需要更清晰的饮水与携带决策信息。"
            "先验证真实场景、预算和现有替代方案，再决定是否进入样品阶段。"
            "所有结论都保留来源、限制与停止条件。七天内只记录可追溯的反馈数量、"
            "来源日期和停止原因，不把概念偏好写成产品事实。"
        ),
        "listing-pack.md": ("# 随行杯概念调研页\n\n当前无样品、无规格。请告诉我们：选择这一品类时，你会先看真实使用场景、预算、购买时机还是现有替代方案？本页不售卖、不收款，不承诺产品能力或交付时间。"),
        "content-pack.md": ("# 问题型内容包\n\n当前无样品、无规格。请只回答品类问题：你在通勤或办公场景中最希望先解决什么？哪些信息缺失时你不会继续了解？内容仅用于需求调研，不接受付款或预订。"),
        "launch-calendar.csv": "day,action\n",
    }
    return [
        _tool_call(
            "write_file",
            {
                "description": f"Write {name}",
                "path": f"/mnt/user-data/outputs/{name}",
                "content": content,
            },
            f"call-write-{index}",
        )
        for index, (name, content) in enumerate(files.items(), start=1)
    ]


def _launch_response(messages: list[BaseMessage]) -> AIMessage:
    task_types = [call.get("args", {}).get("subagent_type") for call in _tool_calls(messages, "task")]
    if "market-voc-researcher" not in task_types:
        return _task(
            "market-voc-researcher",
            "Research launch signals",
            "Return bounded public-signal findings for a no-sample commuter tumbler concept. Use no tools in this replay.",
        )
    if "offer-architect" not in task_types:
        return _task(
            "offer-architect",
            "Design validation offer",
            "Use the supplied replay research to define the audience wedge, assumptions, and cheapest validation experiments.",
        )
    if "asset-studio" not in task_types:
        return _task(
            "asset-studio",
            "Draft safe concept assets",
            "Create no-sample, question-led listing and content concepts without product claims.",
        )
    if not _tool_calls(messages, "write_file"):
        return AIMessage(content="", tool_calls=_launch_pack_write_calls())
    present_count = len(_tool_calls(messages, "present_files"))
    if present_count == 0:
        return AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "present_files",
                    {"filepaths": [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]},
                    "call-present-1",
                )
            ],
        )
    if present_count == 1 and not _tool_calls(messages, "str_replace"):
        return AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "str_replace",
                    {
                        "description": "Repair invalid evidence JSON from preflight observation",
                        "path": "/mnt/user-data/outputs/evidence-ledger.json",
                        "old_str": "{broken",
                        "new_str": '{"meta":{"status":"no sample"},"entries":[{"id":"E1","claim":"Public category page exists","label":"observed_public","source_urls":["https://example.com/category"]}]}',
                    },
                    "call-repair-ledger",
                ),
                _tool_call(
                    "str_replace",
                    {
                        "description": "Add the missing validation action row named by preflight",
                        "path": "/mnt/user-data/outputs/launch-calendar.csv",
                        "old_str": "day,action\n",
                        "new_str": "day,action\n1,Collect traceable user problems\n",
                    },
                    "call-repair-calendar",
                ),
            ],
        )
    if present_count == 1:
        return AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "present_files",
                    {"filepaths": [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]},
                    "call-present-2",
                )
            ],
        )
    return AIMessage(
        content=(
            "Launch Ultra replay complete: three specialists finished in dependency order, "
            "the first deterministic preflight returned two observations, only "
            "evidence-ledger.json and launch-calendar.csv were revised, and the second "
            "present_files call delivered all 7/7 artifacts. 未经过独立 Evidence Checker 审计。"
        )
    )


def _growth_response(messages: list[BaseMessage]) -> AIMessage:
    if not _tool_calls(messages, "inspect_data"):
        return AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "inspect_data",
                    {"filenames": ["customers.csv", "assignments.csv", "outcomes.csv"]},
                    "call-growth-inspect",
                )
            ],
        )
    if not _tool_calls(messages, "query_data"):
        return AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "query_data",
                    {
                        "filenames": ["customers.csv", "assignments.csv", "outcomes.csv"],
                        "sql": (
                            "SELECT a.variant, COUNT(DISTINCT a.user_id) AS visitors, "
                            "SUM(o.converted) AS conversions FROM assignments AS a "
                            "JOIN outcomes AS o USING (user_id) JOIN customers AS c USING (user_id) "
                            "WHERE c.segment = 'new' GROUP BY a.variant ORDER BY a.variant"
                        ),
                    },
                    "call-growth-query",
                )
            ],
        )
    if not _tool_calls(messages, "analyze_ab_test"):
        return AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "analyze_ab_test",
                    {
                        "control_visitors": 100,
                        "control_conversions": 10,
                        "variant_visitors": 100,
                        "variant_conversions": 20,
                    },
                    "call-growth-ab",
                )
            ],
        )
    return AIMessage(
        content=(
            "SHIP WITH MONITORING. The three-file join returns 100 control visitors with "
            "10 conversions and 100 variant visitors with 20 conversions. The deterministic "
            "A/B tool reports p = 0.0477, a +10.00 pp absolute lift, and a 95% CI of "
            "+0.20 to +19.80 pp; SRM is not detected. Keep monitoring guardrails before a full rollout."
        )
    )


def _respond(messages: list[BaseMessage]) -> AIMessage:
    first_system = _first_system_text(messages)
    if first_system.startswith("You are the Market & VOC Researcher"):
        return AIMessage(
            content=(
                "observed_public: a public category page exists at https://example.com/category. assumption: commuter buyers may prioritize cleaning and carry scenarios. No sales, review, specification, or performance claims are available."
            )
        )
    if first_system.startswith("You are the Offer Architect"):
        return AIMessage(
            content=(
                "Audience wedge: commuters comparing reusable drinkware. Verdict: test_now. "
                "Validate problem priority, acceptable budget, and information gaps with a non-transactional concept test; stop if qualified problem signals remain weak."
            )
        )
    if first_system.startswith("You are the Asset Studio"):
        return AIMessage(
            content=(
                "NO-SAMPLE MODE assets: ask which commute problem matters most, which "
                "existing alternative is unsatisfactory, and what budget or information "
                "is required. Do not describe product features, tests, testimonials, "
                "availability, or delivery."
            )
        )

    text = _all_text(messages)
    if LAUNCH_MARKER in text:
        return _launch_response(messages)
    if GROWTH_MARKER in text:
        return _growth_response(messages)
    return AIMessage(content="[]")


class OpenSKUScenarioModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "opensku-scenario-recorder"

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        output = _respond(messages)
        turn = {
            "input_hash": hash_messages(messages),
            "input_preview": _canonical_messages(messages),
            "output": message_to_dict(output),
        }
        with _lock:
            _recorded_turns.append(turn)
        return output

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        output = self._next(messages)
        chunk = AIMessageChunk(
            content=output.content,
            tool_calls=output.tool_calls,
            additional_kwargs=output.additional_kwargs,
            id=output.id,
        )
        yield ChatGenerationChunk(message=chunk)

    def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable:  # type: ignore[override]
        return self


__all__ = [
    "GROWTH_MARKER",
    "LAUNCH_MARKER",
    "OpenSKUScenarioModel",
    "recorded_turns",
    "reset_recorded_turns",
]
