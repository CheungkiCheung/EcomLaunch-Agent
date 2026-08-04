"""Live E2E driver: real backend + real LLM, with metric capture.

Usage:
    uv run python e2e_live/driver.py --list
    uv run python e2e_live/driver.py --run b1
    uv run python e2e_live/driver.py --run all
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field

import requests

GATEWAY = os.environ.get("E2E_GATEWAY", "http://localhost:8001")
TOKEN = os.environ.get("DEER_FLOW_INTERNAL_AUTH_TOKEN", "test-token-openskufast-2026")
EMAIL = os.environ.get("E2E_EMAIL", "e2e-test3@test.com")
PASSWORD = os.environ.get("E2E_PASSWORD", "Test1234!")
HEADERS = {"X-DeerFlow-Internal-Token": TOKEN, "Content-Type": "application/json"}

SSE_EVENT_RE = re.compile(r"^event: (\S+)\s*$")
SSE_DATA_RE = re.compile(r"^data: (.*)$", re.DOTALL)


@dataclass
class RunResult:
    thread_id: str
    run_id: str
    status: str = ""
    elapsed_s: float = 0.0
    final_text: str = ""
    artifacts: list[str] = field(default_factory=list)
    total_tokens: int = 0
    llm_call_count: int = 0
    events: list[dict] = field(default_factory=list)

    def metrics(self) -> dict:
        return {
            "elapsed_s": round(self.elapsed_s, 2),
            "total_tokens": self.total_tokens,
            "llm_call_count": self.llm_call_count,
            "artifacts": len(self.artifacts),
            "status": self.status,
        }


class LiveClient:
    def __init__(self, agent: str | None = None, agent_name: str | None = None):
        # Gateway routes custom agents via assistant_id != "lead_agent".
        # Pass the agent name as assistant_id so make_lead_agent loads the
        # per-agent config (memory_enabled, run_budget, flash_skills...).
        self.agent = agent or agent_name or "lead_agent"
        self.agent_name = self.agent if self.agent != "lead_agent" else agent_name
        self._client = requests.Session()
        self._csrf_token: str | None = None
        self._login()

    def _login(self) -> None:
        r = self._client.post(
            f"{GATEWAY}/api/v1/auth/login/local",
            data={"username": EMAIL, "password": PASSWORD},
            timeout=30,
        )
        r.raise_for_status()
        self._csrf_token = self._client.cookies.get("csrf_token")
        self._state_headers = {"Content-Type": "application/json"}
        if self._csrf_token:
            self._state_headers["X-CSRF-Token"] = self._csrf_token

    def create_thread(self) -> str:
        r = self._client.post(
            f"{GATEWAY}/api/threads",
            headers=self._state_headers,
            json={"metadata": {"agent_name": self.agent_name} if self.agent_name else {}},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["thread_id"]

    def upload(self, thread_id: str, files: list[tuple[str, bytes, str]]) -> None:
        parts = []
        for name, content, mime in files:
            parts.append(("files", (name, content, mime)))
        upload_headers = {}
        if self._csrf_token:
            upload_headers["X-CSRF-Token"] = self._csrf_token
        r = self._client.post(
            f"{GATEWAY}/api/threads/{thread_id}/uploads",
            headers=upload_headers,
            files=parts,
            timeout=60,
        )
        r.raise_for_status()

    def run(
        self,
        thread_id: str,
        text: str,
        *,
        config: dict | None = None,
        timeout: float = 600,
        followup: bool = False,
    ) -> RunResult:
        body: dict = {
            "assistant_id": self.agent,
            "metadata": {"agent_name": self.agent_name} if self.agent_name else {},
            "input": {"messages": [{"role": "user", "content": text}]},
        }
        if config:
            # Mirrors frontend buildThreadRunContext: Ultra enables subagents,
            # plan mode and high reasoning effort.
            context = dict(config.get("context", {}))
            if "subagent_enabled" not in context:
                context["subagent_enabled"] = True
            if "is_plan_mode" not in context:
                context["is_plan_mode"] = True
            if "reasoning_effort" not in context:
                context["reasoning_effort"] = "high"
            mode = (config.get("configurable") or {}).get("mode")
            if mode:
                context["mode"] = mode
            body["context"] = context
            if "configurable" in config:
                body["config"] = {"configurable": config["configurable"]}
        started = time.monotonic()
        with self._client.post(
            f"{GATEWAY}/api/threads/{thread_id}/runs/stream",
            headers=self._state_headers,
            json=body,
            stream=True,
            timeout=(30, timeout),
        ) as resp:
            resp.raise_for_status()
            result = RunResult(thread_id=thread_id, run_id="")
            current_event = ""
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.strip():
                    continue
                m = SSE_EVENT_RE.match(line)
                if m:
                    current_event = m.group(1)
                    continue
                m = SSE_DATA_RE.match(line)
                if not m:
                    continue
                try:
                    data = json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
                result.events.append({"event": current_event, "data": data})
                self._consume(result, current_event, data)
            result.elapsed_s = time.monotonic() - started
        # Post-run metric fetch: the run record carries token/call stats.
        if result.run_id:
            try:
                rr = self._client.get(
                    f"{GATEWAY}/api/threads/{thread_id}/runs/{result.run_id}",
                    timeout=30,
                )
                if rr.status_code == 200:
                    rec = rr.json()
                    result.total_tokens = rec.get("total_tokens", 0)
                    result.llm_call_count = rec.get("llm_call_count", 0)
            except Exception:
                pass
        return result

    def _consume(self, result: RunResult, event: str, data: dict) -> None:
        if event == "metadata":
            result.run_id = data.get("run_id", result.run_id)
        elif event == "values":
            self._absorb_values(result, data)
        elif event == "end":
            result.status = "end"
            if isinstance(data, dict):
                record = data.get("run", {})
                result.total_tokens = record.get("total_tokens", 0)
                result.llm_call_count = record.get("llm_call_count", 0)
        elif event == "error":
            result.status = f"error: {str(data)[:200]}"

    def _absorb_values(self, result: RunResult, data: dict) -> None:
        if isinstance(data, dict):
            artifacts = data.get("artifacts")
            if isinstance(artifacts, list):
                result.artifacts = artifacts
            messages = data.get("messages")
            if isinstance(messages, list) and messages:
                last = messages[-1]
                content = last.get("content")
                if isinstance(content, str):
                    result.final_text = content
                elif isinstance(content, list):
                    texts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    result.final_text = "".join(texts)


def _mk_sales_csv() -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["月份", "GMV", "订单数", "浏览量", "支付成功订单数", "转化率", "30天留存率", "新客数", "复购率"])
    rows = [
        ("2026-01", 1200000, 3600, 100000, 3200, 0.032, 0.38, 2100, 0.22),
        ("2026-02", 1350000, 4100, 120000, 4100, 0.034, 0.39, 2300, 0.23),
        ("2026-03", 1520000, 4700, 130000, 4700, 0.036, 0.41, 2600, 0.25),
        ("2026-04", 1410000, 4300, 140000, 4300, 0.031, 0.37, 2400, 0.24),
        ("2026-05", 1680000, 5200, 160000, 6200, 0.039, 0.42, 2900, 0.27),
        ("2026-06", 1750000, 5500, 150000, 7000, 0.041, 0.43, 3100, 0.28),
    ]
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


SCENARIOS: dict[str, dict] = {
    "b1": {
        "name": "B1: Growth Analyst 上传+分析",
        "agent_name": "data-inspector",
        "upload": [("sales.csv", _mk_sales_csv, "text/csv")],
        "question": "分析一下这份经营数据，重点看 GMV、转化率和留存的变化趋势",
        "asserts": ["GMV", "转化率", "留存", "%"],
    },
    "b2": {
        "name": "B2: 跨会话记忆（新会话问趋势）",
        "agent_name": "data-inspector",
        "new_thread": True,
        "question": "跟上次分析比，转化率和留存最近怎么样？有没有持续下降的指标？",
        "asserts": [],
    },
    "e1": {
        "name": "E1: 追问承接（EcomLaunch Flash 多轮）",
        "agent_name": "ecom-launch",
        "config": {"configurable": {"mode": "flash"}},
        "followups": [
            "不要提问，直接输出：帮我定 3 个便携咖啡杯的差异化定位（便携通勤/高效办公/极简环保各一个，每点 2-3 句）",
            "第 2 个（高效办公）再具体一点，补充目标人群和场景，2-3 句",
            "现在为这 3 个定位排优先级：预算只有 5 万，哪个先做，为什么。直接输出",
        ],
        "asserts": [],
    },
    "e3": {
        "name": "E3: 纠错/反悔（Growth Analyst 口径修正）",
        "agent_name": "data-inspector",
        "upload": [("sales.csv", _mk_sales_csv, "text/csv")],
        "followups": [
            "4 月的转化率是多少",
            "不对，转化率应该按支付成功口径算，重新算一下",
            "那 6 月按这个口径又是多少",
        ],
        "asserts": [],
    },
    "e2": {
        "name": "E2: 多轮收敛（EcomLaunch Ultra 增量更新）",
        "agent_name": "ecom-launch",
        "config": {"configurable": {"mode": "ultra"}},
        "followups": [
            "不要提问，直接执行：我有一个便携咖啡杯，帮我做完整的 Launch Validation Pack（无样品无规格）",
            "现在把定位从便携通勤改成高端办公人群，重新生成定位相关文件",
        ],
        "asserts": ["artifacts"],
        "timeout": 900,
    },
    "a2": {
        "name": "A2: Ultra 7/7 完整交付",
        "agent_name": "ecom-launch",
        "config": {"configurable": {"mode": "ultra"}},
        "question": "不要提问，直接执行：我有一个太阳能充电宝，无样品无规格，帮我做完整的 Launch Validation Pack",
        "asserts": ["artifacts"],
        "timeout": 900,
    },
    "a3": {
        "name": "A3: 修订闭环（故意失败注入）",
        "agent_name": "ecom-launch",
        "config": {"configurable": {"mode": "ultra"}},
        "question": "不要提问，直接执行：我有一个便携咖啡杯，无样品无规格，帮我做完整的 Launch Validation Pack，并故意把一个文件的证据标签写错测试系统",
        "asserts": ["artifacts"],
        "timeout": 900,
    },
    "b3": {
        "name": "B3: A/B 实验结论",
        "agent_name": "data-inspector",
        "upload": [("sales.csv", _mk_sales_csv, "text/csv")],
        "question": "不要提问，直接分析：这份数据里 5 月和 6 月像不像一次 A/B 实验的对照组和实验组（转化率从 3.9% 到 4.1%）？该不该把这个‘实验’的改动推上线？给出结论",
        "asserts": [],
    },
}


def _run_scenario(name: str, spec: dict) -> RunResult:
    print(f"\n=== {spec['name']} ===")
    client = LiveClient(agent_name=spec["agent_name"])
    thread_id = client.create_thread()
    if spec.get("upload"):
        files = [(n, f(), m) for n, f, m in spec["upload"]]
        client.upload(thread_id, files)
        print(f"  uploaded {len(files)} file(s)")

    config = spec.get("config")
    followups: list[str] = spec.get("followups", []) or [spec["question"]]
    result: RunResult | None = None
    for i, question in enumerate(followups):
        label = f"  Q{i+1}: {question[:50]}..."
        print(label, flush=True)
        if spec.get("new_thread") and i > 0:
            thread_id = client.create_thread()
            print("  (new thread for cross-session check)", flush=True)
        result = client.run(thread_id, question, config=config)
        preview = result.final_text[:220].replace("\n", " ")
        print(f"  -> [{result.status}] {result.elapsed_s:.1f}s tokens={result.total_tokens} calls={result.llm_call_count}", flush=True)
        print(f"     {preview}", flush=True)
        if result.artifacts:
            print(f"     artifacts: {result.artifacts}", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--run", default="all")
    args = parser.parse_args()

    if args.list:
        for name, spec in SCENARIOS.items():
            print(f"{name}: {spec['name']}")
        return

    targets = [args.run] if args.run != "all" else list(SCENARIOS)
    summary = {}
    for name in targets:
        spec = SCENARIOS[name]
        try:
            result = _run_scenario(name, spec)
            summary[name] = result.metrics()
        except Exception as e:  # noqa: BLE001
            print(f"  !! FAILED: {e}")
            summary[name] = {"error": str(e)[:200]}

    print("\n\n===== METRICS SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
