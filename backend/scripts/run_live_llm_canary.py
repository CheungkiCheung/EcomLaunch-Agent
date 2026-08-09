"""Run a bounded OpenSKU live-model canary through the real Gateway.

The canary is intentionally separate from deterministic Replay E2E. It runs
only when a dedicated API key is available, never on pull requests by default,
and writes sanitized state, run events, metrics, and artifacts for diagnosis.
Without a key it exits successfully with an explicit ``skipped`` summary.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND.parent
sys.path.insert(0, str(_BACKEND))

PACK_FILES = {
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
}
CANARY_TOOLS = {"task", "read_file", "render_launch_pack", "write_file", "str_replace", "present_files"}

FLASH_PROMPT = """OpenSKU live canary. For a concept-stage reusable desk cable
organizer, which should be tested first: the demand hypothesis or the price
hypothesis? Do not call any tool. End your response with this line exactly:
OPENSKU_CANARY_OK
"""

ULTRA_PROMPT = """Run the complete OpenSKU Launch Validation Pack workflow for this
offline canary. Do not browse, fetch URLs, or use image generation. Use only the
brief below, delegate to the three configured specialists in dependency order,
then create and present all seven required files under /mnt/user-data/outputs.

Brief: a concept-stage reusable desk cable organizer for the US market, target
price USD 19, office workers as the hypothesis audience. There is no sample,
no specification sheet, no test data, and no public research in this run.

