"""Run Store Operator end to end against a live gateway and real DeepSeek V4.

The script registers a throwaway local user, creates one real thread, uploads
public CSV files, drains real SSE runs, and evaluates the persisted message
trace. It has no replay, mock, cache, retry, or model fallback path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

EXPECTED_MODEL = "deepseek-v4-flash"
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
NUMBER_RE = re.compile(r"\d")

CASES = (
    {
        "id": "simple-direct",
        "prompt": "请先检查我刚上传的这批数据，直接告诉我每个文件有多少行、覆盖什么时间。这个问题很简单，不需要分派子智能体。",
        "expected_profile": None,
    },
    {
        "id": "analyst-comparison",
        "prompt": "请比较数据里最近14天和此前14天的去重订单数，并找出变化最大的订单状态。这个计算目标比较明确，你可以让 analyst 独立计算后再用中文回答。",
        "expected_profile": "analyst",
    },
    {
        "id": "explore-multitable",
        "prompt": "我不确定这几张表怎样关联。请从经营分析角度检查多表粒度、关联键和目前最值得分析的三个问题；范围较广，可以让 explore 先做数据探索。",
        "expected_profile": "explore",
    },
    {
        "id": "verifier-high-impact",
        "prompt": "最近14天与此前14天的去重订单数会影响经营动作，请让 verifier 独立复算，检查日期边界和重复计数，然后给出核验结论。",
        "expected_profile": "verifier",
    },
    {
        "id": "missing-metric",
        "prompt": "只根据当前上传数据，能不能判断广告ROI为什么下降？请直接说明能确认什么、缺什么，不要编造广告消耗、曝光或利润。",
        "expected_profile": None,
    },
)


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _tool_calls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in messages:
        raw_calls = message.get("tool_calls")
        if isinstance(raw_calls, list):
            calls.extend(call for call in raw_calls if isinstance(call, dict))
    return calls


def _task_outcomes(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    profile_by_call_id: dict[str, str] = {}
    for call in _tool_calls(messages):
        if call.get("name") != "task" or not isinstance(call.get("id"), str):
            continue
        args = call.get("args")
        if isinstance(args, dict) and isinstance(args.get("subagent_type"), str):
            profile_by_call_id[call["id"]] = args["subagent_type"]

    outcomes: list[dict[str, str]] = []
    for message in messages:
        if message.get("type") != "tool":
            continue
        call_id = message.get("tool_call_id")
        if not isinstance(call_id, str) or call_id not in profile_by_call_id:
            continue
        additional = message.get("additional_kwargs")
        raw_status = (
            additional.get("subagent_status")
            if isinstance(additional, dict)
            else None
        )
        content = _message_text(message)
        if raw_status in {"completed", "failed"}:
            status = raw_status
        elif "Task Succeeded" in content:
            status = "completed"
        elif "Task Failed" in content:
            status = "failed"
        else:
            status = "unknown"
        outcomes.append(
            {
                "call_id": call_id,
                "profile": profile_by_call_id[call_id],
                "status": status,
            }
        )
    return outcomes


def _final_answer(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("type") not in {"ai", "assistant"}:
            continue
        if message.get("tool_calls"):
            continue
        text = _message_text(message).strip()
        if text:
            return text
    return ""


def _provider_evidence(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for message in messages:
        if message.get("type") not in {"ai", "assistant"}:
            continue
        metadata = message.get("response_metadata")
        if not isinstance(metadata, dict):
            continue
        identity = metadata.get("actual_model_identity")
        request_id = metadata.get("provider_request_id")
        retry_count = metadata.get("retry_count")
        if identity or request_id or retry_count is not None:
            evidence.append(
                {
                    "actual_model_identity": identity,
                    "provider_request_id": request_id,
                    "provider_request_id_source": metadata.get(
                        "provider_request_id_source"
                    ),
                    "retry_count": retry_count,
                }
            )
    return evidence


def _thread_messages(client: httpx.Client, thread_id: str) -> list[dict[str, Any]]:
    response = client.get(f"/api/threads/{thread_id}/state")
    response.raise_for_status()
    payload = response.json()
    values = payload.get("values") if isinstance(payload, dict) else None
    messages = values.get("messages") if isinstance(values, dict) else None
    return [message for message in messages or [] if isinstance(message, dict)]


def _drain_run(
    client: httpx.Client,
    *,
    thread_id: str,
    csrf: str,
    prompt: str,
    files_metadata: list[dict[str, Any]] | None = None,
) -> None:
    human_message: dict[str, Any] = {
        "type": "human",
        "content": [{"type": "text", "text": prompt}],
    }
    if files_metadata:
        human_message["additional_kwargs"] = {"files": files_metadata}
    body = {
        "assistant_id": "lead_agent",
        "input": {"messages": [human_message]},
        "config": {"recursion_limit": 1000},
        "context": {
            "agent_name": "store-operator",
            "model_name": "deepseek-reasoner",
            "mode": "ultra",
            "thinking_enabled": True,
            "is_plan_mode": True,
            "subagent_enabled": True,
            "reasoning_effort": "high",
            "thread_id": thread_id,
        },
        "stream_mode": ["values", "messages", "custom"],
        "stream_subgraphs": True,
    }
    event_count = 0
    with client.stream(
        "POST",
        f"/api/threads/{thread_id}/runs/stream",
        json=body,
        headers={"X-CSRF-Token": csrf},
        timeout=900.0,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("event:"):
                event_count += 1
    if event_count == 0:
        raise RuntimeError("实时运行没有返回任何 SSE event")


def _evaluate_case(
    case: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    calls = _tool_calls(messages)
    tool_names = [str(call.get("name") or "") for call in calls]
    task_outcomes = _task_outcomes(messages)
    task_profiles = [
        str(args.get("subagent_type"))
        for call in calls
        if call.get("name") == "task"
        and isinstance((args := call.get("args")), dict)
        and args.get("subagent_type")
    ]
    answer = _final_answer(messages)
    failures: list[str] = []
    expected_profile = case["expected_profile"]
    if expected_profile is None and "task" in tool_names:
        failures.append("简单问题不应强制调用 Subagent")
    if expected_profile and expected_profile not in task_profiles:
        failures.append(f"没有调用预期 Subagent：{expected_profile}")
    if expected_profile and not any(
        outcome["profile"] == expected_profile
        and outcome["status"] == "completed"
        for outcome in task_outcomes
    ):
        failures.append(f"预期 Subagent 未成功完成：{expected_profile}")
    if case["id"] == "simple-direct" and "store_inspect_data" not in tool_names:
        failures.append("首次简单分析没有调用 store_inspect_data")
    if case["id"] in {"analyst-comparison", "verifier-high-impact"} and not NUMBER_RE.search(answer):
        failures.append("窗口比较回答没有数字")
    if case["id"] == "missing-metric":
        limitation_terms = ("缺少", "没有", "无法", "不能", "不足")
        if not any(term in answer for term in limitation_terms):
            failures.append("缺失广告字段时没有明确说明数据限制")
    if not answer:
        failures.append("没有最终回答")
    elif not CHINESE_RE.search(answer):
        failures.append("最终回答不是中文")
    return {
        "case_id": case["id"],
        "passed": not failures,
        "failures": failures,
        "tool_names": tool_names,
        "task_profiles": task_profiles,
        "task_outcomes": task_outcomes,
        "final_answer": answer,
        "final_answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
    }


def run_gate(
    base_url: str,
    dataset_dir: Path,
    audit_dir: Path,
    *,
    cases: tuple[dict[str, Any], ...] = CASES,
) -> tuple[dict[str, Any], Path]:
    dataset_files = [
        dataset_dir / name
        for name in ("orders.csv", "order_items.csv", "products.csv", "sellers.csv")
    ]
    missing = [str(path) for path in dataset_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"公开数据文件不存在：{missing}")

    with httpx.Client(base_url=base_url.rstrip("/"), timeout=120.0) as client:
        email = f"store-live-{uuid.uuid4().hex[:12]}@example.com"
        register = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "store-live-gate-password-2026"},
        )
        register.raise_for_status()
        csrf = client.cookies.get("csrf_token")
        if not csrf:
            raise RuntimeError("注册后没有取得 CSRF cookie")

        thread_id = str(uuid.uuid4())
        created = client.post(
            "/api/threads",
            json={"thread_id": thread_id, "metadata": {"agent_name": "store-operator"}},
            headers={"X-CSRF-Token": csrf},
        )
        created.raise_for_status()

        handles = [path.open("rb") for path in dataset_files]
        try:
            upload = client.post(
                f"/api/threads/{thread_id}/uploads",
                files=[
                    ("files", (path.name, handle, "text/csv"))
                    for path, handle in zip(dataset_files, handles, strict=True)
                ],
                headers={"X-CSRF-Token": csrf},
            )
        finally:
            for handle in handles:
                handle.close()
        upload.raise_for_status()
        uploaded = upload.json().get("files") or []
        files_metadata = [
            {
                "filename": item["filename"],
                "size": item["size"],
                "path": item["virtual_path"],
                "status": "uploaded",
            }
            for item in uploaded
        ]

        case_results: list[dict[str, Any]] = []
        all_new_messages: list[dict[str, Any]] = []
        before = len(_thread_messages(client, thread_id))
        for index, case in enumerate(cases):
            _drain_run(
                client,
                thread_id=thread_id,
                csrf=csrf,
                prompt=case["prompt"],
                files_metadata=files_metadata if index == 0 else None,
            )
            current = _thread_messages(client, thread_id)
            new_messages = current[before:]
            before = len(current)
            all_new_messages.extend(new_messages)
            case_results.append(_evaluate_case(case, new_messages))

    provider_evidence = _provider_evidence(all_new_messages)
    provider_ids = [
        item["provider_request_id"]
        for item in provider_evidence
        if isinstance(item.get("provider_request_id"), str)
    ]
    provider_failures: list[str] = []
    if not provider_evidence:
        provider_failures.append("Agent trace 没有 provider telemetry")
    if any(item.get("actual_model_identity") != EXPECTED_MODEL for item in provider_evidence):
        provider_failures.append("存在非 deepseek-v4-flash 的模型响应")
    if any(item.get("retry_count") != 0 for item in provider_evidence):
        provider_failures.append("存在 retry_count 不为 0 的模型响应")
    if len(provider_ids) != len(provider_evidence):
        provider_failures.append("存在缺少 provider_request_id 的模型响应")
    if len(provider_ids) != len(set(provider_ids)):
        provider_failures.append("provider_request_id 不唯一，无法证明全部响应为 fresh")

    result = {
        "schema_version": "1.0",
        "run_id": f"store-live-{uuid.uuid4().hex}",
        "checked_at": datetime.now(UTC).isoformat(),
        "status": (
            "passed"
            if not provider_failures and all(case["passed"] for case in case_results)
            else "failed"
        ),
        "transport": "real_http_sse",
        "model_alias": "deepseek-reasoner",
        "expected_model": EXPECTED_MODEL,
        "configured_max_retries": 0,
        "mock": False,
        "replay": False,
        "application_cache": False,
        "provider_prompt_cache_is_not_acceptance_evidence": True,
        "fallback": False,
        "thread_id": thread_id,
        "dataset": [
            {
                "filename": path.name,
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in dataset_files
        ],
        "cases": case_results,
        "provider_evidence": provider_evidence,
        "provider_failures": provider_failures,
    }
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"{result['run_id']}.json"
    audit_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result, audit_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Store Operator live gate")
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument(
        "--case-id",
        action="append",
        choices=[case["id"] for case in CASES],
        help="只运行指定用例；可重复传入。省略时运行全部用例。",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path("../.deer-flow/store-operator/evaluation/live-gate"),
    )
    args = parser.parse_args()
    selected_ids = set(args.case_id or [])
    selected_cases = tuple(
        case for case in CASES if not selected_ids or case["id"] in selected_ids
    )
    result, path = run_gate(
        args.base_url,
        args.dataset_dir,
        args.audit_dir,
        cases=selected_cases,
    )
    summary = {
        "status": result["status"],
        "case_status": {
            item["case_id"]: item["passed"] for item in result["cases"]
        },
        "provider_response_count": len(result["provider_evidence"]),
        "provider_failures": result["provider_failures"],
        "audit_path": str(path.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