Evidence rules: mark external facts unavailable or estimated; do not use
observed_public or uploaded_real labels. Keep source URLs empty for estimated
entries. Consumer copy must stay in no-sample question/hypothesis language and
must not claim materials, dimensions, performance, guarantees, testimonials, or
first-person use. JSON must parse. Every CSV must have a header and at least one
non-empty data row. If deterministic preflight reports an issue, make only the
minimum named repair and present the full pack again.
"""


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _credentials() -> tuple[str, str, str]:
    api_key = os.environ.get("OPENSKU_CANARY_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENSKU_CANARY_BASE_URL") or os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model = os.environ.get("OPENSKU_CANARY_MODEL", "gpt-4.1-mini")
    return api_key.strip(), base_url.strip(), model.strip()


def _build_live_config(*, home: Path, api_key: str, base_url: str, model: str) -> str:
    import yaml

    source = yaml.safe_load((_REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("config.yaml must contain a mapping")

    source["log_level"] = "warning"
    source["models"] = [
        {
            "name": "opensku-live-canary",
            "display_name": "OpenSKU Live Canary",
            "use": "langchain_openai:ChatOpenAI",
            "model": model,
            "api_key": "$OPENAI_API_KEY",
            "base_url": "$OPENAI_API_BASE",
            "temperature": 0,
            "max_tokens": int(os.environ.get("OPENSKU_CANARY_MAX_OUTPUT_TOKENS", "12000")),
            "max_retries": 1,
            "stream_chunk_timeout": 120,
            "supports_thinking": False,
            "supports_reasoning_effort": False,
            "supports_vision": False,
        }
    ]
    source["tools"] = [tool for tool in source.get("tools", []) if isinstance(tool, dict) and tool.get("name") in CANARY_TOOLS]
    source.setdefault("skills", {})["path"] = str(_REPO_ROOT / "skills")
    source["skills"]["container_path"] = "/mnt/skills"
    source.setdefault("sandbox", {})["use"] = "deerflow.sandbox.local:LocalSandboxProvider"
    source["sandbox"]["allow_host_bash"] = False
    source["database"] = {
        "backend": "sqlite",
        "sqlite_dir": str(home / "db"),
    }
    source["run_events"] = {
        "backend": "memory",
        "max_trace_content": 20000,
        "track_token_usage": True,
    }
    source["memory"] = {"enabled": False, "injection_enabled": False}
    source["summarization"] = {"enabled": False}
    source["title"] = {"enabled": False}
    source.setdefault("agents_api", {})["enabled"] = True

    for specialist in source.get("subagents", {}).get("custom_agents", {}).values():
        if isinstance(specialist, dict):
            specialist["tools"] = []
            specialist["model"] = "opensku-live-canary"

    return yaml.safe_dump(source, allow_unicode=True, sort_keys=False)


def _prepare_runtime(
    home: Path,
    config_path: Path,
    *,
    api_key: str,
    base_url: str,
) -> None:
    import yaml

    extensions = home / "extensions_config.json"
    extensions.write_text(
        json.dumps({"mcpServers": {}, "skills": {}}),
        encoding="utf-8",
    )
    project_root = home / "project"
    shutil.copytree(_REPO_ROOT / "agents", project_root / "agents")
    for agent_name in ("ecom-launch", "openskufast"):
        agent_config_path = project_root / "agents" / agent_name / "config.yaml"
        agent_config = yaml.safe_load(agent_config_path.read_text(encoding="utf-8"))
        budget = agent_config["run_budget"]
        budget["max_lead_model_calls"] = int(os.environ.get("OPENSKU_CANARY_MAX_MODEL_CALLS", "15"))
        budget["max_total_tokens"] = int(os.environ.get("OPENSKU_CANARY_MAX_TOTAL_TOKENS", "120000"))
        budget["max_execution_seconds"] = int(os.environ.get("OPENSKU_CANARY_MAX_EXECUTION_SECONDS", "360"))
        agent_config_path.write_text(
            yaml.safe_dump(agent_config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    os.environ["OPENSKU_HOME"] = str(home)
    os.environ["OPENSKU_CONFIG_PATH"] = str(config_path)
    os.environ["OPENSKU_PROJECT_ROOT"] = str(project_root)
    os.environ["OPENSKU_EXTENSIONS_CONFIG_PATH"] = str(extensions)
    os.environ["AUTH_JWT_SECRET"] = "opensku-live-canary-local-secret-32-bytes"
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_API_BASE"] = base_url


def _register(client: Any) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"opensku-canary-{uuid.uuid4().hex[:12]}@example.com",
            "password": "canary-local-password-123",
        },
    )
    if response.status_code != 201:
        raise AssertionError(f"registration failed: {response.status_code} {response.text}")
    csrf = client.cookies.get("csrf_token")
    if not csrf:
        raise AssertionError("registration did not set csrf_token")
    return csrf


def _create_thread(client: Any, csrf: str) -> str:
    thread_id = f"opensku-live-canary-{uuid.uuid4().hex[:12]}"
    response = client.post(
        "/api/threads",
        json={"thread_id": thread_id, "metadata": {"agent_name": "ecom-launch"}},
        headers={"X-CSRF-Token": csrf},
    )
    if response.status_code != 200:
        raise AssertionError(f"thread creation failed: {response.status_code} {response.text}")
    return thread_id


def _tool_calls(state: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in state.get("messages", []):
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict):
                calls.append(call)
    return calls


def _tool_results(state: dict[str, Any]) -> dict[str, list[str]]:
    call_names = {str(call.get("id")): str(call.get("name")) for call in _tool_calls(state) if call.get("id") and call.get("name")}
    results: dict[str, list[str]] = {}
    for message in state.get("messages", []):
        if not isinstance(message, dict) or message.get("type") != "tool":
            continue
        name = call_names.get(str(message.get("tool_call_id")))
        if name:
            results.setdefault(name, []).append(str(message.get("content", "")))
    return results


def _final_text(state: dict[str, Any]) -> str:
    for message in reversed(state.get("messages", [])):
        if not isinstance(message, dict) or message.get("type") != "ai":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def _run_scenario(
    client: Any,
    *,
    csrf: str,
    name: str,
    prompt: str,
    context: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    thread_id = _create_thread(client, csrf)
    response = client.post(
        f"/api/threads/{thread_id}/runs/wait",
        json={
            "assistant_id": "ecom-launch",
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "config": {"recursion_limit": 100},
            "context": context,
            "stream_mode": ["values"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    if response.status_code != 200:
        raise AssertionError(f"{name} run failed: {response.status_code} {response.text}")
    state = response.json()
    runs_response = client.get(f"/api/threads/{thread_id}/runs")
    if runs_response.status_code != 200 or not runs_response.json():
        raise AssertionError(f"{name} run record missing: {runs_response.text}")
    run = runs_response.json()[0]
    if run.get("status") != "success":
        raise AssertionError(f"{name} status is not success: {run}")

    events_response = client.get(f"/api/threads/{thread_id}/runs/{run['run_id']}/events?limit=1000")
    events = events_response.json() if events_response.status_code == 200 else []
    _write_json(output_dir / f"{name}-state.json", state)
    _write_json(output_dir / f"{name}-run.json", run)
    _write_json(output_dir / f"{name}-events.json", events)

    artifacts = state.get("artifacts") or []
    artifact_names = {Path(str(path)).name for path in artifacts}
    for artifact in artifacts:
        virtual_path = str(artifact).lstrip("/")
        download = client.get(f"/api/threads/{thread_id}/artifacts/{virtual_path}")
        if download.status_code == 200:
            target = output_dir / "artifacts" / name / Path(virtual_path).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(download.content)

    calls = _tool_calls(state)
    tool_names = [str(call.get("name")) for call in calls if call.get("name")]
    unexpected = sorted(set(tool_names) - CANARY_TOOLS)
    if unexpected:
        raise AssertionError(f"{name} used tools outside canary policy: {unexpected}")

    return {
        "name": name,
        "thread_id": thread_id,
        "run_id": run["run_id"],
        "status": run["status"],
        "llm_call_count": run.get("llm_call_count", 0),
        "total_tokens": run.get("total_tokens", 0),
        "tool_names": tool_names,
        "artifacts": sorted(artifact_names),
        "final_text": _final_text(state)[:1000],
        "tool_results": _tool_results(state),
    }


def _assert_flash(result: dict[str, Any]) -> None:
    if "OPENSKU_CANARY_OK" not in result["final_text"]:
        raise AssertionError(f"flash canary response mismatch: {result['final_text']!r}")
    if result["tool_names"]:
        raise AssertionError(f"flash canary should not call tools: {result['tool_names']}")


def _assert_ultra(result: dict[str, Any]) -> None:
    if result["tool_names"].count("task") != 3:
        raise AssertionError(f"ultra canary expected three specialists: {result['tool_names']}")
    if set(result["artifacts"]) != PACK_FILES:
        raise AssertionError(f"ultra canary did not deliver 7/7 pack: {result['artifacts']}")
    # The compact renderer invokes the authoritative presenter internally, so
    # the successful preflight result is attached to `render_launch_pack` in
    # the public trace. Keep the legacy `present_files` shape for compatibility
    # with older canary fixtures.
    present_results = [
        *result["tool_results"].get("present_files", []),
        *result["tool_results"].get("render_launch_pack", []),
    ]
    if not present_results or "Successfully presented files" not in present_results[-1]:
        raise AssertionError(f"ultra canary did not finish with a passing preflight: {present_results}")
    max_calls = int(os.environ.get("OPENSKU_CANARY_MAX_MODEL_CALLS", "15"))
    if int(result["llm_call_count"] or 0) > max_calls:
        raise AssertionError(f"ultra canary exceeded model-call budget {max_calls}: {result['llm_call_count']}")
    max_tokens = int(os.environ.get("OPENSKU_CANARY_MAX_TOTAL_TOKENS", "120000"))
    if int(result["total_tokens"] or 0) > max_tokens:
        raise AssertionError(f"ultra canary exceeded token budget {max_tokens}: {result['total_tokens']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("flash", "full"), default="full")
    parser.add_argument("--output-dir", default="canary-results")
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key, base_url, model = _credentials()
    if not api_key:
        summary = {
            "status": "skipped",
            "reason": "OPENSKU_CANARY_API_KEY/OPENAI_API_KEY is not configured",
            "profile": args.profile,
        }
        _write_json(output_dir / "summary.json", summary)
        print("SKIP: live LLM canary key is not configured")
        return 0

    home = Path(tempfile.mkdtemp(prefix="opensku-live-canary-"))
    config_path = home / "config.yaml"
    config_path.write_text(
        _build_live_config(
            home=home,
            api_key=api_key,
            base_url=base_url,
            model=model,
        ),
        encoding="utf-8",
    )
    _prepare_runtime(
        home,
        config_path,
        api_key=api_key,
        base_url=base_url,
    )

    summary: dict[str, Any] = {
        "status": "running",
        "profile": args.profile,
        "model": model,
        "base_url_host": base_url.split("//", 1)[-1].split("/", 1)[0],
        "provider": "langchain_openai:ChatOpenAI",
        "replay": False,
        "scenarios": [],
    }
    _write_json(output_dir / "summary.json", summary)

    try:
        from starlette.testclient import TestClient

        from app.gateway.app import create_app

        with TestClient(create_app()) as client:
            csrf = _register(client)
            flash = _run_scenario(
                client,
                csrf=csrf,
                name="flash",
                prompt=FLASH_PROMPT,
                context={
                    "mode": "flash",
                    "thinking_enabled": False,
                    "is_plan_mode": False,
                    "subagent_enabled": False,
                },
                output_dir=output_dir,
            )
            _assert_flash(flash)
            summary["scenarios"].append(flash)

            if args.profile == "full":
                ultra = _run_scenario(
                    client,
                    csrf=csrf,
                    name="ultra",
                    prompt=ULTRA_PROMPT,
                    context={
                        "mode": "ultra",
                        "thinking_enabled": True,
                        "is_plan_mode": True,
                        "subagent_enabled": True,
                        "reasoning_effort": "high",
                    },
                    output_dir=output_dir,
                )
                _assert_ultra(ultra)
                summary["scenarios"].append(ultra)

        summary["status"] = "passed"
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(output_dir / "summary.json", summary)
        print(summary["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
